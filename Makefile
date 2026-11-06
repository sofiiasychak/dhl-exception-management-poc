SHELL := /bin/sh
-include .env
AWS_PROFILE := $(if $(strip $(AWS_PROFILE)),$(AWS_PROFILE),default)
AWS_REGION := $(if $(strip $(AWS_REGION)),$(AWS_REGION),eu-central-1)
STACK_NAME := $(if $(strip $(STACK_NAME)),$(STACK_NAME),exception-management-poc)
export AWS_PROFILE
export AWS_REGION
export STACK_NAME
export DEPLOYMENT_BUCKET

COMPOSE := docker compose

.PHONY: help up down seed test deploy destroy

help:
	@printf '%s\n' \
	  'make help     Show available commands' \
	  'make up       Start the local app, DynamoDB Local, and Cognito emulator' \
	  'make down     Stop the local stack' \
	  'make seed     Wipe and reload demo data in DynamoDB' \
	  'make test     Run backend and frontend checks' \
	  'make deploy   Deploy the CloudFormation stack and frontend to AWS' \
	  'make destroy  Delete the CloudFormation stack (retained buckets may need emptying)'

up:
	$(COMPOSE) up --build -d
	@printf 'Frontend: http://localhost:5173  API: http://localhost:8000/docs\n'

down:
	$(COMPOSE) down

seed:
	$(COMPOSE) run --rm api python -m app.seed

test:
	PYTHONPATH=backend python3 -m pytest backend/tests backend/app --disable-warnings -q
	cd frontend && npm run typecheck && npm run build

deploy:
	python3 infra/deploy.py

destroy:
	python3 infra/destroy.py
