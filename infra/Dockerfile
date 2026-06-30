FROM python:3.12-slim

# libgomp1: OpenMP runtime required by LightGBM / XGBoost (absent in slim image)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY requirements.txt ./
RUN uv pip install --system --no-cache -r requirements.txt

COPY env ./env
COPY configs ./configs
COPY src ./src

# entrypoints は src/runner/ パッケージ。src を import 解決パスに通す。
ENV PYTHONPATH=/app/src

ENTRYPOINT ["python"]
CMD ["-m", "runner.experiment.train", "--config", "configs/lgbm_baseline.yaml"]
