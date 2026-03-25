# Доступ к БД (Docker Compose)

Этот файл описывает, как подключаться к PostgreSQL, который запущен через `docker compose` в текущем проекте.

## 1. Текущие параметры подключения (из `.env`)

- `POSTGRES_DB=app`
- `POSTGRES_USER=app`
- `POSTGRES_PASSWORD=app`
- `POSTGRES_HOST=db`
- `POSTGRES_PORT=5432`

## 2. Актуальные URL подключения

Внутри Docker-сети (так подключается API):

```text
postgresql+psycopg://app:app@db:5432/app
```

С хоста (для DBeaver/pgAdmin/DataGrip/локального psql):

```text
postgresql://app:app@localhost:5432/app
```

## 3. Быстрый вход в БД через контейнер

Поднять сервисы:

```bash
docker compose up -d
```

Открыть `psql` внутри контейнера `db`:

```bash
docker compose exec db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

## 4. Полезные команды в psql

```sql
\conninfo
\dt
\d users
\d auth_sessions
SELECT * FROM users;
SELECT * FROM auth_sessions ORDER BY id DESC LIMIT 20;
```

Выход:

```sql
\q
```

## 5. Одноразовые команды без интерактива

Показать таблицы:

```bash
docker compose exec -T db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\\dt"'
```

Показать пользователей:

```bash
docker compose exec -T db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT id, username, email, birthday FROM users ORDER BY id;"'
```

## 6. Подключение GUI-клиентом

Используйте:

- Host: `localhost`
- Port: `5432`
- Database: `app`
- User: `app`
- Password: `app`

Если клиент запускается внутри того же docker-compose (другой контейнер), host должен быть `db`.

