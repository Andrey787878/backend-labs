# Лабораторные работы №2 и №3 (FastAPI + PostgreSQL)

## Разделение По Лабам

### ЛР2 — Авторизация (`/api/auth/*`)

- `app/auth_routes.py`
- `app/auth_service.py`
- `app/token_service.py`
- `app/dependencies.py` (auth dependencies)
- `app/models.py`:
  `User`, `AuthSession`
- `app/schemas.py`:
  `LoginRequest`, `RegisterRequest`, `RefreshRequest`
- `app/dto.py`:
  auth/session DTO

### ЛР3 — RBAC (data layer + DTO/schemas + migrations)

- `app/models.py`:
  `Role`, `Permission`, `UserRole`, `PermissionRole`
- `app/schemas.py`:
  `StoreRoleRequest`, `UpdateRoleRequest`, `StorePermissionRequest`, `UpdatePermissionRequest`,
  `AttachUserRoleRequest`, `AttachRolePermissionRequest`
- `app/dto.py`:
  `RoleDTO`, `RoleCollectionDTO`, `PermissionDTO`, `PermissionCollectionDTO` и связанные write DTO
- `alembic/*` и `alembic.ini`:
  миграции и базовый seed для RBAC

### ЛР4 — Audit Logging + Undo

- `app/models.py`:
  `ChangeLog` + soft-delete поля пользователя
- `app/audit_context.py`:
  привязка `actor_user_id` к DB-сессии на время мутаций
- `app/audit_events.py`:
  автоматическое логирование create/update/delete (`User`, `Role`, `Permission`)
- `app/audit_service.py`:
  история изменений (`story`) и откат состояния (`undo`)
- `app/audit_routes.py`:
  endpoints истории и восстановления по `change_log`
- `app/rbac_service.py`, `app/rbac_routes.py`:
  добавленные admin-операции `PATCH/DELETE/RESTORE` для `User`
- `alembic/versions/20260520_0003_add_change_logs_and_user_soft_delete.py`:
  таблица `change_logs` + soft-delete колонки `users`
- `alembic/versions/20260520_0004_seed_story_permissions.py`:
  `get-story-*` permissions и назначение `admin`
- `docs/LR4_ENDPOINTS_SCHEMA.md`, `docs/LR4_SWAGGER_CHECKS.md`, `docs/LR4_DEFENSE_QA.md`:
  документация для проверки и защиты

### ЛР6 — Git Webhook Deployment

- `app/git_webhook_routes.py`:
  открытый endpoint `POST /hooks/git`
- `app/deployment_service.py`:
  последовательность webhook deployment: логирование, lock, Git-команды
- `app/git_command_runner.py`:
  безопасный запуск Git-команд без shell
- `app/deployment_lock.py`:
  файловая блокировка от параллельного deployment
- `app/deployment_logger.py`:
  структурированные логи в `deployment_logs/deployment.log`
- `app/config.py`, `.env.example`:
  `GIT_WEBHOOK_SECRET`, `GIT_DEFAULT_BRANCH`, TTL lock и timeout команд
- `docs/LR6_ENDPOINTS_SCHEMA.md`, `docs/LR6_SWAGGER_CHECKS.md`, `docs/LR6_DEFENSE_QA.md`:
  документация для проверки и защиты

## ЛР2: Авторизация

## 1. Кратко о проекте

Этот сервис реализует API-аутентификацию и управление server-side сессиями пользователей:

- регистрация пользователя;
- вход по `username/password`;
- выдача пары `access_token + refresh_token`;
- получение текущего пользователя (`/me`);
- выход из текущей сессии (`/out`);
- просмотр активных сессий (`/tokens`);
- выход со всех устройств (`/out_all`);
- обновление пары токенов (`/refresh`) с rotation, one-time refresh и reuse detection.

## 2. Ключевая идея реализации

Система основана на двух уровнях проверки:

1. Проверка JWT (подпись, срок, обязательные claims).
2. Проверка server-side состояния сессии в БД (`auth_sessions`).

То есть даже валидный JWT перестает работать, если соответствующая сессия в БД отозвана/истекла.

## 3. Архитектура

### 3.1 Структура `app/`

```text
app/
  main.py          # создание FastAPI-приложения, lifespan, подключение роутов
  db.py            # SQLAlchemy engine/session, Base, get_db
  config.py        # конфигурация из .env + валидация секретов/TTL
  models.py        # ORM-модели User и AuthSession
  schemas.py       # request-схемы и валидация входных данных
  dto.py           # immutable DTO для входа/выхода
  token_service.py # выпуск/проверка JWT, hash refresh
  auth_service.py  # бизнес-логика авторизации и управления сессиями
  dependencies.py  # auth dependencies, guest-only, pre-validation
  auth_routes.py   # HTTP endpoints /api/auth/*
```

### 3.2 Разделение по слоям

- `auth_routes.py`: HTTP-слой, принимает запросы и отдает ответы.
- `schemas.py`: валидация входа (`RegisterRequest`, `LoginRequest`, `RefreshRequest`).
- `dependencies.py`: проверки доступа, bearer-auth, pre-check уникальности регистрации.
- `auth_service.py`: доменная логика (сессии, refresh-rotation, revoke).
- `token_service.py`: криптография токенов.
- `models.py` + `db.py`: данные и транзакционная работа с БД.
- `dto.py`: типизированные immutable-объекты ответа/входа между слоями.

### 3.3 Поток вызова

```text
HTTP Request
  -> auth_routes.py
  -> schemas.py / dependencies.py
  -> auth_service.py
  -> token_service.py
  -> models.py + db.py
  -> DTO
  -> HTTP Response
```

## 4. Модель данных

### 4.1 Таблица `users`

- `id`
- `username`
- `email`
- `password_hash`
- `birthday`
- `created_at`
- `updated_at`

Особенности:

- `username` и `email` уникальны без учета регистра (индексы на `lower(...)`).

### 4.2 Таблица `auth_sessions`

- `id`
- `user_id`
- `family_id`
- `access_jti`
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

Смысл:

- `access_jti` связывает access JWT с записью сессии.
- `refresh_hash` хранит только хеш refresh, а не raw token.
- `revoked_*` и `refresh_used_at` поддерживают revoke/reuse-detection.

## 5. Формат токенов

### 5.1 Access token

`access_token` — JWT с claims:

- `sub` — id пользователя;
- `jti` — id access-сессии (`access_jti`);
- `iat`, `exp`;
- `type=access`.

Использование:

- передается в `Authorization: Bearer <access_token>`;
- валидируется по подписи и сроку;
- затем проверяется состояние сессии в БД.

### 5.2 Refresh token

`refresh_token` — JWT с claims:

- `sub` — id пользователя;
- `access_jti` — привязка к сессии;
- `jti` — id refresh-токена;
- `iat`, `exp`;
- `type=refresh`.

Использование:

- передается в body `/refresh`;
- в БД хранится только `refresh_hash` (HMAC-SHA256 с `REFRESH_TOKEN_PEPPER`).

## 6. Логика endpoint-ов

Все маршруты под префиксом `/api/auth`.

### 6.1 `POST /register`

- guest-only (если уже есть активная авторизация, вернет `403`);
- валидация полей запроса;
- pre-check уникальности `username/email` до сервиса;
- создание пользователя с `password_hash`.

Успех: `201 UserDTO`.

### 6.2 `POST /login`

- валидация запроса;
- проверка username/password;
- создание сессии и выдача `access + refresh`;
- контроль лимита активных сессий (`MAX_ACTIVE_SESSIONS`): при переполнении отзываются самые старые.

Успех: `200 AuthSuccessDTO`.

### 6.3 `GET /me`

- требует bearer access token;
- JWT-проверка + server-side проверка сессии;
- возврат текущего пользователя.

Успех: `200 UserDTO`.

### 6.4 `POST /out`

- требует bearer access token;
- отзывает текущую сессию по `access_jti`.

Успех: `200 MessageResponseDTO`.

### 6.5 `GET /tokens`

- требует bearer access token;
- возвращает список активных сессий пользователя без секретных токенов.

Успех: `200 TokenListDTO`.

### 6.6 `POST /out_all`

- требует bearer access token;
- отзывает все активные сессии пользователя.

Успех: `200 LogoutAllResponseDTO`.

### 6.7 `POST /refresh`

- принимает `refresh_token` в body;
- проверяет refresh JWT и связку с сессией;
- выполняет rotation: старая refresh-сессия помечается использованной/отзывается, создается новая сессия и новая пара токенов.

Безопасность в `refresh`:

- `used/revoked/expired/hash_mismatch` -> `revoke all` + `403`.
- `session not found` по `sub + access_jti` -> `revoke all` + `403`.
- если подпись/формат refresh невалидны, но токен можно связать с существующей сессией (`sub + access_jti`) -> `revoke all` + `403`.
- полностью мусорный/несвязываемый токен -> `401`.

## 7. Access control и Swagger UI

### 7.1 Как авторизоваться в Swagger

Защищенные методы: `GET /me`, `POST /out`, `GET /tokens`, `POST /out_all`.

В Swagger используется `HTTPBearer` security scheme:

1. Нажмите `Authorize`.
2. Вставьте токен в поле авторизации (для UI обычно достаточно самого токена).
3. Swagger сам отправит `Authorization: Bearer <token>`.

### 7.2 Для curl/postman

Передавайте заголовок явно:

```bash
-H "Authorization: Bearer <access_token>"
```

## 8. Ошибки и статусы

Основные коды:

- `200` — успешные операции;
- `201` — успешная регистрация;
- `401` — отсутствует/невалиден токен, неверные креды;
- `403` — revoked/expired сессия, guest-only запрет, компрометация refresh;
- `422` — ошибки валидации полей (включая дубли `username/email` на регистрации);
- `503` — временная ошибка БД/сохранения.

## 9. Конфигурация (`.env`)

Используются:

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

Важно:

- `JWT_SECRET` — подпись JWT;
- `REFRESH_TOKEN_PEPPER` — только для хеширования refresh;
- `JWT_SECRET` не короче 32 байт;
- `REFRESH_TOKEN_PEPPER` обязателен и не пустой.

## 10. Запуск

### 10.0 Применение миграций

Для Docker Compose (рекомендуется):

```bash
docker compose exec api python -m alembic -c /app/alembic.ini upgrade head
```

Для локального запуска (без Docker):

```bash
alembic upgrade head
```

### 10.1 Docker

```bash
cp .env.example .env
docker compose up --build -d
```

- API: `http://localhost:8080`
- Swagger: `http://localhost:8080/docs`

### 10.2 Локально

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

## 11. Быстрый smoke-check

1. `POST /api/auth/register` -> `201`.
2. `POST /api/auth/login` -> получить `access_token` и `refresh_token`.
3. `GET /api/auth/me` с bearer access -> `200`.
4. `POST /api/auth/refresh` с refresh -> новая пара токенов.
5. Повторить refresh старым токеном -> `403` и revoke сессий.

## 12. Дополнительные документы

- [DB schema](docs/DB_SCHEMA.md)
- [RBAC DB schema (ЛР3)](docs/RBAC_DB_SCHEMA.md)
- [Auth endpoint schema](docs/AUTH_ENDPOINTS_SCHEMA.md)
- [RBAC endpoint schema (ЛР3)](docs/RBAC_ENDPOINTS_SCHEMA.md)
- [Swagger checks](docs/AUTH_SWAGGER_CHECKS.md)
- [RBAC Swagger checks (ЛР3)](docs/RBAC_SWAGGER_CHECKS.md)
- [RBAC Defense QA (ЛР3)](docs/RBAC_DEFENSE_QA.md)
