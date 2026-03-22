CONFIG ?= test_config.json
IMAGE  ?= telegram-mailing-helper
APP_TELEGRAM_TOKEN ?=

.PHONY: install run test test-unit test-e2e test-e2e-headed playwright-install \
        docker-build docker-run docker-stop

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

docker-build: ## Build Docker image (IMAGE=telegram-mailing-helper)
	docker build -t $(IMAGE) .

docker-run: docker-build ## Build and run the app in Docker; pass token via APP_TELEGRAM_TOKEN=<token>
	docker run --rm \
		--name $(IMAGE) \
		-e APP_TELEGRAM_TOKEN=$(APP_TELEGRAM_TOKEN) \
		-p 23455:23455 \
		-p 23446:23446 \
		-v $(shell pwd)/docker-data/config:/app/config \
		-v $(shell pwd)/docker-data/db:/app/db \
		$(IMAGE)

docker-stop: ## Stop the running container
	docker stop $(IMAGE) 2>/dev/null || true

vnc: ## Start VNC server for IDE test runner (Ctrl+C to stop)
	vncserver :1 -geometry 1920x1080 -depth 24 -websocketPort 9022 -SecurityTypes None
	@echo "VNC started on display :1  —  press Ctrl+C to stop"
	@trap 'vncserver -kill :1; exit 0' INT TERM; while true; do sleep 1; done
