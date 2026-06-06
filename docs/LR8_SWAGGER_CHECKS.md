# Проверка ЛР8 через Swagger

Откройте `http://localhost:8080/docs`.

## 1. Подготовка

1. Выполните миграции:

```bash
python -m alembic upgrade head
```

2. Убедитесь, что роль `admin` получила permission:

```text
generate-report
```

3. Авторизуйтесь как администратор и вставьте Bearer token в Swagger.

## 2. Проверка доступа

Вызовите без токена:

```http
POST /api/report/generate
```

Ожидаемо: `401`.

Вызовите обычным пользователем без permission.

Ожидаемо: `403`.

## 3. Проверка постановки в очередь

Вызовите администратором:

```http
POST /api/report/generate
```

Ожидаемо: `202`.

Пример ответа:

```json
{
  "message": "Отчёт поставлен в очередь на генерацию.",
  "job_id": 1,
  "status": "queued"
}
```

## 4. Проверка worker-а

Через несколько секунд проверьте таблицу `report_jobs`.

Ожидаемо:

- `status = succeeded`;
- `attempts >= 1`;
- `report_path` заполнен.

## 5. Проверка файла отчёта

Проверьте файл:

```text
reports/analytics_report_<job_id>.json
```

Внутри должны быть:

- `type`;
- `period`;
- `method_rating`;
- `entity_rating`;
- `user_rating`.

## 6. Проверка интеграции с ЛР7

Вызов `POST /api/report/generate` должен появиться в request/response логах:

```http
GET /api/ref/log/request
```
