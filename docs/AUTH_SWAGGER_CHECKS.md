# Проверка API через Swagger

Откройте `http://localhost:8080/docs`.

Для защищенных методов сначала нажмите `Authorize` и вставьте:
`Bearer <access_token>`.

## 1. Базовые пользователи для проверки

`User A`:

```json
{
	"username": "StudentA",
	"email": "studenta@example.com",
	"password": "Strong#123",
	"c_password": "Strong#123",
	"birthday": "2000-05-20"
}
```

`User B`:

```json
{
	"username": "StudentB",
	"email": "studentb@example.com",
	"password": "Strong#456",
	"c_password": "Strong#456",
	"birthday": "1999-08-15"
}
```

## 2. `POST /api/auth/register`

Успех (`201`): используйте `User A`, затем `User B`.

Ошибка `409` (дубликат):

```json
{
	"username": "StudentA",
	"email": "studenta@example.com",
	"password": "Strong#123",
	"c_password": "Strong#123",
	"birthday": "2000-05-20"
}
```

Ошибка `422` (username не по правилам):

```json
{
	"username": "student1",
	"email": "newuser@example.com",
	"password": "Strong#123",
	"c_password": "Strong#123",
	"birthday": "2000-05-20"
}
```

Ошибка `422` (слабый пароль):

```json
{
	"username": "StudentC",
	"email": "studentc@example.com",
	"password": "weakpass",
	"c_password": "weakpass",
	"birthday": "2000-05-20"
}
```

Ошибка `422` (`c_password` не совпадает):

```json
{
	"username": "StudentD",
	"email": "studentd@example.com",
	"password": "Strong#123",
	"c_password": "Strong#124",
	"birthday": "2000-05-20"
}
```

Ошибка `422` (неверный формат даты):

```json
{
	"username": "StudentE",
	"email": "studente@example.com",
	"password": "Strong#123",
	"c_password": "Strong#123",
	"birthday": "20-05-2000"
}
```

Ошибка `422` (возраст < 14):

```json
{
	"username": "StudentF",
	"email": "studentf@example.com",
	"password": "Strong#123",
	"c_password": "Strong#123",
	"birthday": "2015-01-01"
}
```

## 3. `POST /api/auth/login`

Успех (`200`):

```json
{
	"username": "StudentA",
	"password": "Strong#123"
}
```

Ошибка `401` (неверный пароль):

```json
{
	"username": "StudentA",
	"password": "Wrong#123"
}
```

Ошибка `401` (неизвестный пользователь):

```json
{
	"username": "StudentZ",
	"password": "Strong#123"
}
```

Ошибка `422` (пустой username):

```json
{
	"username": "   ",
	"password": "Strong#123"
}
```

Проверка rate-limit (`429`): отправьте неверный логин из одного клиента больше лимита в минуту.

## 4. `POST /api/auth/refresh`

Успех (`200`):

```json
{
	"refresh_token": "<REFRESH_TOKEN_ИЗ_LOGIN>"
}
```

Ошибка `422` (пустой `refresh_token`):

```json
{
	"refresh_token": "   "
}
```

Ошибка `401` (случайный токен):

```json
{
	"refresh_token": "not_existing_refresh_token"
}
```

Ошибка `403` (reuse detection):

1. Логин и сохраните `refresh_1`.
2. Вызовите `refresh` с `refresh_1` и получите `refresh_2`.
3. Еще раз вызовите `refresh` с `refresh_1` (старым) -> `403`.

## 5. `POST /api/auth/change-password`

Успех (`200`):

```json
{
	"current_password": "Strong#123",
	"new_password": "NewStrong#123",
	"c_password": "NewStrong#123"
}
```

Ошибка `401` (неверный текущий пароль):

```json
{
	"current_password": "Wrong#123",
	"new_password": "NewStrong#123",
	"c_password": "NewStrong#123"
}
```

Ошибка `422` (слабый новый пароль):

```json
{
	"current_password": "Strong#123",
	"new_password": "weak",
	"c_password": "weak"
}
```

Ошибка `422` (`c_password` не совпадает):

```json
{
	"current_password": "Strong#123",
	"new_password": "NewStrong#123",
	"c_password": "NewStrong#124"
}
```

## 6. Защищенные методы без body

1. `GET /api/auth/me` без `Authorize` -> `401`.
2. `GET /api/auth/me` с валидным access -> `200`.
3. `POST /api/auth/out` с валидным access -> `200`, потом `GET /me` тем же access -> `403`.
4. Два логина подряд -> `GET /api/auth/tokens` показывает активные сессии (`200`).
5. `POST /api/auth/out_all` в одной сессии -> в другой сессии `GET /me` -> `403`.
6. `POST /api/auth/register` с `Authorize` (валидный access) -> `403` (guest-only).
