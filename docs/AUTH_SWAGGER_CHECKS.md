# Проверка API через Swagger (актуальная)

Откройте `http://localhost:8080/docs`.

## 1. Как правильно авторизоваться в Swagger

### 1.1 Защищенные методы

Защищенные методы:

- `GET /api/auth/me`
- `POST /api/auth/out`
- `GET /api/auth/tokens`
- `POST /api/auth/out_all`

Для них нужен `access_token` в заголовке `Authorization`.

Правильный способ в Swagger UI:

1. Сначала выполните `POST /api/auth/login` и скопируйте `access_token`.
2. Нажмите кнопку `Authorize` (замок вверху страницы Swagger).
3. В поле `HTTPBearer` вставьте **сам JWT токен** (строка вида `eyJ...`), без слова `Bearer`.
4. Нажмите `Authorize`, потом `Close`.
5. Выполните защищенный метод.

Проверка, что все ок:

- В блоке `Curl` у защищенного метода должен появиться заголовок:
  - `-H 'Authorization: Bearer <...>'`

Если этого заголовка нет, сервер вернет `401`.

### 1.2 Важно про тип токена

Для защищенных методов нужен только `access_token`.

Если подставить `refresh_token`, получите ошибку:

```json
{
  "detail": "Поле type должно быть равно \"access\"."
}
```

### 1.3 Почему у `/register` больше нет поля `Authorization`

`POST /api/auth/register` не является защищенным методом, поэтому поле `Authorization` из Swagger скрыто.
Это сделано для более понятного UI.

Важно:

- Правило guest-only в API осталось: если отправить валидный access в заголовке `Authorization`, сервер вернет `403`.
- Просто в Swagger UI это поле не показывается для `/register`; такой кейс удобнее проверять через curl/Postman.

## 2. Базовые пользователи для проверки

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

## 3. Проверки endpoint-ов

## 3.1 `POST /api/auth/register`

Успех (`201`): используйте `User A`, затем `User B`.

Проверка guest-only (`403`) через curl/Postman:

1. Сначала сделайте `POST /api/auth/login` и возьмите `access_token`.
2. Отправьте `POST /api/auth/register` с заголовком `Authorization: Bearer <access_token>`.
3. Ожидаемо получите `403`.

Ошибка `422` (дубликат):

```json
{
  "username": "StudentA",
  "email": "studenta@example.com",
  "password": "Strong#123",
  "c_password": "Strong#123",
  "birthday": "2000-05-20"
}
```

## 3.2 `POST /api/auth/login`

Успех (`200`):

```json
{
  "username": "StudentA",
  "password": "Strong#123"
}
```

После успеха скопируйте:

- `access_token` -> для `Authorize` и защищенных методов.
- `refresh_token` -> только для `POST /api/auth/refresh`.

Ошибка `401` (неверный пароль):

```json
{
  "username": "StudentA",
  "password": "Wrong#123"
}
```

## 3.3 `POST /api/auth/refresh`

Успех (`200`):

```json
{
  "refresh_token": "<REFRESH_TOKEN_ИЗ_LOGIN>"
}
```

Важно:

- Токен для `/refresh` отправляется в `body`, не через `Authorize`.
- После успешного refresh используйте новый `access_token` для защищенных методов.

Ошибка `422` (пустой `refresh_token`):

```json
{
  "refresh_token": "   "
}
```

Ошибка `401` (совсем невалидный токен):

```json
{
  "refresh_token": "not_existing_refresh_token"
}
```

Ошибка `403` (reuse detection):

1. Логин -> получите `refresh_1`.
2. `POST /refresh` с `refresh_1` -> получите `refresh_2`.
3. Еще раз отправьте `refresh_1` -> `403`.

## 3.4 Защищенные методы без body

Чек-лист:

1. `GET /api/auth/me` без авторизации -> `401`.
2. `GET /api/auth/me` с валидным `access_token` -> `200`.
3. `POST /api/auth/out` с валидным `access_token` -> `200`.
4. После этого `GET /api/auth/me` тем же token -> `403`.
5. После этого `GET /api/auth/tokens` тем же token -> `403`.
6. Сделайте новый `POST /login`, авторизуйтесь новым access -> `GET /api/auth/tokens` -> `200`.
7. Два логина подряд -> `GET /api/auth/tokens` показывает несколько активных сессий (`200`).
8. `POST /api/auth/out_all` в одной сессии -> в другой сессии `GET /api/auth/me` -> `403`.

## 4. Таблица быстрых причин ошибок

- `401` + `"Отсутствует заголовок Authorization."`
  - Причина: не нажали `Authorize` или токен не применился.
  - Проверьте `Curl`: должен быть `Authorization: Bearer ...`.

- `401` + `"Поле type должно быть равно \"access\"."`
  - Причина: в защищенный метод отправлен refresh token.
  - Решение: использовать `access_token`.

- `403` + `"Текущая сессия отозвана."`
  - Причина: вы уже сделали `POST /out` или `POST /out_all` этим/связанным токеном.
  - Решение: новый `POST /login` и новый access.

- `403` на `/register`
  - Причина: маршрут guest-only, а вы отправили валидный `Authorization`.

## 5. Мини-сценарий "точно рабочая проверка"

1. `POST /api/auth/register` (новый пользователь) -> `201`.
2. `POST /api/auth/login` -> взять `access_token`.
3. `Authorize` -> вставить `access_token`.
4. `GET /api/auth/me` -> `200`.
5. `POST /api/auth/out` -> `200`.
6. `GET /api/auth/me` тем же access -> `403`.
7. `POST /api/auth/login` еще раз -> новый access.
8. `GET /api/auth/tokens` -> `200`.
