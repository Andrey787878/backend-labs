# Проверка ЛР7 через Swagger

Откройте `http://localhost:8080/docs`.

## 1. Подготовка

1. Выполните миграции:

```bash
alembic upgrade head
```

2. Убедитесь, что роль `admin` получила permissions:

```text
get-list-log
read-log
delete-log
```

3. Авторизуйтесь как администратор и вставьте Bearer token в Swagger.

## 2. Проверка списка логов

Вызовите:

```http
GET /api/ref/log/request
```

Ожидаемо: `200`, DTO с `items`, `page`, `pages`, `total`, `count`.

## 3. Проверка фильтрации

Пример `filter`:

```json
[{"key":"response_status","value":"200"}]
```

Ожидаемо: в ответе только записи со статусом `200`.

## 4. Проверка сортировки

Пример `sortBy`:

```json
[{"key":"called_at","order":"desc"}]
```

Ожидаемо: новые записи идут первыми.

## 5. Проверка просмотра одного лога

Вызовите:

```http
GET /api/ref/log/request/{log_request_id}
```

Ожидаемо: полные данные request/response.

## 6. Проверка удаления

Вызовите:

```http
DELETE /api/ref/log/request/{log_request_id}
```

Ожидаемо: `204 No Content`.

## 7. Проверка безопасности

Сделайте запрос `/api/auth/login` или `/api/auth/register`.
В полном логе значения `password`, `c_password`, `Authorization`, `token`, `access_token`,
`refresh_token` должны быть замаскированы.

## 8. Проверка глобальности middleware

Вызовите `/hooks/git` из ЛР6.
После этого запрос должен появиться в `/api/ref/log/request`.

## 9. Проверка автоматической очистки

В `.env` должны быть заданы:

```env
REQUEST_LOG_RETENTION_HOURS=73
REQUEST_LOG_CLEAN_INTERVAL_SECONDS=3600
```

Для быстрой ручной проверки можно запустить:

```bash
python -m app.request_log_cleaner
```
