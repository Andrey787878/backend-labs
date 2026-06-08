# Схема endpoint-а ЛР6 (Git Webhook Deployment)

## 1) Общие правила

- ЛР6 вынесена в отдельную Swagger-группу `git-webhook`.
- Webhook открыт для внешнего Git-сервиса и не требует JWT/RBAC.
- Доступ защищается только `secret_key`, который сравнивается с `GIT_WEBHOOK_SECRET`.
- Секрет хранится в `.env` и не логируется.
- Перед обновлением проверяется dirty worktree. Локальные изменения не stash-ятся и не коммитятся:
  они логируются как warning, затем очищаются перед deployment.
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

Перед основными командами выполняется preflight:

```bash
git status --porcelain --untracked-files=all
```

Если рабочая директория грязная, webhook пишет warning в `deployment.log`, возвращает
warning в JSON-ответе и очищает локальные изменения:

```bash
git reset --hard HEAD
git clean -fd -e deployment_logs/
```

Ignored-файлы, например `.env`, не удаляются, потому что `git clean` запускается без `-x`,
а `deployment_logs/` явно исключается из очистки.

## 6) Response DTO

`DeploymentResponseDTO`:

- `message` - итог deployment.
- `branch` - обновляемая ветка.
- `warnings` - предупреждения для администратора, например dirty worktree.
- `commands` - результаты основных Git-команд `checkout`, `reset --hard`, `pull`.

## 7) Логи и lock

- Логи пишутся в `deployment_logs/deployment.log`.
- Lock пишется в `deployment_logs/deploy.lock`.
- Lock имеет TTL из `GIT_WEBHOOK_LOCK_TTL_SECONDS`.
- Основные и preflight Git-команды логируются с `stdout`, `stderr`, `return_code`.
- При dirty worktree логируются события `dirty_worktree_detected` и `dirty_worktree_discarded`.
