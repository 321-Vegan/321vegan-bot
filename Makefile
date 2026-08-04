SHELL := /bin/sh

COMPOSE ?= docker compose
PYTHON ?= .venv/bin/python

.DEFAULT_GOAL := help

.PHONY: help build up down restart logs ps test sync

help:
	@printf '%s\n' \
		'Available commands:' \
		'  make build    Build the bot image' \
		'  make up       Build and start the bot in the background' \
		'  make down     Stop and remove the bot container' \
		'  make restart  Restart the running bot' \
		'  make logs     Follow the bot logs' \
		'  make ps       Show the service status' \
		'  make test     Run the local test suite' \
		'  make sync     Synchronize Discord commands once and exit'

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart bot

logs:
	$(COMPOSE) logs -f bot

ps:
	$(COMPOSE) ps

test:
	$(PYTHON) -m pytest -q

sync:
	$(COMPOSE) run --rm --build --no-deps bot \
		python -m vegan_discord_bot --sync-commands
