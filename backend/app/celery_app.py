from celery import Celery
from app.config import settings

celery_app = Celery(
    "policy_impact_engine",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.timezone = "UTC"

# Auto-discover tasks
celery_app.autodiscover_tasks(["app.tasks"])
