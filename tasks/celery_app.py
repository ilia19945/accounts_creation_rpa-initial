"""
Celery application instance.

Import this singleton wherever you need to register a task or
reference the application:
    celery -A tasks.celery_app worker -E --loglevel=INFO -Q new_emps,terminations,other -P gevent
    celery -A tasks.celery_app flower --basic_auth=admin:admin
"""

from celery import Celery

import app.utils.logging as fl

celery_app = Celery(
    'tasks',
    backend='redis://redis:6379/0',
    broker='redis://redis:6379/0',
    queue='new_emps,terminations,other',
)
celery_app.conf.broker_transport_options = {'visibility_timeout': 2592000}  # 30 days

fl.info('Celery server has successfully initialised.')
