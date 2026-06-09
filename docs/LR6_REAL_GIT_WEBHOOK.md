# ЛР6: запуск webhook с реальным Git-репозиторием

Этот режим нужен, если на сдаче требуется показать не локальный demo-origin, а работу webhook-а с настоящим `origin` текущего репозитория.

## Важно перед запуском

Webhook выполняет команды:

```bash
git checkout <GIT_DEFAULT_BRANCH>
git reset --hard HEAD
git pull origin <GIT_DEFAULT_BRANCH>
```

Перед основными командами webhook проверяет dirty worktree через
`git status --porcelain --untracked-files=all`. Если есть локальные незакоммиченные
изменения, сервис пишет warning в `deployment.log`, возвращает warning в JSON-ответе,
очищает изменения через `git reset --hard HEAD` и `git clean -fd -e deployment_logs/`,
затем продолжает deployment.

Это сделано специально для production-сценария: локальные изменения на сервере не
stash-ятся и не commit-ятся, потому что они могут быть случайными или подозрительными.
Ignored-файлы, например `.env`, не удаляются, потому что `git clean` запускается без `-x`,
а `deployment_logs/` явно исключается из очистки.

## 1. Настроить ветку

В `.env` укажите ветку, которую должен подтягивать webhook:

```env
GIT_DEFAULT_BRANCH=lb6
```

Если демонстрируете обновление из `main`, укажите:

```env
GIT_DEFAULT_BRANCH=main
```

## 2. Запустить контейнер с реальным `.git`

Обычный `docker-compose.yml` собирает image без `.git`. Для реального webhook-а используйте дополнительный compose-файл:

```bash
docker compose -f docker-compose.yml -f docker-compose.real-git.yml up -d --build
```

Он примонтирует текущую папку в контейнер:

```text
.:/app
```

Значит внутри контейнера будет настоящий `.git` текущего проекта.

## 3. Проверить репозиторий внутри контейнера

```bash
docker compose -f docker-compose.yml -f docker-compose.real-git.yml exec api git -C /app status
docker compose -f docker-compose.yml -f docker-compose.real-git.yml exec api git -C /app branch
docker compose -f docker-compose.yml -f docker-compose.real-git.yml exec api git -C /app remote -v
```

В `remote -v` должен быть реальный `origin`, например GitHub.

## 4. Доступ к GitHub

Если репозиторий публичный, `git pull origin <branch>` обычно работает без токена.

Если репозиторий приватный, контейнеру нужен доступ к GitHub:

- HTTPS remote с токеном;
- SSH remote и примонтированный SSH-ключ;
- GitHub deploy key.

Не коммитьте токены и ключи в проект. Секреты должны храниться только локально или на сервере.

## 5. Выполнить миграции

```bash
docker compose -f docker-compose.yml -f docker-compose.real-git.yml exec api python -m alembic upgrade head
```

## 6. Проверить webhook в Swagger

Откройте:

```text
http://localhost:8080/docs
```

Группа:

```text
git-webhook
```

Endpoint:

```text
POST /hooks/git
```

Body:

```json
{
  "secret_key": "00000000-0000-0000-0000-000000000000"
}
```

Ожидаемо при корректном `origin` и доступе к Git:

```text
200 OK
```

В ответе будут результаты основных команд `checkout`, `reset --hard`, `pull`.
Если перед deployment были локальные изменения, поле `warnings` будет непустым.

## 7. Проверить логи

```bash
docker compose -f docker-compose.yml -f docker-compose.real-git.yml exec api tail -20 /app/deployment_logs/deployment.log
```

В логах должны быть:

- `deployment_start`;
- `git_preflight_command`;
- `git_command`;
- `dirty_worktree_detected` / `dirty_worktree_discarded`, если были локальные изменения;
- `deployment_finish`;
- статус `success`.

Секретный ключ в логах не выводится.

## Что говорить на сдаче

В обычном Docker image `.git` не копируется, потому что это нормальная практика сборки. Для демонстрации реального `git pull` используется отдельный compose-файл `docker-compose.real-git.yml`, который явно примонтирует рабочий репозиторий в контейнер.

Так webhook работает с настоящим `origin`, но этот режим нужно запускать осознанно:
локальные незакоммиченные изменения в примонтированной папке будут залогированы и удалены.
