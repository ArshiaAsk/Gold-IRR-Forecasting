# Reproducibility targets. Python 3.12. See README.md for what each target does.
# Uses .venv/bin/python when present, otherwise python3 on PATH.

PYTHON ?= $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; else echo python3; fi)
PORT ?= 8000
APP_PORT ?= 8501
IMAGE ?= gold-irr-forecasting

.PHONY: help install test check evaluate backtest api app docker-build docker-run fetch-data

help:
	@echo "install       install runtime + development dependencies"
	@echo "test          run the full test suite (pytest)"
	@echo "check         run tests and the README-numbers check"
	@echo "evaluate      re-run the committed Stage 3 protocol (long: ~21 min, retrains)"
	@echo "backtest      re-run the committed Stage 4 economic check (inference only)"
	@echo "api           start the FastAPI service on port $(PORT)"
	@echo "app           start the Streamlit app on port $(APP_PORT)"
	@echo "docker-build  build the single-service image ($(IMAGE))"
	@echo "docker-run    run the API container on port $(PORT)"
	@echo "fetch-data    fetch TGJU + Yahoo into data/raw/ (needs yfinance, curl_cffi)"

install:
	$(PYTHON) -m pip install -r requirements-dev.txt

test:
	$(PYTHON) -m pytest -q

check: test
	$(PYTHON) scripts/check_readme_numbers.py

evaluate:
	@echo "Re-running the pre-registered Stage 3 protocol. This retrains 109 LSTMs"
	@echo "and took 1,259.6 s (21.0 min) on the reference machine."
	$(PYTHON) -m src.evaluate --variant all --artifact

backtest:
	$(PYTHON) -m src.backtest_check

api:
	API_KEY=$${API_KEY:-demo-key} $(PYTHON) -m uvicorn src.api.main:app --host 127.0.0.1 --port $(PORT)

app:
	$(PYTHON) -m streamlit run streamlit_app.py --server.port $(APP_PORT)

docker-build:
	docker build -t $(IMAGE) .

docker-run:
	docker run --rm -p $(PORT):8000 -e API_KEY=demo-key $(IMAGE)

fetch-data:
	$(PYTHON) scripts/fetch_data.py
