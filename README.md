# LB1

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
curl http://localhost:8080/info/server
curl http://localhost:8080/info/client
curl http://localhost:8080/info/database
```

### Проверка опасного `User-Agent`

```bash
curl -i -H "User-Agent: <script>alert(1)</script>" http://localhost:8080/info/client
```
