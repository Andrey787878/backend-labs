# Схема endpoint-а ЛР6 (Git Webhook Deployment)

## 1) Общие правила

- ЛР6 вынесена в отдельную Swagger-группу `git-webhook`.
- Webhook открыт для внешнего Git-сервиса и не требует JWT/RBAC.
- Доступ защищается только `secret_key`, который сравнивается с `GIT_WEBHOOK_SECRET`.
- Секрет хранится в `.env` и не логируется.
- Ответы возвращаются в JSON.

## 2) Endpoint

| Метод | Путь | Body | Успех |
| --- | --- | --- | --- |
| `POST` | `/hooks/git` | `GitWebhookRequest` | `200`, `DeploymentResponseDTO` |

## 3) Request body

JSON:

```json
{
  "secret_key": "00000000-0000-0000-0000-000000000000"
}
```

Form body также поддерживается через поле `secret_key`.

## 4) HTTP-статусы

- `200` - deployment выполнен успешно.
- `403` - неверный `secret_key`.
- `409` - deployment уже выполняется.
- `422` - `secret_key` не передан или body некорректный.
- `500` - ошибка проверки Git-репозитория или выполнения Git-команд.

## 5) Git-команды

Команды выполняются строго в таком порядке:

```bash
git checkout <GIT_DEFAULT_BRANCH>
git reset --hard HEAD
git pull origin <GIT_DEFAULT_BRANCH>
```

Ветка задается через `GIT_DEFAULT_BRANCH`, по умолчанию `main`.

## 6) Логи и lock

- Логи пишутся в `deployment_logs/deployment.log`.
- Lock пишется в `deployment_logs/deploy.lock`.
- Lock имеет TTL из `GIT_WEBHOOK_LOCK_TTL_SECONDS`.
- Каждая Git-команда логируется с `stdout`, `stderr`, `return_code`.
