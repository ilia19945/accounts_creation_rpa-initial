import time

from funcs import gmail_app_password
from celery import Celery

from email.mime.text import MIMEText
import smtplib
import fast_api_logging as fl

celery_app = Celery('tasks', backend='redis://localhost', broker='redis://localhost', queue='new_emps,terminations,other')
fl.info('Celery server has successfully initialised.')

# to run celery with 3 queues type in terminal:
# celery -A tasks worker -E --loglevel=INFO -Q new_emps,terminations,other -P gevent
# to run flower with admin user:
# celery -A tasks flower --basic_auth=admin:admin

@celery_app.task
def send_gmail_message(sender, to, cc, subject, message_text, countdown):
    fl.info(f'A new task is received. Email subject: {subject}. To: {to}. Countdown (in hours):{countdown}.')

    message = MIMEText(message_text, 'html')
    message['from'] = sender
    message['to'] = ",".join(to)
    message['cc'] = ",".join(cc)
    message['subject'] = subject

    recipients = to + cc

    server = smtplib.SMTP('smtp.gmail.com: 587')
    server.starttls()
    server.login(sender, gmail_app_password)
    server.sendmail(from_addr=sender, to_addrs=recipients, msg=message.as_string())
    server.quit()
    fl.info(f'Message will be sent to:{to}, hours to send: {countdown}')
    return f'Message was successfully sent to:{to}, hours to send was: {countdown}'


# result = send_gmail_message.apply_async(
#                                         ('ilya.konovalov@junehomes.com', # from
#                                          ["ilia19945@mail.ru"], # to
#                                          ['maria.zhuravleva@junehomes.com', 'ilia19945@gmail.com', supervisor_email], # cc
#                                          'test message', # subject
#                                          'final_draft' # email body
#                                         ),
#                                       countdown=10)
#                                                           ^^^ comments should be removed.

# revoke tasks  https://docs.celeryq.dev/en/stable/userguide/workers.html#revoke-revoking-tasks
#               https://stackoverflow.com/questions/8920643/cancel-an-already-executing-task-with-celery
#
# in celery it's impossible to  delete the received task wo using a flower GUI. you can only flag it as revoked which means it will immediately marked as revoked when ETA
# passes.
# to  revoke the task:
# - in python console:
# >>> from tasks import celery_app
# >>> a = celery_app.control.inspect()
# >>> a.scheduled()
# identify the id of the task
# celery_app.control.revoke('c944ee91-d4e7-4733-a82b-2dbdaef7c809')

#
# @celery_app.task
# def add(x, y):
#     time.sleep(600)
#     return x + y
#
#
# @celery_app.task
# def multiply(x, y):
#     time.sleep(10)
#     return x * y
