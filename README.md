# Разработка серверных приложений

## Структура

``` text
/
├─ app/
│  ├─ main.py
│  ├─ core/
│  │  └─ settings.py
│  ├─ api/
│  │  ├─ router.py
│  │  └─ controllers/
│  │     └─ info_controller.py
│  ├─ dto/
│  │  ├─ server_info_dto.py
│  │  ├─ client_info_dto.py
│  │  └─ database_info_dto.py
│  └─ db/
│     └─ session.py
├─ docker-compose.yml
├─ Dockerfile
├─ requirements.txt
├─ .gitignore
└─ .env.example
```

## Что за что отвечает

### `app/main.py`
Точка входа приложения:
- создаёт экземпляр `FastAPI()`
- подключает основной роутер (`app.api.router`)

### `app/core/settings.py`
Настройки приложения (конфиг):
- читает переменные окружения из `.env`
- хранит `APP_LOCALE`, `APP_TIMEZONE`
- хранит `DATABASE_URL` для подключения к PostgreSQL

> `.env` не коммитится, вместо него в репозитории хранится `.env.example`.

### `app/api/router.py`
Единая точка подключения роутов:
- описывает маршруты `/info/server`, `/info/client`, `/info/database`
- связывает эндпоинты с методами контроллера

### `app/api/controllers/info_controller.py`
Контроллер с бизнес-логикой для эндпоинтов `/info/*`:
- `server_info()` — информация о сервере/окружении
- `client_info(request)` — информация о клиенте (IP, User-Agent)
- `database_info()` — информация о подключении к БД (драйвер, версия, имя базы)

### `app/dto/*`
DTO-модели (Pydantic) — структуры ответов API.
Важно: эндпоинты возвращают **DTO**, а не `dict`.

- `ServerInfoDTO` — ответ для `/info/server`
- `ClientInfoDTO` — ответ для `/info/client`
- `DatabaseInfoDTO` — ответ для `/info/database`

### `app/db/session.py`
Работа с базой данных:
- создание подключения/engine (через `DATABASE_URL`)
- получение мета-информации о БД (версия сервера, имя базы)


## Переменные окружения

Необходимо создать файл `.env` в корне проекта, и задать ключи используя `.env.example` как шаблон.

## Запуск

``` bash
docker compose up --build
```

## Проверка

```bash
curl -i "http://localhost:8080/docs"
curl -s "http://localhost:8080/info/server"
curl -s "http://localhost:8080/info/client"
curl -s "http://localhost:8080/info/database"
```