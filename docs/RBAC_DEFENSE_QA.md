# Подготовка к защите ЛР3 (RBAC): вопросы и короткие ответы

Этот файл для устной защиты: что отвечать кратко и где это подтверждается в коде.

## 0. Что реализовано в ЛР3 (коротко)

- RBAC-модель: `roles`, `permissions`, `role_user`, `permission_role`.
- Soft delete для ролей, разрешений и pivot-связей.
- Обязательные `/api/ref/*` endpoint-ы.
- Проверка доступа по permission slug.
- Единый формат 403 при отсутствии права.

Код:
- Модели: `app/models.py`
- Сервис: `app/rbac_service.py`
- Зависимости/permission check: `app/dependencies.py`
- HTTP routes: `app/rbac_routes.py`

## 1. Почему не достаточно просто JWT для RBAC?

Коротко:
RBAC должен проверяться по актуальным данным БД (активные роли/разрешения/связи), а не только по токену.

Как сделано:
- `require_permission(...)` делает SQL-проверку связей `user -> role -> permission`.
- Учитываются только активные записи (`deleted_at IS NULL`).

Код: `app/dependencies.py:234-267`.

## 2. Где хранится политика доступа?

- `roles` — роли;
- `permissions` — разрешения;
- `role_user` — назначение ролей пользователям;
- `permission_role` — назначение разрешений ролям.

Код: `app/models.py:90-295`.

## 3. Как работает проверка прав на endpoint?

1. Пользователь аутентифицируется через access token.
2. Для endpoint вызывается `Depends(require_permission("<slug>"))`.
3. Если права нет -> бросается `PermissionDeniedError`.
4. Глобальный handler возвращает `403` в строгом JSON-формате.

Код:
- Проверка slug: `app/dependencies.py:234-267`
- Handler 403: `app/main.py:30-38`
- Привязка permission к route: `app/rbac_routes.py`.

## 4. Какой формат 403 обязателен?

Строго:

```json
{
  "error": "Access denied. Required permission: <permission-slug>"
}
```

Где обеспечивается:
- `PermissionDeniedError` содержит slug.
- Глобальный handler собирает JSON ровно с ключом `error`.

Код: `app/dependencies.py:33-39`, `app/main.py:35-38`.

## 5. Что такое soft delete и где он реализован?

Soft delete = запись не удаляется физически, а помечается:
- `deleted_at`
- `deleted_by`

Применяется к:
- `roles`, `permissions`, `role_user`, `permission_role`.

Код:
- Поля в моделях: `app/models.py`.
- Сервисные операции `soft_delete_*` и `restore_*`: `app/rbac_service.py`.

## 6. Чем soft delete отличается от hard delete в API?

- `DELETE .../soft`: заполняет `deleted_at`, `deleted_by`.
- `POST .../restore`: очищает `deleted_at`, `deleted_by`.
- `DELETE` без `/soft`: физически удаляет запись.

Код:
- Routes: `app/rbac_routes.py`.
- Логика: `app/rbac_service.py`.

## 7. Как решена проблема many-to-many при soft delete?

Коротко:
Не используется «голый secondary only». Сделаны отдельные ORM-модели `UserRole` и `PermissionRole`.

Зачем:
Чтобы хранить `created_by`, `deleted_at`, `deleted_by` на связях.

Код: `app/models.py:204-295`.

## 8. Как исключены soft-deleted связи из активных списков?

- В ORM relationships и в SQL-запросах добавлен фильтр `deleted_at IS NULL`.

Примеры:
- `User.roles`: только активные связи и активные роли.
- `Role.permissions`: только активные связи и активные permissions.

Код:
- Relationships: `app/models.py:46-58`, `app/models.py:140-152`, `app/models.py:189-201`.
- List-методы сервиса: `app/rbac_service.py`.

## 9. Как проверяется уникальность name/slug?

- На create: проверка существования `name`/`slug` + DB unique.
- На update: проверка с исключением текущей записи (`id != current_id`).

Код:
- role checks: `app/rbac_service.py:200-203`, `app/rbac_service.py:225-228`, `app/rbac_service.py:660-670`.
- permission checks: `app/rbac_service.py:331-334`, `app/rbac_service.py:363-366`, `app/rbac_service.py:672-682`.

## 10. Что происходит при attach, если связь уже была soft-deleted?

Стратегия: restore существующей связи.

Поведение:
- активная связь уже есть -> `422`;
- есть soft-deleted -> restore;
- нет связи -> create.

Код:
- user-role attach: `app/rbac_service.py:112-144`.
- role-permission attach: `app/rbac_service.py:474-513`.

## 11. Как заполняются created_by / deleted_by?

- create/attach: `created_by = current_user.id`.
- soft delete: `deleted_by = current_user.id`.
- restore: `deleted_by = NULL`, `deleted_at = NULL`.

Код: `app/rbac_service.py`.

## 12. Почему password_hash не утекает наружу?

Потому что response-модели используют `UserDTO`, где нет `password_hash`.

Код:
- `UserDTO`: `app/dto.py:143-153`.
- Маппинг в DTO: `app/rbac_service.py:696-704`, `app/auth_service.py`.

## 13. Какие обязательные endpoint-ы ЛР3 реализованы?

- `/api/ref/user*` (list users, user-role attach/delete/soft/restore)
- `/api/ref/policy/role*` (CRUD + soft/restore)
- `/api/ref/policy/permission*` (CRUD + soft/restore)
- `/api/ref/policy/role/{role_id}/permission*` (attach/delete/soft/restore + list)

Код: `app/rbac_routes.py`.

## 14. Что с миграциями и запуском?

- Схема БД управляется Alembic.
- `create_all` при старте приложения убран.
- Для Docker Compose миграции запускаются так:
  `docker compose exec api python -m alembic -c /app/alembic.ini upgrade head`.
- Цепочка миграций:
  - `20260409_0000` — auth tables
  - `20260409_0001` — RBAC tables
  - `20260409_0002` — RBAC base seed

Код:
- `app/main.py:13-16`
- `alembic/versions/*.py`

## 15. Частый вопрос: почему без сидинга role_user нельзя сразу пользоваться /api/ref?

Потому что все `/api/ref/*` требуют permission, а permissions приходят через роли пользователя.
Если у пользователя нет роли, доступ будет `403`.

Это штатно решается bootstrap-назначением первого admin в БД.

## 16. Какие коды ответов используются в RBAC-слое?

- `200` — успешные операции.
- `201` — создание role/permission.
- `401` — нет/битый access token.
- `403` — нет permission.
- `404` — не найдена сущность/связь.
- `422` — валидация/конфликт.
- `503` — временная ошибка БД.

Код:
- `app/rbac_routes.py` (маппинг ошибок).
- `app/dependencies.py` и `app/main.py` (401/403).

## 17. Какие ограничения/нюансы можно честно проговорить на защите?

- Для первого администратора нужен bootstrap `role_user` (ручной или отдельный init-шаг).
- PATCH поддерживает явный `description: null` и корректно очищает поле `description`.

Главное:
- обязательное ТЗ закрыто;
- auth-часть ЛР2 не сломана;
- RBAC-права проверяются централизованно и единообразно.
