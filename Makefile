# 3L 交易系统 — Makefile
# 用法: make <target>

APP_DIR := $(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
VENV_DIR := $(APP_DIR)/.venv
PYTHON := $(VENV_DIR)/bin/python
PIP := $(VENV_DIR)/bin/pip

.PHONY: install run test lint clean docker-build docker-run

# ── 安装 ────────────────────────────────────────
install: $(VENV_DIR)/bin/python
	$(PIP) install -r $(APP_DIR)/requirements.txt

install-dev: install
	$(PIP) install -r $(APP_DIR)/requirements-dev.txt

$(VENV_DIR)/bin/python:
	python3 -m venv $(VENV_DIR)
	$(PIP) install --upgrade pip -q

# ── 运行 ────────────────────────────────────────
run:
	$(PYTHON) $(APP_DIR)/server.py

# ── 测试 ────────────────────────────────────────
test:
	cd $(APP_DIR) && $(PYTHON) -m pytest tests/ --ignore=tests/test_api.py -q

test-all:
	cd $(APP_DIR) && $(PYTHON) -m pytest tests/ -q

test-api:
	cd $(APP_DIR) && $(PYTHON) -m pytest tests/test_api.py -q

# ── 代码检查 ────────────────────────────────────
lint:
	$(PIP) install -q flake8 2>/dev/null || true
	$(VENV_DIR)/bin/flake8 $(APP_DIR)/*.py $(APP_DIR)/services/ --max-line-length=100

# ── 清理 ────────────────────────────────────────
clean:
	rm -rf $(VENV_DIR)
	find $(APP_DIR) -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find $(APP_DIR) -name "*.pyc" -delete

# Docker
docker-build:
	docker build -t 3l-server $(APP_DIR)

docker-run:
	docker run -d -p 8080:8080 \
		-v $(DATA_DIR):/data \
		-v $(APP_DIR)/logs:/app/logs \
		--name 3l-server \
		--restart unless-stopped \
		3l-server
