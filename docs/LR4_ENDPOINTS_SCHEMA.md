# Схема endpoint-ов ЛР4 (Audit Logging + Undo)

## 1) Общие правила

- Все маршруты ЛР4 имеют префикс `/api/ref`.
- Все маршруты требуют авторизацию (`Authorization: Bearer <access_token>`).
- Проверка прав выполняется через RBAC permission slug.
- Все ответы API возвращаются в JSON.
- `password_hash` не возвращается в API-ответах истории.

## 2) Новые permission (ЛР4)

- `get-story-user`
- `get-story-role`
- `get-story-permission`

Эти права назначаются роли `admin` миграцией сидов ЛР4.

## 3) Карта endpoint-ов ЛР4

### 3.1 История изменений

| Метод | Путь | Нужный permission | Успех |
| --- | --- | --- | --- |
| `GET` | `/api/ref/user/{user_id}/story` | `get-story-user` | `200`, `ChangeLogCollectionDTO` |
| `GET` | `/api/ref/policy/role/{role_id}/story` | `get-story-role` | `200`, `ChangeLogCollectionDTO` |
| `GET` | `/api/ref/policy/permission/{permission_id}/story` | `get-story-permission` | `200`, `ChangeLogCollectionDTO` |

### 3.2 Undo

| Метод | Путь | Нужный permission |
| --- | --- | --- |
| `POST` | `/api/ref/changelog/{log_id}/restore` | по типу сущности в логе: `restore-user` / `restore-role` / `restore-permission` |

Успех: `200`, `ChangeLogDTO` (новая запись восстановления).

## 4) Добавленные user-маршруты для полного lifecycle users

| Метод | Путь | Нужный permission | Успех |
| --- | --- | --- | --- |
| `GET` | `/api/ref/user/{user_id}` | `read-user` | `200`, `UserDTO` |
| `PATCH` | `/api/ref/user/{user_id}` | `update-user` | `200`, `UserDTO` |
| `DELETE` | `/api/ref/user/{user_id}/soft` | `delete-user` | `200`, `MessageResponseDTO` |
| `POST` | `/api/ref/user/{user_id}/restore` | `restore-user` | `200`, `MessageResponseDTO` |
| `DELETE` | `/api/ref/user/{user_id}` | `delete-user` | `200`, `MessageResponseDTO` |

## 5) Формат истории

`ChangeLogDTO`:

- `id`
- `entity_type`
- `entity_id`
- `changed_fields`: только различающиеся поля между `before` и `after`
- `created_at`
- `created_by`

## 6) Мутации, которые логируются автоматически

Для сущностей `users`, `roles`, `permissions`:

- create
- update
- soft delete (как update)
- restore (как update)
- hard delete

## 7) Транзакционность

- Audit-запись создается в той же транзакции, что и основная мутация.
- Если сохранение лога падает, основная мутация тоже откатывается.
