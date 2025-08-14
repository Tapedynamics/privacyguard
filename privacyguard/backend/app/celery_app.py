"""
Celery application for sending tasks from the FastAPI backend.

This module defines a Celery instance configured via environment variables.
It does not register any tasks itself; tasks are defined in the `worker`
package. The backend uses this instance to enqueue long‑running operations
without blocking HTTP requests.
"""
import os

from celery import Celery


def make_celery() -> Celery:
    broker_url = os.getenv("CELERY_BROKER_URL", "amqp://guest:guest@rabbitmq:5672//")
    backend_url = os.getenv("CELERY_RESULT_BACKEND", "rpc://")
    celery_app = Celery("privacyguard", broker=broker_url, backend=backend_url)
    # Import task modules here when necessary
    return celery_app


celery_app = make_celery()