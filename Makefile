.PHONY: up down stop logs build restart shell

up:
	docker-compose up -d --build

down:
	docker-compose down

stop:
	docker-compose stop

logs:
	docker-compose logs -f

build:
	docker-compose build

restart:
	docker-compose restart

shell:
	docker-compose exec app bash
