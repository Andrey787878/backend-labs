# Схема endpoint-а ЛР8 (Queued Analytics Reports)

## 1) Общие правила

- ЛР8 формирует аналитический отчёт асинхронно через DB-backed очередь.
- Источники данных: `logs_requests` из ЛР7 и `change_logs` из ЛР4.
- Доступ к запуску отчёта есть только у администратора с permission `generate-report`.
- Swagger-группа: `reports`.
- Формат отчёта: JSON.

## 2) Endpoint

| Метод | Путь | Permission | Ответ |
| --- | --- | --- | --- |
| `POST` | `/api/report/generate` | `generate-report` | `202`, `ReportGenerateResponseDTO` |

Успешный ответ:

```json
{
  "message": "Отчёт поставлен в очередь на генерацию.",
  "job_id": 1,
  "status": "queued"
}
```

## 3) Queue storage

Очередь хранится в таблице `report_jobs`.

Основные статусы:

- `queued`
- `running`
- `succeeded`
- `failed`

Повторные попытки регулируются:

- `REPORT_JOB_MAX_ATTEMPTS`
- `REPORT_JOB_RETRY_DELAY_MINUTES`
- `REPORT_JOB_TIMEOUT_MINUTES`

## 4) Report content

Файл сохраняется в `REPORTS_DIR`, пример:

```text
reports/analytics_report_1.json
```

Структура отчёта:

```json
{
  "type": "Analytics report",
  "generated_at": "...",
  "period": {
    "from": "...",
    "to": "...",
    "hours": 24
  },
  "method_rating": [],
  "entity_rating": [],
  "user_rating": []
}
```

## 5) Что считается

- `method_rating`: количество вызовов методов из `logs_requests`.
- `entity_rating`: количество изменений сущностей из `change_logs`.
- `user_rating`: запросы, изменения, авторизации и текущее количество permissions пользователя.

Пункт про "количество разрешений" в ТЗ неоднозначен, поэтому в ЛР8 используется
текущее количество активных permissions пользователя через его роли.
