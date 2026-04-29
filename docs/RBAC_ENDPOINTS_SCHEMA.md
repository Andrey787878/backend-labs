# Схема работы endpoint-ов `/api/ref/*` (ЛР3: RBAC)

## 1) Общие правила

- Все маршруты ЛР3 имеют префикс `/api/ref`.
- Все маршруты требуют авторизованного пользователя (`Authorization: Bearer <access_token>`).
- Для каждого маршрута выполняется проверка permission по slug через роли пользователя.
- При отсутствии права возвращается строго:
  - `403`
  - `{"error": "Access denied. Required permission: <permission-slug>"}`
- Все ответы API возвращаются в JSON.

## 2) Карта endpoint-ов

### 2.1 Пользователи и роли пользователя

| Метод | Путь | Нужный permission | Request body | Успех |
| --- | --- | --- | --- | --- |
| `GET` | `/api/ref/user` | `get-list-user` | Нет | `200`, `list[UserDTO]` |
| `GET` | `/api/ref/user/{user_id}/role` | `read-user` | Нет | `200`, `RoleCollectionDTO` |
| `POST` | `/api/ref/user/{user_id}/role` | `update-user` | `AttachUserRoleRequest` | `200`, `RoleDTO` |
| `DELETE` | `/api/ref/user/{user_id}/role/{role_id}` | `delete-user` | Нет | `200`, `MessageResponseDTO` |
| `DELETE` | `/api/ref/user/{user_id}/role/{role_id}/soft` | `delete-user` | Нет | `200`, `MessageResponseDTO` |
| `POST` | `/api/ref/user/{user_id}/role/{role_id}/restore` | `restore-user` | Нет | `200`, `MessageResponseDTO` |

### 2.2 Роли

| Метод | Путь | Нужный permission | Request body | Успех |
| --- | --- | --- | --- | --- |
| `GET` | `/api/ref/policy/role` | `get-list-role` | Нет | `200`, `RoleCollectionDTO` |
| `GET` | `/api/ref/policy/role/{role_id}` | `read-role` | Нет | `200`, `RoleDTO` |
| `POST` | `/api/ref/policy/role` | `create-role` | `StoreRoleRequest` | `201`, `RoleDTO` |
| `PUT` | `/api/ref/policy/role/{role_id}` | `update-role` | `StoreRoleRequest` | `200`, `RoleDTO` |
| `PATCH` | `/api/ref/policy/role/{role_id}` | `update-role` | `UpdateRoleRequest` | `200`, `RoleDTO` |
| `DELETE` | `/api/ref/policy/role/{role_id}` | `delete-role` | Нет | `200`, `MessageResponseDTO` |
| `DELETE` | `/api/ref/policy/role/{role_id}/soft` | `delete-role` | Нет | `200`, `MessageResponseDTO` |
| `POST` | `/api/ref/policy/role/{role_id}/restore` | `restore-role` | Нет | `200`, `MessageResponseDTO` |

### 2.3 Разрешения

| Метод | Путь | Нужный permission | Request body | Успех |
| --- | --- | --- | --- | --- |
| `GET` | `/api/ref/policy/permission` | `get-list-permission` | Нет | `200`, `PermissionCollectionDTO` |
| `GET` | `/api/ref/policy/permission/{permission_id}` | `read-permission` | Нет | `200`, `PermissionDTO` |
| `POST` | `/api/ref/policy/permission` | `create-permission` | `StorePermissionRequest` | `201`, `PermissionDTO` |
| `PUT` | `/api/ref/policy/permission/{permission_id}` | `update-permission` | `StorePermissionRequest` | `200`, `PermissionDTO` |
| `PATCH` | `/api/ref/policy/permission/{permission_id}` | `update-permission` | `UpdatePermissionRequest` | `200`, `PermissionDTO` |
| `DELETE` | `/api/ref/policy/permission/{permission_id}` | `delete-permission` | Нет | `200`, `MessageResponseDTO` |
| `DELETE` | `/api/ref/policy/permission/{permission_id}/soft` | `delete-permission` | Нет | `200`, `MessageResponseDTO` |
| `POST` | `/api/ref/policy/permission/{permission_id}/restore` | `restore-permission` | Нет | `200`, `MessageResponseDTO` |

### 2.4 Связь роль-разрешение

| Метод | Путь | Нужный permission | Request body | Успех |
| --- | --- | --- | --- | --- |
| `GET` | `/api/ref/policy/role/{role_id}/permission` | `read-role` | Нет | `200`, `PermissionCollectionDTO` |
| `POST` | `/api/ref/policy/role/{role_id}/permission` | `update-role` | `AttachRolePermissionRequest` | `200`, `PermissionDTO` |
| `DELETE` | `/api/ref/policy/role/{role_id}/permission/{permission_id}` | `delete-role` | Нет | `200`, `MessageResponseDTO` |
| `DELETE` | `/api/ref/policy/role/{role_id}/permission/{permission_id}/soft` | `delete-role` | Нет | `200`, `MessageResponseDTO` |
| `POST` | `/api/ref/policy/role/{role_id}/permission/{permission_id}/restore` | `restore-role` | Нет | `200`, `MessageResponseDTO` |

## 3) Request-схемы и валидация

### `StoreRoleRequest`

- `name`: обязательное, не пустое.
- `slug`: обязательное, не пустое, шаблон `[A-Za-z0-9_-]+`.
- `description`: optional string.
- `extra="forbid"`.

### `UpdateRoleRequest`

- `name`: optional, если передан — не пустой.
- `slug`: optional, если передан — шаблон `[A-Za-z0-9_-]+`.
- `description`: optional.
- При явном `description: null` поле `description` очищается.
- Пустой payload запрещен.
- `extra="forbid"`.

### `StorePermissionRequest`

- `name`: обязательное, не пустое.
- `slug`: обязательное, не пустое, шаблон `[A-Za-z0-9_-]+`.
- `description`: optional string.
- `extra="forbid"`.

### `UpdatePermissionRequest`

- `name`: optional, если передан — не пустой.
- `slug`: optional, если передан — шаблон `[A-Za-z0-9_-]+`.
- `description`: optional.
- При явном `description: null` поле `description` очищается.
- Пустой payload запрещен.
- `extra="forbid"`.

### `AttachUserRoleRequest`

- `role_id`: обязательный, `>= 1`.
- `extra="forbid"`.

### `AttachRolePermissionRequest`

- `permission_id`: обязательный, `>= 1`.
- `extra="forbid"`.

## 4) Soft delete и restore

- Soft delete реализован полями `deleted_at` и `deleted_by`.
- Это относится к:
  - `roles`
  - `permissions`
  - `role_user`
  - `permission_role`
- При soft delete:
  - выставляются `deleted_at` и `deleted_by`.
- При restore:
  - `deleted_at` и `deleted_by` очищаются (`NULL`).
- Активные списки (`list_*`) по умолчанию возвращают только записи с `deleted_at IS NULL`.

## 5) Стратегия attach для soft-deleted связей

- Для `user-role` и `role-permission` используется единая стратегия:
  - если активная связь уже существует -> `422`;
  - если найдена мягко удаленная связь -> выполняется restore этой связи;
  - если связи нет -> создается новая.

## 6) created_by / deleted_by

- `created_by` для create/attach заполняется текущим авторизованным пользователем.
- `deleted_by` для soft delete заполняется текущим авторизованным пользователем.
- Для restore `deleted_by` очищается.

## 7) Основные коды и ошибки

- `200` — успешная операция.
- `201` — успешное создание роли/разрешения.
- `401` — отсутствует/невалиден access token.
- `403` — нет требуемого permission.
- `404` — сущность или связь не найдена.
- `422` — ошибка валидации или конфликт (например, дубликат name/slug).
- `503` — временная ошибка доступа/сохранения данных.

## 8) DTO ответов

- `UserDTO`: `id`, `username`, `email`, `birthday`, `roles`.
- `RoleDTO`: публичные поля роли без секретов.
- `RoleCollectionDTO`: `items`, `total`.
- `PermissionDTO`: публичные поля разрешения.
- `PermissionCollectionDTO`: `items`, `total`.
- `MessageResponseDTO`: сервисное сообщение о результате операции.

`password_hash` в ответах API не возвращается.
