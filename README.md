# Backend Labs

Витрина лабораторных работ по разработке серверных приложений. Основная ветка `main` содержит навигацию по решениям, а каждая лабораторная вынесена в отдельную ветку.

Репозиторий: [github.com/Andrey787878/backend-labs](https://github.com/Andrey787878/backend-labs)

## Ветки лабораторных

| Ветка | Лабораторная работа | Краткое содержание |
|---|---|---|
| [`main`](https://github.com/Andrey787878/backend-labs/tree/main) | Витрина проекта | Навигация по лабораторным работам и краткое описание структуры репозитория. |
| [`lb1`](https://github.com/Andrey787878/backend-labs/tree/lb1) | Базовая подготовка | Структура FastAPI-проекта, Docker-окружение, базовая документация. |
| [`lb2`](https://github.com/Andrey787878/backend-labs/tree/lb2) | Авторизация | Регистрация, логин, JWT access/refresh, server-side sessions, refresh rotation, logout. |
| [`lb3`](https://github.com/Andrey787878/backend-labs/tree/lb3) | RBAC | Роли, разрешения, связи user-role и role-permission, защищённые admin endpoints. |
| [`lb4`](https://github.com/Andrey787878/backend-labs/tree/lb4) | Audit logging | Логирование изменений сущностей, история изменений, undo/restore-сценарии. |
| [`lb6`](https://github.com/Andrey787878/backend-labs/tree/lb6) | Git webhook | Webhook для обновления проекта через Git, secret key, lock, deployment logs. |
| [`lb7`](https://github.com/Andrey787878/backend-labs/tree/lb7) | Request/Response logging | Middleware логирования HTTP-запросов и ответов, таблица `logs_requests`, endpoints просмотра логов. |
| [`lb8`](https://github.com/Andrey787878/backend-labs/tree/lb8) | Очереди и отчёты | DB-backed очередь задач, background worker, генерация JSON-отчёта по логам. |
| [`lb12`](https://github.com/Andrey787878/backend-labs/tree/lb12) | Автоматический зачёт | Загрузка Excel-файла, расчёт посещаемости, выполненных лабораторных и автоматического зачёта. |

## Структура развития

Поздние ветки развивают предыдущие решения и сохраняют накопленную функциональность:

```text
lb2 -> lb3 -> lb4 -> lb6 -> lb7 -> lb8 -> lb12
```

## Технологический стек

| Область | Технологии |
|---|---|
| Backend | Python, FastAPI, Pydantic |
| Database | PostgreSQL, SQLAlchemy, Alembic |
| Auth | JWT, refresh rotation, server-side sessions |
| Access control | RBAC, roles, permissions |
| Infrastructure | Docker, Docker Compose |
| Files and reports | OpenPyXL, JSON reports |
| Documentation | Swagger/OpenAPI, Markdown docs |

## Основные модули по веткам

### `lb2`: Авторизация

- регистрация и логин;
- access/refresh JWT;
- хранение активных сессий на сервере;
- refresh rotation;
- logout одной или всех сессий.

### `lb3`: RBAC

- роли и разрешения;
- назначение ролей пользователям;
- назначение разрешений ролям;
- защита endpoints через permission checks.

### `lb4`: Audit logging

- журналирование изменений;
- история изменений сущностей;
- восстановление и undo-сценарии.

### `lb6`: Git webhook

- endpoint `POST /hooks/git`;
- проверка `secret_key`;
- файловая блокировка deployment-процесса;
- выполнение Git-команд;
- структурированные deployment logs.

### `lb7`: Request/Response logging

- middleware логирования HTTP-запросов;
- сохранение request/response данных;
- просмотр и очистка логов администратором.

### `lb8`: Очереди и отчёты

- таблица задач `report_jobs`;
- постановка отчёта в очередь;
- background worker;
- аналитический JSON-отчёт.

### `lb12`: Автоматический зачёт

- загрузка `.xlsx` файла посещаемости;
- парсинг листа `Посещаемость`;
- расчёт процента посещаемости;
- расчёт процента выполненных лабораторных;
- итоговая группировка студентов по группам;
- список студентов, получающих зачёт автоматически.

## Документация

В ветках лабораторных находятся дополнительные Markdown-файлы с описанием endpoints, схем ответов и проверок. Основная документация API доступна через Swagger после запуска соответствующей ветки.
