# Проверка ЛР6 через Swagger

Откройте `http://localhost:8080/docs`.

## 1. Подготовка

1. Убедитесь, что в `.env` задан секрет ровно 36 символов:

```env
GIT_WEBHOOK_SECRET=00000000-0000-0000-0000-000000000000
GIT_DEFAULT_BRANCH=main
```

2. Запустите приложение:

```bash
docker compose up -d --build
```

3. Для безопасной демонстрации успешного `git pull` подготовьте demo Git-репозиторий внутри контейнера:

```bash
sh scripts/prepare_lr6_webhook_demo.sh
```

Скрипт создает локальный bare `origin` в `/tmp/lr6_demo_origin.git`, настраивает `/app` как Git worktree и добавляет demo-коммит, который webhook сможет подтянуть через `git pull origin main`.

Важно: настоящий репозиторий на host-машине не используется и не изменяется.

4. В Swagger найдите группу `git-webhook`.

## 2. Проверка 403

Вызовите `POST /hooks/git` с неверным секретом:

```json
{
  "secret_key": "wrong"
}
```

Ожидаемо: `403`, `Invalid secret key`.

## 3. Проверка 200 после demo-подготовки

Вызовите `POST /hooks/git` с корректным секретом:

```json
{
  "secret_key": "00000000-0000-0000-0000-000000000000"
}
```

После `sh scripts/prepare_lr6_webhook_demo.sh` ожидаемо: `200`.

В ответе должны быть команды:

- `git checkout main`;
- `git reset --hard HEAD`;
- `git pull origin main`.

Если перед deployment рабочая директория была грязной, в ответе дополнительно будет
непустой `warnings`. Список затронутых файлов смотрим в `deployment.log`.

В контейнере после успешного pull появится файл:

```text
/app/DEMO_WEBHOOK_MARKER.txt
```

## 4. Проверка 500 окружения

Если не запускать demo-подготовку и приложение работает в Docker-образе без `.git`, корректный секрет вернет `500` с сообщением, что текущая директория не является Git-репозиторием.

Это не падение приложения, а обработанный негативный сценарий неправильного deployment-окружения.

## 5. Проверка логов

После вызова проверьте файл:

```text
/app/deployment_logs/deployment.log
```

В логах должны быть:

- старт deployment;
- IP клиента;
- результат Git-команд или ошибка;
- финальный статус.

Секретный ключ в логах отсутствует.

## 6. Проверка dirty worktree warning

После demo-подготовки создайте локальное незакоммиченное изменение внутри контейнера:

```bash
docker compose exec api sh -lc "cd /app && printf dirty > LOCAL_DIRTY_FILE.txt"
```

Вызовите webhook с корректным секретом.

Ожидаемо:

- `200`;
- в JSON-ответе `warnings` содержит предупреждение про dirty worktree;
- `/app/LOCAL_DIRTY_FILE.txt` удален;
- в `deployment.log` есть события `dirty_worktree_detected` и `dirty_worktree_discarded`.

## 7. Проверка 409

Создайте lock-файл вручную внутри контейнера:

```bash
docker compose exec api sh -lc "mkdir -p /app/deployment_logs && printf test > /app/deployment_logs/deploy.lock"
```

Вызовите webhook с корректным секретом до истечения TTL.

Ожидаемо: `409`, `Deployment already in progress`.
