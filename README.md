# Лабораторная работа №2: Авторизация (FastAPI + PostgreSQL)

## 1. Проект реализует

- регистрацию пользователя;
- вход по `username/password`;
- выдачу `access token` и `refresh token`;
- server-side хранение состояния сессий;
- in-memory rate-limit для `/login` и `/refresh`;
- refresh rotation и reuse detection;
- отзыв текущей сессии и всех сессий;
- смену пароля с отзывом всех сессий.

## 2. Что важно понимать

- `access token` — это JWT, короткоживущий.
- `refresh token` — это непрозрачная случайная строка (не JWT), одноразовая.
- В БД **не хранятся raw-токены**.
- В БД хранятся: `access_jti`, `refresh_hash` и метаданные сессии.
- Проверка доступа к защищенным маршрутам идет не только по JWT, но и по server-side состоянию сессии в БД.

## 2.1 Документация в `docs/`

- `docs/DB_SCHEMA.md` — поля таблиц `users` и `auth_sessions`.
- `docs/AUTH_ENDPOINTS_SCHEMA.md` — схема работы всех endpoint-ов `/api/auth/*`.

## 3. Архитектура `app/`

### 3.1 Дерево `app/`

```text
app/
  main.py          # создание FastAPI-приложения, lifespan, подключение роутов
  db.py            # engine, Base, SessionLocal, get_db
  config.py        # Settings из .env + валидация конфигурации
  models.py        # ORM-модели User и AuthSession
  schemas.py       # входные request-схемы (валидация JSON)
  dto.py           # внутренние и выходные DTO (типизированные объекты)
  rate_limiter.py  # in-memory лимитер запросов
  token_service.py # JWT/access и refresh-хеширование (криптография)
  auth_service.py  # бизнес-логика авторизации и сессий
  dependencies.py  # FastAPI dependencies (auth/guest/db/service context)
  auth_routes.py   # HTTP endpoints /api/auth/*
```

### 3.2 Принцип слоев

- `auth_routes.py` — только HTTP-слой: принимает запрос, вызывает сервис, возвращает ответ.
- `schemas.py` и `dto.py` — валидация и типизированный обмен данными между слоями.
- `auth_service.py` — бизнес-логика, транзакции, управление сессиями.
- `token_service.py` — криптография токенов (JWT access, генерация/хеширование refresh).
- `dependencies.py` — проверка авторизации и сборка контекста текущего пользователя.

### 3.3 Как модули связаны между собой

```text
HTTP Request
  -> auth_routes.py
  -> schemas.py (валидация body)
  -> dependencies.py (Bearer/JWT/server-side session)
  -> auth_service.py (бизнес-логика)
  -> token_service.py (создание/проверка токенов, hash refresh)
  -> models.py + db.py (SQLAlchemy и PostgreSQL)
  -> dto.py (формирование типизированного ответа)
  -> HTTP Response
```

### 3.4 Что делает каждый файл `app/`

`app/main.py`:

- `create_app()` создает FastAPI и кладет `settings` в `app.state`.
- В `lifespan` вызывается `Base.metadata.create_all(bind=engine)`.
- `from app import models` нужен для регистрации ORM-моделей в `Base.metadata` перед `create_all`.

`app/db.py`:

- Читает настройки через `get_settings()`.
- Создает `engine` и `SessionLocal`.
- `get_db()` выдает SQLAlchemy-сессию на запрос и закрывает ее в `finally`.

`app/config.py`:

- Класс `Settings` читает `.env`.
- Валидирует `JWT_ALGORITHM`, `REFRESH_TOKEN_PEPPER`, TTL и остальные параметры.
- Разделяет секреты: `JWT_SECRET` только для подписи JWT, `REFRESH_TOKEN_PEPPER` только для hash refresh.

`app/models.py`:

- `User` хранит профиль и `password_hash`.
- `AuthSession` хранит server-side состояние сессии.
- Индексы `uq_users_username_ci` и `uq_users_email_ci` делают уникальность без учета регистра.

`app/schemas.py`:

- Валидирует форму входного JSON для каждого endpoint.
- Проверяет формат username для `register`, возраст (14+), сложность пароля при `register`/`change-password`, совпадение `password/c_password`.
- Для `login` применяет те же правила формата, что и в ТЗ: `username` по шаблону и `password` по требованиям сложности.
- Возвращает DTO через `to_dto()`, чтобы сервис работал уже с валидированными данными.

`app/dto.py`:

- Описывает immutable-объекты (входные и выходные).
- Нужен как граница между слоями: роут/сервис/ответ говорят в одних типах.

`app/token_service.py`:

- `create_access_token()` генерирует JWT с claim: `sub`, `jti`, `iat`, `exp`, `type=access`.
- `decode_access_token()` проверяет header, подпись, `exp`, обязательные поля и `type`.
- `create_refresh_token()` создает случайный непрозрачный токен.
- `hash_refresh_token()` считает HMAC-SHA256 для хранения в БД.

`app/dependencies.py`:

- `_extract_bearer_token()` строго проверяет формат `Authorization: Bearer <token>`.
- `get_current_access_payload()` делает JWT-проверки (header + decode).
- `get_current_user_context()` делает server-side проверку сессии в БД по `access_jti`.
- `ensure_guest_only()` пускает только гостя на `/register` (если активная сессия есть, вернет `403`).

`app/auth_service.py`:

- Реализует все бизнес-сценарии: register, login, me, logout, refresh, change-password.
- Управляет транзакциями, revoke-логикой и лимитом сессий.
- Обрабатывает параллелизм через блокировки БД и единый порядок блокировок.

`app/auth_routes.py`:

- Объявляет endpoint'ы `/api/auth/*`.
- Забирает `ip` и `user-agent` из `Request`.
- Перехватывает доменные исключения и мапит их в корректные HTTP-коды.

### 3.5 Жизненный цикл запросов в `app/`

`POST /api/auth/register`:

1. `auth_routes.register` получает `RegisterRequest`.
2. `schemas.py` проверяет поля (username/password/birthday/c_password).
3. `dependencies.ensure_guest_only` блокирует вызов, если клиент уже авторизован.
4. `AuthService.register_user` проверяет дубли username/email без учета регистра.
5. Пароль хешируется (`bcrypt`), создается запись `users`.
6. Возвращается `UserDTO` без секретов.

`POST /api/auth/login`:

1. `auth_routes.login` берет body + `ip/user-agent`.
2. `AuthService.login_user` проверяет логин/пароль.
3. `_create_session` выдает `access_token` + `refresh_token`.
4. В `auth_sessions` пишется `access_jti`, `refresh_hash`, сроки, метаданные клиента.
5. `_enforce_session_limit` отзывает самые старые активные сессии при переполнении.
6. Роут возвращает `AuthSuccessDTO`.

`GET /api/auth/me`:

1. `dependencies.get_current_access_payload` валидирует JWT.
2. `dependencies.get_current_user_context` проверяет сессию в БД.
3. `auth_routes.me` вызывает `AuthService.get_current_user`.
4. Возвращается `UserDTO`.

`POST /api/auth/refresh`:

1. Клиент отправляет raw refresh token.
2. `AuthService.refresh_tokens` считает `refresh_hash`.
3. Находит владельца token и блокирует строки (`users -> auth_sessions`) через `FOR UPDATE`.
4. Если refresh уже использован/истек/отозван, вызывается revoke всех сессий пользователя.
5. Если валиден, старая сессия помечается `refresh_used_at` и отзывается (`refresh_rotated`).
6. Создается новая сессия с тем же `family_id` и новой парой токенов.

`POST /api/auth/out` и `POST /api/auth/out_all`:

1. Через dependency получается `CurrentUserContext`.
2. `AuthService` отзывает текущую или все сессии.
3. Возвращается DTO-сообщение.

`POST /api/auth/change-password`:

1. Проверяется access через dependency.
2. Валидируется `ChangePasswordRequest`.
3. `AuthService.change_password` сверяет `current_password`.
4. Обновляет `password_hash`.
5. Отзывает все активные сессии пользователя.

### 3.6 Жизненный цикл токенов в `app/`

Access token:

- Формат: JWT.
- Где создается: `TokenService.create_access_token`.
- Где проверяется: `dependencies.get_current_access_payload`.
- Когда перестает работать: при истечении `exp` или при revoke server-side сессии.

Refresh token:

- Формат: случайная строка (не JWT).
- Где создается: `TokenService.create_refresh_token`.
- Где хранится: на клиенте raw token, на сервере только `refresh_hash`.
- Одноразовость: каждый успешный refresh делает rotation и отзывает старую сессию.
- Reuse detection: повторное использование старого refresh => revoke всех сессий пользователя.

### 3.7 Модель server-side сессии (`auth_sessions`)

- `access_jti`: связка access JWT с записью в БД.
- `refresh_hash`: хеш refresh-токена (raw значение в БД не хранится).
- `family_id`: объединяет цепочку refresh-rotation одной логической сессии.
- `refresh_used_at`: признак, что refresh уже был применен.
- `revoked_at` и `revoked_reason`: причина и время отзыва.
- `access_expires_at` и `refresh_expires_at`: сроки жизни токенов.
- `ip` и `user_agent`: метаданные клиента для аудита.

### 3.8 Параллелизм и консистентность в `app/`

- В refresh используется блокировка строки пользователя и сессии (`with_for_update`), чтобы один refresh нельзя было успешно применить дважды параллельно.
- Лимит активных сессий тоже сериализуется блокировкой строки `User`.
- В обоих местах соблюдается порядок блокировок `users -> auth_sessions` для снижения риска дедлоков.
- Коммиты и rollback инкапсулированы в `_commit_or_rollback`.

### 3.9 Где рождаются HTTP ошибки

- `auth_service.py` поднимает доменные исключения (`InvalidCredentialsError`, `RefreshTokenCompromisedError` и т.д.).
- `auth_routes.py` в `_raise_http_for_auth_error` мапит их в HTTP-коды:

1. `401`: невалидные креды/токены.
2. `403`: отозванная сессия, компрометация refresh, запрет guest-only.
3. `404`: пользователь не найден.
4. `409`: конфликт уникальности.
5. `422`: ошибки валидации входа и бизнес-валидации `ValueError`.
6. `503`: ошибки persistence/БД.

## 4. Структура БД

### `users`

- `id`
- `username` (уникальный без учета регистра)
- `email` (уникальный без учета регистра)
- `password_hash`
- `birthday`
- `created_at`
- `updated_at`

### `auth_sessions`

- `id`
- `user_id`
- `family_id`
- `access_jti` (уникальный)
- `refresh_hash`
- `created_at`
- `last_used_at`
- `access_expires_at`
- `refresh_expires_at`
- `refresh_used_at`
- `revoked_at`
- `revoked_reason`
- `ip`
- `user_agent`

## 5. Конфигурация

Используются переменные из `.env` (пример в `.env.example`):

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `APP_HOST`
- `APP_PORT`
- `JWT_SECRET`
- `JWT_ALGORITHM`
- `REFRESH_TOKEN_PEPPER`
- `ACCESS_TOKEN_TTL_MINUTES`
- `REFRESH_TOKEN_TTL_MINUTES`
- `MAX_ACTIVE_SESSIONS`
- `LOGIN_RATE_LIMIT_MAX_REQUESTS`
- `LOGIN_RATE_LIMIT_WINDOW_SECONDS`
- `REFRESH_RATE_LIMIT_MAX_REQUESTS`
- `REFRESH_RATE_LIMIT_WINDOW_SECONDS`

Важно:

- `JWT_SECRET` — только подпись JWT.
- `REFRESH_TOKEN_PEPPER` — только хеширование refresh token.
- `JWT_SECRET` обязателен и должен быть не короче 32 символов.
- Для `HS256` длина `JWT_SECRET` должна быть не меньше `32` байт.
- Оба секрета должны быть заданы; использовать одинаковые значения не рекомендуется.

## 6. Запуск

### 6.1 Через Docker

1. Создать `.env`:

```bash
cp .env.example .env
```

2. Запустить:

```bash
docker compose up --build -d
```

3. Открыть:

- API: `http://localhost:8080`
- Swagger: `http://localhost:8080/docs`

### 6.2 Локально

1. Поднять PostgreSQL.
2. Заполнить `.env`.
3. Установить зависимости:

```bash
pip install -r requirements.txt
```

4. Запустить:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

## 7. API: маршруты и ожидаемые статусы

Все маршруты под префиксом `/api/auth`.

- `POST /register` → `201`
- `POST /login` → `200`
- `GET /me` → `200`
- `POST /out` → `200`
- `GET /tokens` → `200`
- `POST /out_all` → `200`
- `POST /refresh` → `200`
- `POST /change-password` → `200`

Примечания:

- `register` доступен только неавторизованным (guest-only).
- `me`, `out`, `tokens`, `out_all`, `change-password` — защищенные (Bearer access token).
- `/tokens` возвращает только метаданные сессий, без реальных токенов.

## 8. Проверка API через Swagger

- Откройте `http://localhost:8080/docs`.
- Все готовые body и сценарии проверок вынесены в `docs/AUTH_SWAGGER_CHECKS.md`.
- Для защищенных методов сначала нажмите `Authorize` и вставьте:
  `Bearer <access_token>`

## 9. Что именно проверяется по безопасности

### Access token

- Bearer-формат заголовка.
- Наличие и валидность `alg` в JWT header.
- Проверка подписи.
- Проверка `exp`.
- Проверка `type=access`.
- Проверка server-side состояния сессии по `access_jti`.

### Refresh token

- Генерируется как криптографически случайная строка.
- В БД хранится только `refresh_hash`.
- Одноразовый (rotation).
- Повторное использование/компрометация → revoke all.

### Метаданные клиента

- `IP` валидируется как корректный IPv4/IPv6.
- `User-Agent` нормализуется: trim, пустое -> `None`, запрет `\r`, `\n`, `\x00`, ограничение длины 512.
- `IP` и `User-Agent` хранятся только в БД, не в токене.

## 10. Учебные упрощения

- Таблицы создаются на startup через `Base.metadata.create_all(...)`.
- Rate-limit реализован in-memory и работает в рамках одного процесса приложения.
