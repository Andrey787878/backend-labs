# Cхема БД

## `users`

| Поле            | Тип                           | NULL | Назначение                                              |
| --------------- | ----------------------------- | ---- | ------------------------------------------------------- |
| `id`            | `Integer` (PK, autoincrement) | Нет  | ID пользователя.                                        |
| `username`      | `String(64)`                  | Нет  | Логин пользователя.                                     |
| `email`         | `String(255)`                 | Нет  | Электронная почта пользователя.                         |
| `password_hash` | `String(255)`                 | Нет  | Хеш пароля (raw пароль не хранится).                    |
| `birthday`      | `Date`                        | Нет  | Дата рождения пользователя.                             |
| `created_at`    | `DateTime(timezone=True)`     | Нет  | Дата и время создания записи пользователя.              |
| `updated_at`    | `DateTime(timezone=True)`     | Нет  | Дата и время последнего обновления записи пользователя. |

## `auth_sessions`

| Поле                 | Тип                           | NULL | Назначение                                                      |
| -------------------- | ----------------------------- | ---- | --------------------------------------------------------------- |
| `id`                 | `Integer` (PK, autoincrement) | Нет  | ID сессии.                                                      |
| `user_id`            | `Integer` (FK -> `users.id`)  | Нет  | ID владельца сессии (ссылка на пользователя).                   |
| `family_id`          | `String(64)`                  | Нет  | ID семейства refresh-цепочки для одной логической сессии.       |
| `access_jti`         | `String(64)`                  | Нет  | Идентификатор access JWT для server-side проверки и отзыва.     |
| `refresh_hash`       | `String(255)`                 | Нет  | Хеш refresh token (raw refresh token не хранится).              |
| `created_at`         | `DateTime(timezone=True)`     | Нет  | Дата и время создания сессии.                                   |
| `last_used_at`       | `DateTime(timezone=True)`     | Да   | Дата и время последнего использования сессии.                   |
| `access_expires_at`  | `DateTime(timezone=True)`     | Нет  | Срок действия access token этой сессии.                         |
| `refresh_expires_at` | `DateTime(timezone=True)`     | Нет  | Срок действия refresh token этой сессии.                        |
| `refresh_used_at`    | `DateTime(timezone=True)`     | Да   | Время, когда refresh token уже был использован (одноразовость). |
| `revoked_at`         | `DateTime(timezone=True)`     | Да   | Время отзыва сессии.                                            |
| `revoked_reason`     | `String(255)`                 | Да   | Причина отзыва сессии.                                          |
| `ip`                 | `String(45)`                  | Да   | IP клиента при создании/обновлении сессии.                      |
| `user_agent`         | `String(512)`                 | Да   | User-Agent клиента при создании/обновлении сессии.              |
