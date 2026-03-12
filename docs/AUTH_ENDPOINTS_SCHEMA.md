# Схема работы endpoint-ов `/api/auth/*`

## 1) Общие правила

- Все ответы и ошибки от API приходят в JSON.
- Префикс всех маршрутов: `/api/auth`.
- `register` доступен только гостю (если валидная активная авторизация уже есть -> `403`).
- `me`, `out`, `tokens`, `out_all`, `change-password` требуют `Authorization: Bearer <access_token>`.
- `login` и `refresh` ограничены rate-limit по IP (in-memory, per-process):
  - `login`: по умолчанию `5` запросов за `60` секунд.
  - `refresh`: по умолчанию `10` запросов за `60` секунд.
  - При превышении: `429` + `Retry-After`.

## 2) Карта endpoint-ов

| Метод  | Путь               | Нужен access token | Request body            | Успех                         |
| ------ | ------------------ | ------------------ | ----------------------- | ----------------------------- |
| `POST` | `/register`        | Нет (guest-only)   | `RegisterRequest`       | `201`, `UserDTO`              |
| `POST` | `/login`           | Нет                | `LoginRequest`          | `200`, `AuthSuccessDTO`       |
| `GET`  | `/me`              | Да                 | Нет                     | `200`, `UserDTO`              |
| `POST` | `/out`             | Да                 | Нет                     | `200`, `MessageResponseDTO`   |
| `GET`  | `/tokens`          | Да                 | Нет                     | `200`, `TokenListDTO`         |
| `POST` | `/out_all`         | Да                 | Нет                     | `200`, `LogoutAllResponseDTO` |
| `POST` | `/refresh`         | Нет                | `RefreshRequest`        | `200`, `AuthSuccessDTO`       |
| `POST` | `/change-password` | Да                 | `ChangePasswordRequest` | `200`, `MessageResponseDTO`   |

## 3) Валидация входных данных

### `RegisterRequest`

- `username`: только латиница, первая буква заглавная, длина >= 7.
- `email`: валидный email.
- `password`: минимум 8, минимум 1 цифра, 1 lowercase, 1 uppercase, 1 спецсимвол.
- `c_password`: совпадает с `password`.
- `birthday`: формат `YYYY-MM-DD`, возраст >= 14.

### `LoginRequest`

- `username`: только латиница, первая буква заглавная, длина >= 7.
- `password`: минимум 8, минимум 1 цифра, 1 lowercase, 1 uppercase, 1 спецсимвол.

### `RefreshRequest`

- `refresh_token`: не пустой после `strip()`.

### `ChangePasswordRequest`

- `current_password`: обязателен.
- `new_password`: те же правила сложности, что на регистрации.
- `c_password`: совпадает с `new_password`.

## 4) Логика каждого endpoint

### `POST /register`

1. Проверяется guest-only доступ.
2. Валидируется `RegisterRequest`.
3. Сервис проверяет уникальность `username/email` (case-insensitive).
4. Сохраняет пользователя (`password_hash`, не raw пароль).
5. Возвращает `UserDTO`.

Типовые ошибки: `409` (дубликат), `422` (невалидные поля), `503` (ошибка БД).

### `POST /login`

1. Применяется rate-limit по IP.
2. Валидируется `LoginRequest`.
3. Сервис проверяет `username/password`.
4. Создает server-side сессию в `auth_sessions`, выдает `access_token + refresh_token`.
5. Валидирует и сохраняет метаданные клиента:
   - `ip`: должен быть корректным IPv4/IPv6.
   - `user-agent`: <= 512 символов, без CR/LF/NUL и script-паттернов.
6. Применяется лимит активных сессий пользователя (старые отзываются при переполнении).

Типовые ошибки: `401` (неверные учетные данные), `422` (невалидные поля/IP/User-Agent), `429`, `503`.

### `GET /me`

1. Проверяется Bearer access token (формат, header, подпись, срок).
2. Проверяется server-side сессия по `access_jti`.
3. Возвращается текущий пользователь.

Типовые ошибки: `401` (нет/битый токен, сессия не найдена), `403` (сессия отозвана/истекла), `503`.

### `POST /out`

1. Проверяется текущий авторизованный контекст.
2. Отзывается текущая сессия по `access_jti`.
3. Идемпотентный ответ:
   - `"Текущая сессия отозвана."` или
   - `"Сессия уже была неактивна."`.

Типовые ошибки: `401/403/503`.

### `GET /tokens`

1. Проверяется текущий авторизованный контекст.
2. Возвращаются активные сессии пользователя (`TokenListDTO`) без секретов токенов.

Типовые ошибки: `401/403/503`.

### `POST /out_all`

1. Проверяется текущий авторизованный контекст.
2. Отзываются все активные сессии пользователя.
3. Возвращается `revoked_count`.

Типовые ошибки: `401/403/503`.

### `POST /refresh`

1. Применяется rate-limit по IP.
2. Валидируется `RefreshRequest`.
3. Сервис находит сессию по `refresh_hash` (raw refresh в БД не хранится).
4. Делает refresh-rotation:
   - старый refresh одноразово помечается использованным;
   - старая сессия отзывается;
   - создается новая сессия и новая пара токенов.
5. При повторном/просроченном/скомпрометированном refresh:
   - отзываются все сессии пользователя,
   - возвращается ошибка.

Типовые ошибки: `401`, `403` (компрометация), `422` (пустой refresh), `429`, `503`.

### `POST /change-password`

1. Проверяется текущий авторизованный контекст.
2. Валидируется `ChangePasswordRequest`.
3. Сервис проверяет `current_password`.
4. Обновляет `password_hash`.
5. Отзывает все активные сессии пользователя.
6. Возвращает сервисное сообщение об успехе.

Типовые ошибки: `401` (текущий пароль неверен), `422` (невалидные поля), `503`.

## 5) Форматы основных ответов

- `UserDTO`: `id`, `username`, `email`, `birthday`.
- `AuthSuccessDTO`: `access_token`, `refresh_token`, `user`.
- `TokenListDTO`: `items[]` с метаданными сессий (`id`, сроки, `ip`, `user_agent`, `revoked_*`).
- `MessageResponseDTO`: `message`.
- `LogoutAllResponseDTO`: `message`, `revoked_count`.

## 6) Общая карта ошибок

- `401 Unauthorized`: нет/битый access token, неверные креды, невалидный refresh.
- `403 Forbidden`: endpoint только для гостя, сессия отозвана/истекла, компрометация refresh.
- `409 Conflict`: дубли `username/email` при регистрации.
- `422 Unprocessable Content`: ошибки валидации request-полей и доменные `ValueError`.
- `429 Too Many Requests`: превышен rate-limit на `login/refresh`.
- `503 Service Unavailable`: временная ошибка доступа/сохранения в БД.
