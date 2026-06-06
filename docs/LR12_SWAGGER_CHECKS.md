# Проверка ЛР12 через Swagger

## 1. Подготовка

Запустить контейнеры:

```bash
docker compose up -d --build
docker compose exec api python -m alembic upgrade head
```

Создать demo-файл:

```bash
python scripts/make_lr12_demo_xlsx.py
```

Если `openpyxl` не установлен локально, можно создать файл внутри контейнера и скопировать его на host:

```bash
docker compose exec api python scripts/make_lr12_demo_xlsx.py
mkdir -p tmp
docker compose cp api:/app/tmp/lr12_attendance_demo.xlsx tmp/lr12_attendance_demo.xlsx
```

Файл появится здесь:

```text
tmp/lr12_attendance_demo.xlsx
```

## 2. Получить admin

1. Зарегистрировать пользователя через `/api/auth/register`.
2. Назначить ему роль `admin` напрямую в БД:

```sql
insert into role_user (user_id, role_id, created_by)
select u.id, r.id, u.id
from users u
cross join roles r
where u.username = 'Adminuser'
  and r.slug = 'admin'
on conflict do nothing;
```

3. Залогиниться через `/api/auth/login`.
4. В Swagger нажать `Authorize` и вставить `Bearer <access_token>`.

## 3. Проверка endpoint

В Swagger открыть группу `attendance`.

Endpoint:

```text
POST /api/attendance/calculate
```

Загрузить `tmp/lr12_attendance_demo.xlsx`.

Ожидаемо:

- `200`;
- в ответе есть `groups`;
- в ответе есть `automatic_success_students`;
- Иванов проходит по посещаемости и лабам;
- Петров не проходит;
- Сидорова проходит из-за `Зачёт автоматом`.

## 4. Негативные проверки

- без токена: `401`;
- обычный пользователь: `403`;
- без файла: `422`;
- файл не `.xlsx`: `422`;
- нет листа `Посещаемость`: `422`;
- нет обязательной колонки: `422`;
- файл больше `UPLOAD_MAX_SIZE_MB`: `422`.

## 5. Где смотреть permission

Permission:

```text
calculate-attendance
```

Он добавляется миграцией и назначается роли `admin`.
