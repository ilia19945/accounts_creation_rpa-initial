FROM python:3.9

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY . /code

ENV PORT 80 5555

EXPOSE $PORT
VOLUME ["/code"]

CMD ["uvicorn", "mainfastapi:app","--reload", "--host", "0.0.0.0", "--port", "80"]
# CMD ["celery", "-A", "tasks", "worker", "-E", "--loglevel=INFO","-Q","new_emps,terminations,other"]
# CMD ["celery", "-A", "tasks", "flower", "--basic_auth=admin:admin"]