# RBAC Demo Script

Документ для быстрой демонстрации ЛР3 в Swagger.
Иди строго по шагам: терминал -> Swagger -> ожидаемые статусы.

## 1) Поднять проект

```bash
docker compose up -d --build
docker compose exec api python -m alembic -c /app/alembic.ini upgrade head
```

## 2) Чистый прогон

### Вариант A: сброс только данных (схема уже есть)

```bash
docker compose exec db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
TRUNCATE TABLE auth_sessions, permission_role, role_user, permissions, roles, users RESTART IDENTITY CASCADE;
"'
```

После этого `alembic upgrade head` запускать не нужно.

### Вариант B: полный сброс схемы и данных

```bash
docker compose exec db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
"'
docker compose exec api python -m alembic -c /app/alembic.ini upgrade head
```

### Если уже получили ошибку `relation "users" already exists`

```bash
docker compose exec api python -m alembic -c /app/alembic.ini stamp 20260409_0002
```

## 3) Открыть Swagger

- `http://localhost:8080/docs`

## 4) Создать пользователей (`POST /api/auth/register`)

### StudentA

```json
{
	"username": "StudentA",
	"email": "a@example.com",
	"password": "Password1!",
	"c_password": "Password1!",
	"birthday": "2000-01-01"
}
```

### StudentB

```json
{
	"username": "StudentB",
	"email": "b@example.com",
	"password": "Password1!",
	"c_password": "Password1!",
	"birthday": "2000-01-01"
}
```

### StudentC

```json
{
	"username": "StudentC",
	"email": "c@example.com",
	"password": "Password1!",
	"c_password": "Password1!",
	"birthday": "2000-01-01"
}
```

Ожидаемо: `201` для каждого пользователя.

## 5) Логин пользователей (`POST /api/auth/login`)

Сделай логин для:

- `StudentA`
- `StudentB`
- `StudentC`

Сохрани `access_token` каждого.

## 6) Bootstrap только первого администратора (терминал)

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

```bash
docker compose exec db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
SELECT id, username FROM users ORDER BY id;
SELECT id, slug FROM roles ORDER BY id;
SELECT user_id, role_id, deleted_at FROM role_user ORDER BY id;
"'
```

## 7) Authorize в Swagger

Нажми `Authorize` и вставь `access_token` пользователя `StudentA`.

## 8) Демонстрация под админом (`StudentA`)

### 8.1 Выдать роли `user` и `guest` через Swagger

1. `GET /api/ref/user` -> `200` (узнай `user_id` для `StudentB` и `StudentC`)
2. `GET /api/ref/policy/role` -> `200` (узнай `role_id` для `user` и `guest`)
3. `POST /api/ref/user/{studentB_id}/role` body:

```json
{
	"role_id": <role_id_user>
}
```

Ожидаемо: `200`.

4. `POST /api/ref/user/{studentC_id}/role` body:

```json
{
	"role_id": <role_id_guest>
}
```

Ожидаемо: `200`.

### 8.2 Общие RBAC endpoint-ы

1. `GET /api/ref/user` -> `200`
2. `GET /api/ref/policy/role` -> `200`

### 8.3 Role CRUD + soft/restore

1. `POST /api/ref/policy/role` body:

```json
{
	"name": "Manager",
	"slug": "manager",
	"description": "Manager role"
}
```

Ожидаемо: `201`.

2. `PATCH /api/ref/policy/role/{role_id}` body:

```json
{
	"description": null
}
```

Ожидаемо: `200`, `description` очищен.

3. `DELETE /api/ref/policy/role/{role_id}/soft` -> `200`
4. `POST /api/ref/policy/role/{role_id}/restore` -> `200`
5. `DELETE /api/ref/policy/role/{role_id}` -> `200`

### 8.4 User-Role связи

1. `GET /api/ref/user/{user_id}/role` -> `200`
2. `POST /api/ref/user/{user_id}/role` body:

```json
{
	"role_id": 3
}
```

Ожидаемо: `200`.

3. Повтори тот же `POST` -> `422` (дубликат активной связи).
4. `DELETE /api/ref/user/{user_id}/role/{role_id}/soft` -> `200`
5. `POST /api/ref/user/{user_id}/role/{role_id}/restore` -> `200`
6. `DELETE /api/ref/user/{user_id}/role/{role_id}` -> `200`

### 8.5 Permission CRUD + soft/restore

1. `GET /api/ref/policy/permission` -> `200`
2. `POST /api/ref/policy/permission` body:

```json
{
	"name": "Can export users",
	"slug": "export-user",
	"description": "Export users list"
}
```

Ожидаемо: `201`.

3. `DELETE /api/ref/policy/permission/{permission_id}/soft` -> `200`
4. `POST /api/ref/policy/permission/{permission_id}/restore` -> `200`
5. `DELETE /api/ref/policy/permission/{permission_id}` -> `200`

### 8.6 Role-Permission связи

1. `GET /api/ref/policy/role/{role_id}/permission` -> `200`
2. `POST /api/ref/policy/role/{role_id}/permission` body:

```json
{
	"permission_id": 1
}
```

Ожидаемо: `200`.

3. `DELETE /api/ref/policy/role/{role_id}/permission/{permission_id}/soft` -> `200`
4. `POST /api/ref/policy/role/{role_id}/permission/{permission_id}/restore` -> `200`
5. `DELETE /api/ref/policy/role/{role_id}/permission/{permission_id}` -> `200`

## 9) Негативные проверки

1. `401`:

- вызови любой `/api/ref/*` без `Authorize`.

2. `403`:

- авторизуйся как `StudentC`;
- вызови `POST /api/ref/policy/role`.
- ожидаемо:

```json
{
	"error": "Access denied. Required permission: create-role"
}
```

3. `422`:

- `POST /api/ref/policy/role` с невалидным slug:

```json
{
	"name": "Bad",
	"slug": "bad slug!",
	"description": "x"
}
```

4. `404`:

- запроси несуществующий `role_id` или `permission_id`.

## 10) Что проговорить в конце

1. `ЛР2 (auth) сохранена, RBAC добавлен поверх нее.`
2. `Права проверяются по permission slug через dependency.`
3. `Soft delete/restore работают и для сущностей, и для pivot-связей.`
4. `При отсутствии прав возвращается единый 403 формат с required permission.`
