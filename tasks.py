import time

from funcs import gmail_app_password
from celery import Celery

from email.mime.text import MIMEText
import smtplib

celery_app = Celery('tasks', backend='redis://localhost', broker='redis://localhost',queue='new_emps,terminations,other')

# to run celery with 3 queues type in terminal:
# celery -A tasks worker -E --loglevel=INFO -Q new_emps,terminations,other -P gevent

@celery_app.task
def send_gmail_message(sender, to, cc, subject, message_text):
    message = MIMEText(message_text, 'html')
    message['to'] = to
    message['from'] = sender
    message['cc'] = cc
    message['subject'] = subject
    # print(message)
    server = smtplib.SMTP('smtp.gmail.com: 587')
    server.starttls()
    server.login(sender, gmail_app_password)
    server.sendmail(sender, to, message.as_string())
    server.quit()
    return f'Message was successfully sent to:{to}'

# result = send_gmail_message.apply_async(
#                                         ('ilya.konovalov@junehomes.com',
#                                         'ilya.konovalov@junehomes.com',
#                                         'ilya.konovalov+1@junehomes.com',
#                                         'test message',
#                                         'final_draft'),
#                                       countdown=10)

# revoke tasks  https://docs.celeryq.dev/en/stable/userguide/workers.html#revoke-revoking-tasks
#               https://stackoverflow.com/questions/8920643/cancel-an-already-executing-task-with-celery
#
# in celery it's impossible to  delete the received task. you can only flag it as revoked which means it will immediately marked as revoked when ETA
# passes.
# to  revoke the task:
# - in python console:
# >>> from tasks import celery_app
# >>> a = celery_app.control.inspect()
# >>> a.scheduled()
# identify the id of the task
# celery_app.control.revoke('9c0f7294-2a1b-4ad3-9a6b-d86ef9be9795')


@celery_app.task
def add(x, y):
    time.sleep(600)
    return x + y

@celery_app.task
def multiply(x, y):
    time.sleep(10)
    return x * y

