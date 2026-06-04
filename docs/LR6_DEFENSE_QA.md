# ЛР6: короткие ответы для защиты

## Что реализовано?

Открытый Git webhook `POST /hooks/git`, который проверяет `secret_key`, ставит файловую блокировку, логирует процесс и выполняет Git-команды обновления проекта.

## Почему POST?

POST безопаснее GET, потому что секрет не попадает в URL, историю браузера и типовые access-логи.

## Где хранится секрет?

В `.env` через `GIT_WEBHOOK_SECRET`. В коде и логах секрет не хранится и не выводится.

## Какие команды выполняются?

```bash
git checkout <branch>
git reset --hard HEAD
git pull origin <branch>
```

Ветка берется из `GIT_DEFAULT_BRANCH`.

## Как защищена конкуренция?

Через файловый lock `deployment_logs/deploy.lock` с TTL. Если lock активен, API возвращает `409`.

## Где логирование?

В `deployment_logs/deployment.log`. Логируются старт, IP, каждая команда, stdout/stderr, return code, ошибки и завершение.

## Где находится код ЛР6?

- `app/git_webhook_routes.py` - HTTP endpoint.
- `app/deployment_service.py` - порядок deployment-операции.
- `app/git_command_runner.py` - выполнение Git-команд.
- `app/deployment_lock.py` - файловая блокировка.
- `app/deployment_logger.py` - структурированные логи.
