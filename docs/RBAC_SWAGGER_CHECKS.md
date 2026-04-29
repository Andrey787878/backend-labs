# Проверка RBAC API через Swagger (ЛР3)

Откройте `http://localhost:8080/docs`.

## 1. Подготовка перед проверкой

1. Примените миграции:

Для Docker Compose:

```bash
docker compose exec api python -m alembic -c /app/alembic.ini upgrade head
```

Для локального запуска:

```bash
alembic upgrade head
```

2. Зарегистрируйте пользователя и выполните `POST /api/auth/login`, получите `access_token`.
3. В Swagger нажмите `Authorize` и вставьте `access_token`.

Важно: все `/api/ref/*` требуют и авторизацию, и permission.

## 2. Bootstrap первого администратора

Так как user-role сидинг не делается, первому пользователю нужно назначить роль `admin` вручную в БД.

Пример для Docker:

```bash
docker compose exec db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
INSERT INTO role_user (user_id, role_id, created_by)
SELECT u.id, r.id, u.id
FROM users u
JOIN roles r ON r.slug = '\''admin'\''
WHERE u.username = '\''StudentA'\''
ON CONFLICT (user_id, role_id) DO NOTHING;
"'
```

После этого снова войдите под `StudentA` и обновите `Authorize` новым `access_token`.

## 3. Ожидаемые permission-slug по группам

- Пользователи:
  - `get-list-user`, `read-user`, `update-user`, `delete-user`, `restore-user`
- Роли:
  - `get-list-role`, `read-role`, `create-role`, `update-role`, `delete-role`, `restore-role`
- Разрешения:
  - `get-list-permission`, `read-permission`, `create-permission`, `update-permission`, `delete-permission`, `restore-permission`

При отсутствии права ожидается строго:

```json
{
  "error": "Access denied. Required permission: <permission-slug>"
}
```

## 4. Чек-лист проверок endpoint-ов

## 4.1 Пользователи и роли пользователя

1. `GET /api/ref/user` -> `200`.
2. `GET /api/ref/user/{user_id}/role` -> `200`.
3. `POST /api/ref/user/{user_id}/role` с body:

```json
{
  "role_id": 2
}
```

Ожидаемо: `200`.

4. `DELETE /api/ref/user/{user_id}/role/{role_id}/soft` -> `200`.
5. `POST /api/ref/user/{user_id}/role/{role_id}/restore` -> `200`.
6. `DELETE /api/ref/user/{user_id}/role/{role_id}` -> `200`.

## 4.2 Роли

1. `GET /api/ref/policy/role` -> `200`.
2. `POST /api/ref/policy/role`:

```json
{
  "name": "Manager",
  "slug": "manager",
  "description": "Manager role"
}
```

Ожидаемо: `201`.

3. `GET /api/ref/policy/role/{role_id}` -> `200`.
4. `PUT /api/ref/policy/role/{role_id}` -> `200`.
5. `PATCH /api/ref/policy/role/{role_id}` -> `200`.
6. `DELETE /api/ref/policy/role/{role_id}/soft` -> `200`.
7. `POST /api/ref/policy/role/{role_id}/restore` -> `200`.
8. `DELETE /api/ref/policy/role/{role_id}` -> `200`.

## 4.3 Разрешения

1. `GET /api/ref/policy/permission` -> `200`.
2. `POST /api/ref/policy/permission`:

```json
{
  "name": "Can export users",
  "slug": "export-user",
  "description": "Export users list"
}
```

Ожидаемо: `201`.

3. `GET /api/ref/policy/permission/{permission_id}` -> `200`.
4. `PUT /api/ref/policy/permission/{permission_id}` -> `200`.
5. `PATCH /api/ref/policy/permission/{permission_id}` -> `200`.
6. `DELETE /api/ref/policy/permission/{permission_id}/soft` -> `200`.
7. `POST /api/ref/policy/permission/{permission_id}/restore` -> `200`.
8. `DELETE /api/ref/policy/permission/{permission_id}` -> `200`.

## 4.4 Связь роль-разрешение

1. `GET /api/ref/policy/role/{role_id}/permission` -> `200`.
2. `POST /api/ref/policy/role/{role_id}/permission`:

```json
{
  "permission_id": 1
}
```

Ожидаемо: `200`.

3. `DELETE /api/ref/policy/role/{role_id}/permission/{permission_id}/soft` -> `200`.
4. `POST /api/ref/policy/role/{role_id}/permission/{permission_id}/restore` -> `200`.
5. `DELETE /api/ref/policy/role/{role_id}/permission/{permission_id}` -> `200`.

## 5. Негативные проверки

## 5.1 Проверка 401

Вызвать любой `/api/ref/*` без `Authorize` -> `401`.

## 5.2 Проверка 403 (нет права)

1. Назначьте тестовому пользователю роль `guest`.
2. Войдите под ним и вызовите, например, `POST /api/ref/policy/role`.
3. Ожидаемо:

```json
{
  "error": "Access denied. Required permission: create-role"
}
```

## 5.3 Проверка 422 валидации

`POST /api/ref/policy/role` с пустым `name` или невалидным `slug` (например, `"bad slug!"`) -> `422`.

Дополнительно для PATCH:

`PATCH /api/ref/policy/role/{role_id}` с body

```json
{
  "description": null
}
```

Ожидаемо: `200`, поле `description` очищается.

## 5.4 Проверка 404

Запросить несуществующий `role_id` или `permission_id` -> `404`.

## 6. Что проверить отдельно перед защитой

- На ответах нет `password_hash`.
- `soft` операции не удаляют данные физически.
- `restore` очищает `deleted_at` и `deleted_by`.
- `hard` операции реально удаляют связь/сущность.
- Ошибка доступа всегда в одном формате `{"error": ...}`.

## 7. Готовый Текст Для Защиты (Озвучка По Шагам)

1. Вступление:
`Сейчас покажу ЛР3 RBAC: роли, разрешения, связи и проверку доступа по permission-slug.`

2. Миграции:
`Сначала применяю миграции, чтобы схема БД была актуальна.`
Показываю команду из раздела 1.

3. Логин:
`Логинюсь под пользователем, который имеет роль admin, и вставляю access token в Authorize.`

4. Список ролей:
`Проверяю чтение справочника ролей: GET /api/ref/policy/role, ожидаю 200.`

5. Создание роли:
`Создаю новую роль POST /api/ref/policy/role, ожидаю 201. created_by заполняется автоматически текущим пользователем.`

6. PATCH с null:
`Показываю PATCH с description: null. Это очищает описание, ожидаю 200.`

7. Soft delete / restore роли:
`Показываю мягкое удаление роли и восстановление: DELETE .../soft, потом POST .../restore.`
`После restore deleted_at и deleted_by очищаются.`

8. Пользователи и роли пользователя:
`Показываю назначение роли пользователю, затем soft delete связи и restore связи через /api/ref/user/{user_id}/role...`

9. Роль и разрешения:
`Показываю назначение разрешения роли, затем soft delete связи и restore через /api/ref/policy/role/{role_id}/permission...`

10. Проверка отказа доступа:
`Теперь вхожу под пользователем без нужного права и вызываю POST /api/ref/policy/role.`
`Ожидаю 403 и единый JSON: {"error":"Access denied. Required permission: create-role"}.`

11. Проверка валидации:
`Показываю 422: невалидный slug, например "bad slug!".`

12. Финал:
`RBAC работает поверх ЛР2: auth не сломана, права проверяются централизованно, soft delete/restore реализованы для сущностей и связей.`

## 8. Полный E2E Сценарий Для Демонстрации (Команды + Swagger)

### 8.1 Подготовка окружения (терминал)

```bash
docker compose up -d --build
docker compose exec api python -m alembic -c /app/alembic.ini upgrade head
```

Опционально, для полностью чистого прогона:

Вариант A (сброс только данных, схема уже есть):

```bash
docker compose exec db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
TRUNCATE TABLE auth_sessions, permission_role, role_user, permissions, roles, users RESTART IDENTITY CASCADE;
"'
```

Вариант B (полный сброс схемы и данных):

```bash
docker compose exec db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
"'
docker compose exec api python -m alembic -c /app/alembic.ini upgrade head
```

Если уже получили ошибку `relation "users" already exists`:

```bash
docker compose exec api python -m alembic -c /app/alembic.ini stamp 20260409_0002
```

### 8.2 Создание пользователей (Swagger)

Создайте 3 пользователей через `POST /api/auth/register`:

1. `StudentA` (будущий админ)
2. `StudentB` (обычный пользователь)
3. `StudentC` (гость)

Пример body:

```json
{
  "username": "StudentA",
  "email": "a@example.com",
  "password": "Password1!",
  "c_password": "Password1!",
  "birthday": "2000-01-01"
}
```

Ожидаемо: `201`.

### 8.3 Логин пользователей (Swagger)

Через `POST /api/auth/login` получите `access_token` для:

1. `StudentA`
2. `StudentB`
3. `StudentC`

### 8.4 Bootstrap ролей пользователям (терминал)

Назначьте роли вручную в `role_user`:

```bash
docker compose exec db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
INSERT INTO role_user (user_id, role_id, created_by)
SELECT u.id, r.id, a.id
FROM users u
JOIN roles r ON (
  (u.username = '\''StudentA'\'' AND r.slug = '\''admin'\'') OR
  (u.username = '\''StudentB'\'' AND r.slug = '\''user'\'') OR
  (u.username = '\''StudentC'\'' AND r.slug = '\''guest'\'')
)
JOIN users a ON a.username = '\''StudentA'\''
ON CONFLICT (user_id, role_id) DO NOTHING;
"'
```

Проверка:

```bash
docker compose exec db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
SELECT u.username, r.slug AS role_slug, ru.deleted_at
FROM role_user ru
JOIN users u ON u.id = ru.user_id
JOIN roles r ON r.id = ru.role_id
ORDER BY u.username, r.slug;
"'
```

### 8.5 Демонстрация под админом в Swagger (`StudentA`)

1. Нажмите `Authorize`, вставьте `StudentA access_token`.
2. `GET /api/ref/user` -> `200`.
3. `GET /api/ref/policy/role` -> `200`.
4. `POST /api/ref/policy/role` (создайте `manager`) -> `201`.
5. `PATCH /api/ref/policy/role/{role_id}` с:

```json
{
  "description": null
}
```

Ожидаемо: `200`, описание очищено.

6. `DELETE /api/ref/policy/role/{role_id}/soft` -> `200`.
7. `POST /api/ref/policy/role/{role_id}/restore` -> `200`.
8. `DELETE /api/ref/policy/role/{role_id}` -> `200`.

### 8.6 Демонстрация user-role связей

1. `GET /api/ref/user/{user_id}/role` -> `200`.
2. `POST /api/ref/user/{user_id}/role` с `{"role_id": <id роли>}` -> `200`.
3. Повторить тот же `POST` -> `422` (дубликат активной связи).
4. `DELETE /api/ref/user/{user_id}/role/{role_id}/soft` -> `200`.
5. `POST /api/ref/user/{user_id}/role/{role_id}/restore` -> `200`.
6. `DELETE /api/ref/user/{user_id}/role/{role_id}` -> `200`.

### 8.7 Демонстрация permissions и role-permission связей

1. `GET /api/ref/policy/permission` -> `200`.
2. `POST /api/ref/policy/permission` -> `201`.
3. `DELETE /api/ref/policy/permission/{permission_id}/soft` -> `200`.
4. `POST /api/ref/policy/permission/{permission_id}/restore` -> `200`.
5. `DELETE /api/ref/policy/permission/{permission_id}` -> `200`.

Для связи роль-разрешение:

1. `GET /api/ref/policy/role/{role_id}/permission` -> `200`.
2. `POST /api/ref/policy/role/{role_id}/permission` -> `200`.
3. `DELETE /api/ref/policy/role/{role_id}/permission/{permission_id}/soft` -> `200`.
4. `POST /api/ref/policy/role/{role_id}/permission/{permission_id}/restore` -> `200`.
5. `DELETE /api/ref/policy/role/{role_id}/permission/{permission_id}` -> `200`.

### 8.8 Негативные проверки в Swagger

1. `401`: вызовите любой `/api/ref/*` без `Authorize`.
2. `403`: авторизуйтесь как `StudentC` и вызовите `POST /api/ref/policy/role`.
Ожидаемо:

```json
{
  "error": "Access denied. Required permission: create-role"
}
```

3. `422`: `POST /api/ref/policy/role` с `slug = "bad slug!"`.
4. `404`: запросите несуществующий `role_id` или `permission_id`.
