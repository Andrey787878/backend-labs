# LB1 FastAPI + PostgreSQL

Минимальный учебный сервис на `FastAPI` + `PostgreSQL` с запуском через `docker compose`.

## Структура

```text
lb1/
├─ app/
│  ├─ main.py
│  ├─ config.py
│  ├─ services/
│  │  └─ database_info_service.py
│  ├─ dto/
│  │  ├─ server_info.py
│  │  ├─ client_info.py
│  │  └─ database_info.py
├─ .env
├─ .env.example
├─ Dockerfile
├─ docker-compose.yml
├─ requirements.txt
└─ README.md
```

## Что реализовано

- `GET /info/server` - версия Python/FastAPI + locale/timezone
- `GET /info/client` - IP клиента + User-Agent
- `GET /info/database` - драйвер, версия PostgreSQL, имя БД

## Запуск

Запуск без сборки в фоновом режиме:

```bash
docker compose up -d
```

Запуск со сборкой в фоновом режиме:

```bash
docker compose up --build -d
```

Запуск с автопересборкой:

```bash
docker compose up --build --watch
```

Остановка:

```bash
docker compose down
```

## Проверка API

```bash
curl -i http://localhost:8080/info/server
curl -i http://localhost:8080/info/client
curl -i http://localhost:8080/info/database
```

### Проверка опасного `User-Agent`

```bash
curl -i -H "User-Agent: <script>alert(1)</script>" http://localhost:8080/info/client
```
