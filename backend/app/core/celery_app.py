from celery import Celery
from app.core.config import settings
import logging
import sys

# Configure logging to file and stdout for Celery worker
log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    handlers=[
        logging.FileHandler("/db/app.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

# Suppress verbose httpx logging (HTTP Request, 301 Moved Permanently, etc.)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

celery_app = Celery("worker", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

celery_app.conf.update(task_track_started=True)

# Configure Celery Beat schedule
celery_app.conf.beat_schedule = {
    'check-schedules-every-minute': {
        'task': 'app.tasks.sync.check_schedules_task',
        'schedule': 60.0,  # Run every 60 seconds
    },
}
celery_app.conf.timezone = 'UTC'

# Import tasks to register them
from app.tasks import sync  # noqa
from app.tasks import m3u_sync  # noqa
