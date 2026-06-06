# Схема endpoint-ов ЛР7 (Request/Response Logging)

## 1) Общие правила

- ЛР7 логирует все HTTP request/response через глобальный middleware.
- Логи сохраняются в таблицу `logs_requests`.
- Пароли, токены, `Authorization` и `secret_key` маскируются.
- Просмотр и удаление логов доступны только через RBAC permissions.
- Swagger-группа: `request-logs`.

## 2) Admin endpoints

| Метод | Путь | Permission | Ответ |
| --- | --- | --- | --- |
| `GET` | `/api/ref/log/request` | `get-list-log` | `LogRequestCollectionDTO` |
| `GET` | `/api/ref/log/request/{log_request_id}` | `read-log` | `LogRequestDTO` |
| `DELETE` | `/api/ref/log/request/{log_request_id}` | `delete-log` | `204 No Content` |

## 3) Фильтрация списка

Параметр `filter` передается как JSON-массив:

```json
[
  {"key": "response_status", "value": "200"},
  {"key": "user_agent", "value": "curl"}
]
```

Разрешенные поля:

- `user_id`
- `response_status`
- `ip_address`
- `user_agent`
- `controller_path`

`user_agent` фильтруется через частичное совпадение, остальные поля - точным сравнением.

## 4) Сортировка списка

Параметр `sortBy` передается как JSON-массив:

```json
[
  {"key": "called_at", "order": "desc"}
]
```

Разрешенные поля:

- `id`
- `called_at`
- `response_status`
- `user_id`
- `ip_address`
- `controller_path`

## 5) Пагинация

- `page` - номер страницы, по умолчанию `1`.
- `count` - элементов на странице, по умолчанию `10`, максимум `100`.

## 6) Очистка старых логов

CLI-команда:

```bash
python -m app.request_log_cleaner
```

Удаляет записи, у которых `called_at` старше `REQUEST_LOG_RETENTION_HOURS`.
По умолчанию используется `73` часа.

Также при старте приложения запускается background scheduler, который повторяет очистку
каждые `REQUEST_LOG_CLEAN_INTERVAL_SECONDS` секунд. Значение по умолчанию - `3600`.
