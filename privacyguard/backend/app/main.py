"""
FastAPI backend for PrivacyGuard.

This application exposes HTTP endpoints for uploading photos, managing
face metadata and consents, searching by face, and exporting approved
images. It relies on a PostgreSQL database, MinIO/S3 for storage,
Amazon Rekognition for face detection/recognition, RabbitMQ as a
message broker and Celery for asynchronous processing.
"""
import io
import os
import uuid
import zipfile
from datetime import timedelta
from typing import List, Optional

import boto3
from botocore.client import Config
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from . import auth, database, models, schemas, celery_app
from PIL import Image  # for image manipulation in export_privacy_safe
from worker.tasks import blur_faces_in_image  # reuse helper from worker tasks


app = FastAPI(title="PrivacyGuard API")

# Allow CORS for frontend (development). In production, restrict origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def init_db() -> None:
    """Create database tables if they don't exist."""
    models.Base.metadata.create_all(bind=database.engine)


# Initialize tables at startup
@app.on_event("startup")
def on_startup():
    init_db()
    # Create default admin user if not exists
    db = next(database.get_db())
    if not db.query(models.User).filter(models.User.username == "admin").first():
        hashed = auth.get_password_hash(os.getenv("DEFAULT_ADMIN_PASSWORD", "admin"))
        user = models.User(username="admin", password_hash=hashed, role="admin")
        db.add(user)
        db.commit()


# Helper functions for S3/MinIO
def get_s3_client():
    """Return a boto3 S3 client configured for MinIO or AWS."""
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    region = os.getenv("AWS_REGION", "us-east-1")
    endpoint_url = os.getenv("AWS_ENDPOINT_URL")  # for MinIO
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


def upload_to_s3(bucket: str, key: str, data: bytes, content_type: str = "image/jpeg") -> None:
    client = get_s3_client()
    # Ensure bucket exists (creates if not present). MinIO and AWS return error if exists.
    try:
        client.create_bucket(Bucket=bucket)
    except client.exceptions.BucketAlreadyOwnedByYou:
        pass
    except client.exceptions.BucketAlreadyExists:
        pass
    except Exception:
        # ignore other errors; bucket may already exist or creation may not be permitted
        pass
    client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)


def generate_presigned_url(bucket: str, key: str, expires_in: int = 3600) -> str:
    client = get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in,
    )


def get_rekognition_client():
    """Return a boto3 Rekognition client configured from environment variables."""
    return boto3.client(
        "rekognition",
        region_name=os.getenv("AWS_REGION", "us-east-1"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )


def get_collection_id() -> str:
    """Return the Rekognition collection ID used for indexing faces."""
    return os.getenv("AWS_REKOGNITION_COLLECTION", "privacyguard-collection")


# API endpoints

@app.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    """Authenticate a user and issue a JWT token."""
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token_expires = timedelta(minutes=60)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return schemas.Token(access_token=access_token)


@app.post("/upload", response_model=List[int])
def upload_photos(
    files: List[UploadFile] = File(...),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """
    Upload one or more image files.

    Each file is stored in the S3/MinIO bucket and an entry is created in the
    `photos` table with status `in_queue`. A Celery task is enqueued for
    each photo to perform face detection. Only authenticated users may
    upload.
    """
    bucket = os.getenv("S3_BUCKET", "photos")
    uploaded_ids: List[int] = []
    for file in files:
        contents = file.file.read()
        ext = os.path.splitext(file.filename)[1].lower()
        key = f"{uuid.uuid4().hex}{ext}"
        upload_to_s3(bucket, key, contents, content_type=file.content_type or "image/jpeg")
        photo = models.Photo(filename=file.filename, s3_key=key, status=models.PhotoStatus.IN_QUEUE)
        db.add(photo)
        db.commit()
        db.refresh(photo)
        uploaded_ids.append(photo.id)
        # Enqueue Celery task for detection
        celery_app.celery_app.send_task("worker.tasks.process_photo", args=[photo.id])
    return uploaded_ids


@app.get("/photos", response_model=List[schemas.PhotoResponse])
def list_photos(
    status: Optional[models.PhotoStatus] = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """List photos optionally filtered by status."""
    query = db.query(models.Photo)
    if status:
        query = query.filter(models.Photo.status == status)
    photos = query.order_by(models.Photo.upload_time.desc()).all()
    return photos


@app.get("/photos/{photo_id}", response_model=schemas.PhotoResponse)
def get_photo(photo_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    """Retrieve a single photo and its faces."""
    photo = db.query(models.Photo).filter(models.Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    return photo


@app.get("/photos/{photo_id}/url")
def get_photo_url(
    photo_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Return a pre‑signed URL for downloading the original image for the given photo.
    The URL expires after one hour.
    """
    photo = db.query(models.Photo).filter(models.Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    bucket = os.getenv("S3_BUCKET", "photos")
    url = generate_presigned_url(bucket, photo.s3_key, expires_in=3600)
    return {"url": url}


@app.post("/photos/{photo_id}/faces/{face_id}/name", response_model=schemas.FaceResponse)
def set_face_name(
    photo_id: int,
    face_id: int,
    payload: schemas.NameUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Assign a human‑readable name to a face and index it in Rekognition.
    When a face is named, a background task may index the face in the
    collection so that future images can be matched automatically.
    """
    face = db.query(models.Face).filter(models.Face.id == face_id, models.Face.photo_id == photo_id).first()
    if not face:
        raise HTTPException(status_code=404, detail="Face not found")
    face.name = payload.name
    db.commit()
    # Enqueue indexing task
    celery_app.celery_app.send_task("worker.tasks.index_face", args=[face.id])
    db.refresh(face)
    return face


@app.post("/photos/{photo_id}/faces/{face_id}/consent", response_model=schemas.FaceResponse)
def update_consent(
    photo_id: int,
    face_id: int,
    payload: schemas.ConsentUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Update the consent status of a face."""
    face = db.query(models.Face).filter(models.Face.id == face_id, models.Face.photo_id == photo_id).first()
    if not face:
        raise HTTPException(status_code=404, detail="Face not found")
    face.consent_status = payload.consent_status
    db.commit()
    db.refresh(face)
    return face


# ---------------------------------------------------------------------------
# Additional endpoints for privacy safe operations
# ---------------------------------------------------------------------------

@app.post("/photos/{photo_id}/blur")
def queue_blur(
    photo_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Queue a background task to generate a blurred version of the specified photo.

    The task will blur all faces that do not have an approved consent and save
    the blurred image in the same S3 bucket with a `_blur` suffix. This
    endpoint returns immediately after queuing the task.
    """
    photo = db.query(models.Photo).filter(models.Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    # Enqueue Celery task
    celery_app.celery_app.send_task("worker.tasks.generate_blur", args=[photo_id])
    return {"detail": "Blur task enqueued"}


@app.get("/photos/{photo_id}/blurred_url")
def get_blurred_url(
    photo_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Return a pre‑signed URL for the blurred version of a photo if it exists.

    The blurred image is expected to be stored in the same S3 bucket with the
    `_blur` suffix on the key. If the blurred image is not found, a 404
    response is returned. Note that this endpoint does not trigger blur
    generation; use POST /photos/{photo_id}/blur to enqueue the blur task.
    """
    photo = db.query(models.Photo).filter(models.Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    bucket = os.getenv("S3_BUCKET", "photos")
    blur_key = f"{photo.s3_key.rsplit('.', 1)[0]}_blur.jpg"
    s3 = get_s3_client()
    # Check if blurred object exists
    try:
        s3.head_object(Bucket=bucket, Key=blur_key)
    except Exception:
        raise HTTPException(status_code=404, detail="Blurred image not found")
    url = generate_presigned_url(bucket, blur_key, expires_in=3600)
    return {"url": url}


@app.get("/export/privacy-safe")
def export_privacy_safe(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Generate a ZIP archive containing blurred versions of photos with pending or
    rejected consents. For each photo, faces without approved consent are
    blurred. The blurred images are generated on the fly and not saved back
    to S3. This may take several seconds depending on the number of photos.
    """
    bucket = os.getenv("S3_BUCKET", "photos")
    photos = db.query(models.Photo).all()
    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        s3 = get_s3_client()
        for photo in photos:
            # Determine if any face lacks approval
            if not photo.faces:
                continue
            needs_blur = any(
                face.consent_status != models.ConsentStatus.APPROVED for face in photo.faces
            )
            if not needs_blur:
                continue
            # Download image
            try:
                obj = s3.get_object(Bucket=bucket, Key=photo.s3_key)
                original_data = obj["Body"].read()
            except Exception:
                continue
            # Open image
            try:
                img = Image.open(io.BytesIO(original_data)).convert("RGB")
            except Exception:
                continue
            # Collect boxes to blur
            boxes = [face.bbox for face in photo.faces if face.consent_status != models.ConsentStatus.APPROVED]
            if boxes:
                blurred_img = blur_faces_in_image(img, boxes)
            else:
                blurred_img = img
            buffer = io.BytesIO()
            blurred_img.save(buffer, format="JPEG")
            buffer.seek(0)
            zf.writestr(f"{photo.filename}", buffer.read())
    mem_zip.seek(0)
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        mem_zip,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=privacy_safe_photos.zip"},
    )


@app.get("/export/approved")
def export_approved(db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    """
    Generate a ZIP archive containing all photos where every face is approved or
    there are no faces. Photos with any pending/rejected faces are excluded.
    Returns the ZIP as a streaming response.
    """
    bucket = os.getenv("S3_BUCKET", "photos")
    all_photos = db.query(models.Photo).all()
    approved_photos = []
    for photo in all_photos:
        if not photo.faces:
            approved_photos.append(photo)
            continue
        all_approved = all(face.consent_status == models.ConsentStatus.APPROVED for face in photo.faces)
        if all_approved:
            approved_photos.append(photo)
    # Create zip in memory
    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        s3 = get_s3_client()
        for photo in approved_photos:
            obj = s3.get_object(Bucket=bucket, Key=photo.s3_key)
            data = obj["Body"].read()
            # Use original filename for clarity
            zf.writestr(photo.filename, data)
    mem_zip.seek(0)
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        mem_zip,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=approved_photos.zip"},
    )


@app.post("/client/search")
def client_search(file: UploadFile = File(...), db: Session = Depends(database.get_db)):
    """
    Endpoint for clients: upload a selfie and receive a list of photos where
    the same face appears. The selfie is processed via Rekognition to
    search the pre‑existing collection. The selfie is not stored.
    Returns a JSON list of objects with photo_id and a download URL.
    """
    rekog = get_rekognition_client()
    bucket = os.getenv("S3_BUCKET", "photos")
    collection_id = get_collection_id()
    # Read selfie into memory
    image_bytes = file.file.read()
    try:
        response = rekog.search_faces_by_image(
            CollectionId=collection_id,
            Image={"Bytes": image_bytes},
            MaxFaces=10,
            FaceMatchThreshold=80,
        )
    except Exception as e:
        # if collection does not exist or error, return empty list
        return []
    matches = response.get("FaceMatches", [])
    matched_ids = [m["Face"]["FaceId"] for m in matches]
    if not matched_ids:
        return []
    # Find faces in DB with rekognition_face_id in matched_ids
    faces = db.query(models.Face).filter(models.Face.rekognition_face_id.in_(matched_ids)).all()
    unique_photo_ids = sorted({f.photo_id for f in faces})
    results = []
    for pid in unique_photo_ids:
        photo = db.query(models.Photo).get(pid)
        if not photo:
            continue
        url = generate_presigned_url(bucket, photo.s3_key, expires_in=3600)
        results.append({"photo_id": pid, "url": url})
    return results