# ЛР7: короткие ответы для защиты

## Что реализовано?

Глобальное логирование всех HTTP request/response в таблицу `logs_requests`.
Администратор может смотреть, фильтровать, сортировать и удалять записи.

## Почему middleware глобальное?

Так логируются все запросы приложения, включая `/hooks/git` из ЛР6 и публичные auth endpoints.

## Что пишется в лог?

URL, HTTP-метод, контроллер, метод, request body/headers, user_id, IP,
User-Agent, response status, response body/headers, `called_at`, `created_at`.

## Где защита секретов?

В `app/request_log_sanitizer.py`.
Маскируются пароли, токены, `Authorization`, `secret_key`.

## Какие admin endpoints?

```http
GET    /api/ref/log/request
GET    /api/ref/log/request/{log_request_id}
DELETE /api/ref/log/request/{log_request_id}
```

## Какие permissions?

```text
get-list-log
read-log
delete-log
```

Они назначаются роли `admin` миграцией ЛР7.

## Как чистятся старые логи?

Командой:

```bash
python -m app.request_log_cleaner
```

Удаляются записи старше `REQUEST_LOG_RETENTION_HOURS`, по умолчанию `73` часа.
Дополнительно в lifespan приложения запущен background scheduler, который выполняет
очистку каждые `REQUEST_LOG_CLEAN_INTERVAL_SECONDS` секунд.

## Где находится код ЛР7?

- `app/request_log_middleware.py` - глобальное логирование.
- `app/request_log_service.py` - работа с логами.
- `app/request_log_routes.py` - admin endpoints.
- `app/request_log_sanitizer.py` - маскирование чувствительных данных.
- `app/request_log_cleaner.py` - очистка старых логов.
- `app/request_log_scheduler.py` - автоматический запуск очистки по расписанию.
- `alembic/versions/20260604_0005_add_request_response_logs.py` - миграция и permissions.
