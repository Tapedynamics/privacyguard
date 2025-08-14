"""
Celery tasks for processing photos in the PrivacyGuard application.

This module defines asynchronous tasks for face detection, indexing and
image manipulation. Workers run these tasks in the background, reading
messages from RabbitMQ and updating the PostgreSQL database. The tasks
use boto3 to interact with MinIO/S3 and Amazon Rekognition, and Pillow
to manipulate images for blurring.
"""
import io
import os
from typing import List

import boto3
from botocore.client import Config
from celery import Celery
from PIL import Image, ImageFilter
from sqlalchemy.orm import Session

from backend.app import database, models


# Create Celery instance. This must match the configuration used by the backend.
broker_url = os.getenv("CELERY_BROKER_URL", "amqp://guest:guest@rabbitmq:5672//")
backend_url = os.getenv("CELERY_RESULT_BACKEND", "rpc://")
celery = Celery("worker", broker=broker_url, backend=backend_url)


def get_s3_client():
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    region = os.getenv("AWS_REGION", "us-east-1")
    endpoint_url = os.getenv("AWS_ENDPOINT_URL")
    use_ssl = os.getenv("AWS_USE_SSL", "False").lower() == "true"
    return boto3.client(
        "s3",
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=region,
        endpoint_url=endpoint_url,
        use_ssl=use_ssl,
        config=Config(signature_version="s3v4"),
    )


def get_rekognition_client():
    return boto3.client(
        "rekognition",
        region_name=os.getenv("AWS_REGION", "us-east-1"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )


def get_collection_id() -> str:
    return os.getenv("AWS_REKOGNITION_COLLECTION", "privacyguard-collection")


@celery.task(name="worker.tasks.process_photo")
def process_photo(photo_id: int) -> None:
    """
    Celery task that performs face detection on a photo.

    Steps:
        1. Set photo status to PROCESSING.
        2. Download image from S3/MinIO.
        3. Call Rekognition DetectFaces.
        4. Save bounding boxes to the faces table.
        5. Update photo status to PROCESSED.
    """
    db: Session = next(database.get_db())
    photo = db.query(models.Photo).filter(models.Photo.id == photo_id).first()
    if not photo:
        return
    photo.status = models.PhotoStatus.PROCESSING
    db.commit()
    bucket = os.getenv("S3_BUCKET", "photos")
    s3 = get_s3_client()
    try:
        obj = s3.get_object(Bucket=bucket, Key=photo.s3_key)
        data = obj["Body"].read()
    except Exception as e:
        # Mark as processed even if image cannot be retrieved
        photo.status = models.PhotoStatus.PROCESSED
        db.commit()
        return
    rekog = get_rekognition_client()
    try:
        response = rekog.detect_faces(
            Image={"Bytes": data},
            Attributes=["DEFAULT"],
        )
        face_details = response.get("FaceDetails", [])
    except Exception as e:
        face_details = []
    # Remove existing face records (idempotence)
    for f in photo.faces:
        db.delete(f)
    db.commit()
    # Save new faces
    for fd in face_details:
        bbox = fd.get("BoundingBox", {})
        # Rekognition returns relative values (0-1)
        face_record = models.Face(
            photo_id=photo.id,
            rekognition_face_id=None,
            bbox={
                "left": bbox.get("Left"),
                "top": bbox.get("Top"),
                "width": bbox.get("Width"),
                "height": bbox.get("Height"),
            },
            name=None,
            consent_status=models.ConsentStatus.PENDING,
        )
        db.add(face_record)
    photo.status = models.PhotoStatus.PROCESSED
    db.commit()


@celery.task(name="worker.tasks.index_face")
def index_face(face_id: int) -> None:
    """
    Index a named face into the Rekognition collection.

    The face is cropped out of the original image using its bounding box and
    uploaded to Rekognition. The returned FaceId is stored in the database.
    """
    db: Session = next(database.get_db())
    face = db.query(models.Face).filter(models.Face.id == face_id).first()
    if not face or not face.name:
        return
    photo = face.photo
    bucket = os.getenv("S3_BUCKET", "photos")
    s3 = get_s3_client()
    try:
        obj = s3.get_object(Bucket=bucket, Key=photo.s3_key)
        data = obj["Body"].read()
    except Exception:
        return
    # Open image with Pillow
    try:
        image = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:
        return
    w, h = image.size
    # Compute pixel coordinates from relative bbox
    bbox = face.bbox
    left = int(bbox["left"] * w)
    top = int(bbox["top"] * h)
    width = int(bbox["width"] * w)
    height = int(bbox["height"] * h)
    right = left + width
    bottom = top + height
    cropped = image.crop((left, top, right, bottom))
    buffer = io.BytesIO()
    cropped.save(buffer, format="JPEG")
    cropped_bytes = buffer.getvalue()
    rekog = get_rekognition_client()
    collection_id = get_collection_id()
    # Ensure collection exists
    try:
        rekog.create_collection(CollectionId=collection_id)
    except rekog.exceptions.ResourceAlreadyExistsException:
        pass
    try:
        response = rekog.index_faces(
            CollectionId=collection_id,
            Image={"Bytes": cropped_bytes},
            ExternalImageId=str(face.id),
            DetectionAttributes=["DEFAULT"],
        )
        face_records = response.get("FaceRecords", [])
        if face_records:
            # Store the FaceId of the first record
            face_id_returned = face_records[0]["Face"]["FaceId"]
            face.rekognition_face_id = face_id_returned
            db.commit()
    except Exception:
        pass


def blur_faces_in_image(image: Image.Image, boxes: List[dict]) -> Image.Image:
    """
    Apply a Gaussian blur to all regions defined by relative bounding boxes.

    Args:
        image: Pillow Image to modify.
        boxes: List of dicts with keys left, top, width, height (relative 0-1).

    Returns:
        A new Image with blurred regions.
    """
    w, h = image.size
    result = image.copy()
    for bbox in boxes:
        left = int(bbox["left"] * w)
        top = int(bbox["top"] * h)
        width = int(bbox["width"] * w)
        height = int(bbox["height"] * h)
        right = min(left + width, w)
        bottom = min(top + height, h)
        region = result.crop((left, top, right, bottom))
        blurred_region = region.filter(ImageFilter.GaussianBlur(radius=15))
        result.paste(blurred_region, (left, top))
    return result


@celery.task(name="worker.tasks.generate_blur")
def generate_blur(photo_id: int) -> None:
    """
    Generate a blurred version of a photo for faces without consent.

    Creates a copy of the original image where all faces with consent_status
    not APPROVED are blurred. The blurred image is saved back to S3 with
    the suffix `_blur`.
    """
    db: Session = next(database.get_db())
    photo = db.query(models.Photo).filter(models.Photo.id == photo_id).first()
    if not photo:
        return
    bucket = os.getenv("S3_BUCKET", "photos")
    s3 = get_s3_client()
    try:
        obj = s3.get_object(Bucket=bucket, Key=photo.s3_key)
        original_data = obj["Body"].read()
    except Exception:
        return
    image = Image.open(io.BytesIO(original_data)).convert("RGB")
    # Collect bounding boxes of faces that need blurring
    boxes_to_blur = [face.bbox for face in photo.faces if face.consent_status != models.ConsentStatus.APPROVED]
    if not boxes_to_blur:
        # Nothing to blur; copy original
        blurred_image = image
    else:
        blurred_image = blur_faces_in_image(image, boxes_to_blur)
    buffer = io.BytesIO()
    blurred_image.save(buffer, format="JPEG")
    blurred_bytes = buffer.getvalue()
    # Save blurred image with new key
    key = f"{photo.s3_key.rsplit('.', 1)[0]}_blur.jpg"
    s3.put_object(Bucket=bucket, Key=key, Body=blurred_bytes, ContentType="image/jpeg")
    # Optionally store blurred key in DB or elsewhere
    return