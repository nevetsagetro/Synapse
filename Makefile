.PHONY: setup dev start test backend-test frontend-test build clean

setup:
	./setup.sh

dev:
	./synapse dev

start:
	./synapse start

test:
	./synapse test

backend-test:
	cd backend && . ../.venv/bin/activate && pytest

frontend-test:
	cd frontend && npm test

build:
	cd frontend && npm run build

clean:
	rm -rf backend/.venv frontend/node_modules frontend/dist .pytest_cache
