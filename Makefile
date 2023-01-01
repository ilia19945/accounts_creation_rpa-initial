run:
	docker run -d -p 80:80 -p 5555:5555 --env-file .env --rm --name account_creation_automation account_creation_automation \
	&& celery -A tasks worker -E --loglevel=INFO -Q new_emps,terminations,other -P gevent \
	&& celery -A tasks flower --basic_auth=admin:admin
run-dev:
	docker run -d -p 80:80 --env-file .env -v C:\PythonProjects\Fastapi:/code --rm --name account_creation_automation account_creation_automation


build: 
	docker build . -t account_creation_automation


stop:
	docker stop account_creation_automation