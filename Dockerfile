# syntax=docker/dockerfile:1.7

FROM python:3.11-slim AS deps

WORKDIR /build

ENV PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-compile -r requirements.txt -t /deps

FROM gcr.io/distroless/python3-debian12:nonroot AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/deps

COPY --from=deps /deps /deps
COPY --chown=65532:65532 app /app/app

EXPOSE 8080

CMD ["-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
