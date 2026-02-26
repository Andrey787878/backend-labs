FROM python:3.11-slim@sha256:fba6f3b73795df99960f4269b297420bdbe01a8631fc31ea3f121f2486d332d0 AS build
WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel \
  && pip install --no-cache-dir -r requirements.txt -t /deps

COPY . /app

FROM gcr.io/distroless/python3-debian12:nonroot@sha256:3aa5d1eb6e9f83a4ed806174bb40296e04758ab95f53b61f976d3df2b57ca289
WORKDIR /app

COPY --from=build /deps /deps
COPY --from=build /app /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/deps

EXPOSE 8080

CMD ["-m", "gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "4", "--timeout", "60"]