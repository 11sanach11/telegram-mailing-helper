CONFIG ?= test_config.json

.PHONY: install run test test-unit test-e2e test-e2e-headed playwright-install

install:
	poetry install

playwright-install: install
	poetry run playwright install chromium

run: install
	cd telegram_mailing_help && PYTHONPATH=$(shell pwd) poetry run python main.py ../$(CONFIG)

# E2E tests – headless (CI-friendly)
test: playwright-install
	poetry run pytest tests/e2e/ -v

test-headed: ## Run e2e tests in a visible browser (developer mode)
	@set -e; 
	vncserver :1 -geometry 1920x1080 -depth 24 -websocketPort 9022 -SecurityTypes None; 
	DISPLAY=:1 poetry run pytest tests/e2e/ -v --headed --slowmo 1500 || STATUS=$$?; 
	vncserver -kill :1; 
	exit $${STATUS:-0}

vnc: ## Start VNC server for IDE test runner (Ctrl+C to stop)
	vncserver :1 -geometry 1920x1080 -depth 24 -websocketPort 9022 -SecurityTypes None
	@echo "VNC started on display :1  —  press Ctrl+C to stop"
	@trap 'vncserver -kill :1; exit 0' INT TERM; while true; do sleep 1; done
