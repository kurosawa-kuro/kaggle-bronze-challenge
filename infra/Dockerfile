FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY requirements.txt ./
RUN uv pip install --system --no-cache -r requirements.txt

COPY conf ./conf
COPY configs ./configs
COPY src ./src
COPY train.py collect.py submit.py vertex_run.py ./

ENTRYPOINT ["python"]
CMD ["train.py", "--config", "configs/lgbm_baseline.yaml"]
