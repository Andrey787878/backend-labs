# Проверка ЛР4 через Swagger

Откройте `http://localhost:8080/docs`.

## 1. Подготовка

1. Примените миграции:

```bash
docker compose exec api python -m alembic -c /app/alembic.ini upgrade head
```

2. Войдите под пользователем с ролью `admin` и нажмите `Authorize`.

## 2. Проверка user lifecycle + audit

1. `GET /api/ref/user` -> выберите `user_id`.
2. `PATCH /api/ref/user/{user_id}` -> измените `email` или `birthday`.
3. `DELETE /api/ref/user/{user_id}/soft`.
4. `POST /api/ref/user/{user_id}/restore`.
5. `GET /api/ref/user/{user_id}/story` -> убедиться, что есть записи и `changed_fields` содержит только diff.

## 3. Проверка role lifecycle + audit

1. Создайте роль: `POST /api/ref/policy/role`.
2. Обновите роль: `PATCH /api/ref/policy/role/{role_id}`.
3. Мягко удалите: `DELETE /api/ref/policy/role/{role_id}/soft`.
4. Восстановите: `POST /api/ref/policy/role/{role_id}/restore`.
5. История: `GET /api/ref/policy/role/{role_id}/story`.

## 4. Проверка permission lifecycle + audit

1. Создайте разрешение: `POST /api/ref/policy/permission`.
2. Обновите разрешение: `PATCH /api/ref/policy/permission/{permission_id}`.
3. Мягко удалите: `DELETE /api/ref/policy/permission/{permission_id}/soft`.
4. Восстановите: `POST /api/ref/policy/permission/{permission_id}/restore`.
5. История: `GET /api/ref/policy/permission/{permission_id}/story`.

## 5. Проверка undo

1. Возьмите `log_id` из `story`.
2. Вызовите `POST /api/ref/changelog/{log_id}/restore`.
3. Повторно вызовите соответствующий `story` и проверьте новую запись восстановления.

## 6. Негативные проверки

1. Вызов любого `story` без нужного `get-story-*` права -> `403`.
2. `POST /api/ref/changelog/{log_id}/restore` без нужного `restore-*` -> `403`.
3. Невалидный `log_id` для restore -> `404`.

## 7. Что проверить отдельно

- В `changed_fields` нет `password_hash`.
- Мутации логируются только при успешной операции.
- Формат ответов JSON корректный.
