# Схема БД ЛР3 (RBAC)

Документ описывает только RBAC-таблицы ЛР3:
- `roles`
- `permissions`
- `role_user`
- `permission_role`

## `roles`

| Поле | Тип | NULL | Ограничения / назначение |
| --- | --- | --- | --- |
| `id` | `Integer` | Нет | PK, autoincrement |
| `name` | `String(128)` | Нет | `UNIQUE`, имя роли |
| `slug` | `String(128)` | Нет | `UNIQUE`, slug роли |
| `description` | `Text` | Да | описание роли |
| `created_at` | `DateTime(timezone=True)` | Нет | время создания |
| `created_by` | `Integer` | Нет | FK -> `users.id` |
| `updated_at` | `DateTime(timezone=True)` | Да | время обновления |
| `deleted_at` | `DateTime(timezone=True)` | Да | soft delete marker |
| `deleted_by` | `Integer` | Да | FK -> `users.id` |

## `permissions`

| Поле | Тип | NULL | Ограничения / назначение |
| --- | --- | --- | --- |
| `id` | `Integer` | Нет | PK, autoincrement |
| `name` | `String(128)` | Нет | `UNIQUE`, имя разрешения |
| `slug` | `String(128)` | Нет | `UNIQUE`, slug разрешения |
| `description` | `Text` | Да | описание разрешения |
| `created_at` | `DateTime(timezone=True)` | Нет | время создания |
| `created_by` | `Integer` | Нет | FK -> `users.id` |
| `updated_at` | `DateTime(timezone=True)` | Да | время обновления |
| `deleted_at` | `DateTime(timezone=True)` | Да | soft delete marker |
| `deleted_by` | `Integer` | Да | FK -> `users.id` |

## `role_user`

| Поле | Тип | NULL | Ограничения / назначение |
| --- | --- | --- | --- |
| `id` | `Integer` | Нет | PK, autoincrement |
| `user_id` | `Integer` | Нет | FK -> `users.id`, индекс |
| `role_id` | `Integer` | Нет | FK -> `roles.id`, индекс |
| `created_at` | `DateTime(timezone=True)` | Нет | время создания |
| `created_by` | `Integer` | Нет | FK -> `users.id`, индекс |
| `deleted_at` | `DateTime(timezone=True)` | Да | soft delete marker |
| `deleted_by` | `Integer` | Да | FK -> `users.id`, индекс |

Ограничения:
- `UNIQUE (user_id, role_id)` для защиты от дубликатов связи.

## `permission_role`

| Поле | Тип | NULL | Ограничения / назначение |
| --- | --- | --- | --- |
| `id` | `Integer` | Нет | PK, autoincrement |
| `role_id` | `Integer` | Нет | FK -> `roles.id`, индекс |
| `permission_id` | `Integer` | Нет | FK -> `permissions.id`, индекс |
| `created_at` | `DateTime(timezone=True)` | Нет | время создания |
| `created_by` | `Integer` | Нет | FK -> `users.id`, индекс |
| `deleted_at` | `DateTime(timezone=True)` | Да | soft delete marker |
| `deleted_by` | `Integer` | Да | FK -> `users.id`, индекс |

Ограничения:
- `UNIQUE (role_id, permission_id)` для защиты от дубликатов связи.

## Soft delete в ЛР3

Soft delete применяется ко всем 4 RBAC-таблицам:
- `roles`
- `permissions`
- `role_user`
- `permission_role`

Мягкое удаление:
- выставляет `deleted_at`, `deleted_by`.

Восстановление:
- очищает `deleted_at`, `deleted_by` (`NULL`).
