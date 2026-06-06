# ЛР8: короткие ответы для защиты

## Что реализовано?

Асинхронная генерация аналитического JSON-отчёта через DB-backed очередь `report_jobs`.
Администратор ставит задачу через `POST /api/report/generate`, а worker выполняет её в фоне.

## Почему DB-backed очередь?

В лабораторном FastAPI/PostgreSQL окружении это чистый аналог Laravel Queue без Redis/RabbitMQ.
Очередь реально хранит status, attempts, retry/backoff и путь к отчёту.

## Какие данные использует отчёт?

- `logs_requests` из ЛР7;
- `change_logs` из ЛР4;
- `auth_sessions` для количества авторизаций;
- RBAC-связи ролей и permissions для количества активных прав пользователя.

## Какие рейтинги формируются?

- Рейтинг вызываемых методов.
- Рейтинг изменяемых сущностей.
- Рейтинг пользователей.

## Как защищён endpoint?

Permission:

```text
generate-report
```

Он назначается роли `admin` миграцией ЛР8.

## Где находится отчёт?

В директории из `REPORTS_DIR`, по умолчанию:

```text
reports/analytics_report_<job_id>.json
```

## Как реализована отправка?

Так как SMTP в лабораторном окружении не настроен, доставка эмулируется:
файл сохраняется локально, а `ReportSender` логирует получателя из `REPORT_ADMIN_EMAIL`.

## Где находится код ЛР8?

- `app/report_routes.py` - HTTP endpoint.
- `app/report_queue_service.py` - DB-backed очередь.
- `app/report_data_collector.py` - сбор аналитики.
- `app/report_builder.py` - JSON report.
- `app/report_sender.py` - эмуляция доставки.
- `app/report_job_processor.py` - выполнение одной job.
- `app/report_worker.py` - background worker.
- `alembic/versions/20260606_0006_add_report_jobs.py` - миграция и permission.
