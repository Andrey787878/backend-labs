# Подготовка к защите: вопросы преподавателя и ответы по реализации

Этот файл сделан как шпаргалка к сдаче: что отвечать кратко и где это подтверждается в коде.

## 0. Бысткая карта системы (что сказать в начале)

Коротко:

- У нас не чисто stateless JWT, а гибрид: JWT + server-side сессии в БД.
- `access_token` используется для доступа к защищенным методам.
- `refresh_token` используется только в `/api/auth/refresh` для ротации пары токенов.
- Любой access дополнительно проверяется по записи `auth_sessions` (revoked/expired).
- При проблемах refresh (reuse/invalid/session mismatch) сессии отзываются по правилам безопасности.

Код:

- Проверка bearer + payload: `app/dependencies.py:153-170`
- Проверка access-сессии в БД: `app/dependencies.py:172-216`
- Refresh-логика и revoke: `app/auth_service.py:177-296`
- Модель сессий: `app/models.py:42-68`

---

## 1. Как пользователь получает `access` без `refresh`?

Короткий ответ:

`access_token` пользователь получает при `POST /api/auth/login` по `username/password`. Refresh для этого не нужен.

Технически:

1. `/login` валидирует запрос и вызывает `auth_service.login_user(...)`.
2. В сервисе проверяются `username/password`.
3. Создается server-side сессия и сразу генерируется пара `access + refresh`.
4. В ответе возвращается `AuthSuccessDTO` с двумя токенами.

Код:

- Роут login: `app/auth_routes.py:99-117`
- Проверка credentials: `app/auth_service.py:101-109`
- Создание токенов/сессии: `app/auth_service.py:110-126`, `app/auth_service.py:298-337`
- Формат ответа (`access_token`, `refresh_token`): `app/dto.py:45-53`

Фрагмент:

```python
# app/auth_service.py:110-116
family_id = uuid4().hex
_, access_token, refresh_token = self._create_session(
    user=user,
    family_id=family_id,
    ip=ip,
    user_agent=user_agent,
)
```

---

## 2. Как `refresh` идентифицирует пользователя?

Короткий ответ:

Теперь refresh подписанный JWT и содержит `sub` (id пользователя) и `access_jti` (идентификатор access-сессии). По ним сервис находит нужную server-side сессию.

Технически:

- При выдаче refresh формируется payload:
  - `sub`
  - `access_jti`
  - `jti`
  - `iat`, `exp`
  - `type=refresh`
- На `/refresh` токен декодируется, затем берется `sub + access_jti` и по ним ищется запись в `auth_sessions`.

Код:

- Создание refresh payload: `app/token_service.py:157-176`
- Обязательные claims refresh: `app/token_service.py:177-225`
- Поиск сессии по `sub + access_jti`: `app/auth_service.py:232-239`

Фрагмент:

```python
# app/token_service.py:165-172
payload = {
    "sub": str(user_id),
    "access_jti": access_jti,
    "jti": secrets.token_hex(16),
    "iat": issued_at,
    "exp": expires_at,
    "type": "refresh",
}
```

---

## 3. Если refresh истек, можно ли получить новый access через `/refresh`?

Короткий ответ:

Нет. Если refresh истек, `/refresh` не даст новую пару. Нужно снова делать `POST /api/auth/login`.

Технически:

- В refresh-потоке проверяется срок refresh по времени в БД и в payload.
- Если refresh просрочен, это ветка invalid/reuse -> сессии отзываются и возвращается `403` (компрометация/недействительность).

Код:

- Проверка `session.refresh_expires_at <= now` и `refresh_payload.exp <= now`: `app/auth_service.py:251-259`
- Реакция (revoke all + 403): `app/auth_service.py:261-269`, `app/auth_routes.py:51-53`

---

## 4. Можно ли залогиниться больше 5 раз?

Короткий ответ:

`POST /login` можно вызвать сколько угодно раз. Но одновременно активных сессий на пользователя будет максимум `MAX_ACTIVE_SESSIONS=5`.

Технически:

- После каждого логина сервис вызывает `_enforce_session_limit(user.id)`.
- Если активных сессий больше лимита, самые старые отзываются.

Код:

- Лимит после login: `app/auth_service.py:118-120`
- Сам алгоритм лимита: `app/auth_service.py:379-403`
- Конфиг лимита (`5`): `app/config.py:52-56`

---

## 5. Что будет, если отправить refresh от 1-й авторизации после 6 логинов?

Короткий ответ:

С высокой вероятностью он уже отозван лимитом сессий, поэтому `/refresh` вернет `403` и отзовет все текущие сессии пользователя как возможную компрометацию.

Почему так:

1. После 6-го логина лимит оставляет только 5 самых новых сессий.
2. Самая старая (часто это 1-я) помечается `revoked_reason="session_limit_exceeded"`.
3. Если потом использовать ее refresh, проверка увидит `session.revoked_at is not None` и сработает ветка `revoke all`.

Код:

- Отзыв старых при переполнении: `app/auth_service.py:397-403`
- Проверка `session.revoked_at is not None` в refresh: `app/auth_service.py:255-259`
- `revoke all` на invalid/reuse: `app/auth_service.py:261-269`

---

## 6. Что означает `401` при `token not found`?

Короткий ответ:

`401` означает: клиент не авторизован для этого запроса (токен отсутствует/битый/не распознан).

Где именно:

- Для access-защищенных методов:
  - нет заголовка `Authorization` -> `401`.
  - сессия для access `jti` не найдена -> `401`.
- Для refresh:
  - если токен вообще невалидный и не удается связать его с конкретной сессией -> `401`.

Код:

- Нет заголовка: `app/dependencies.py:136-141`
- Access session not found: `app/dependencies.py:184-189`
- Refresh completely invalid -> `401`: `app/auth_service.py:223`, `app/auth_routes.py:49-50`

---

## 7. Почему в access нет `sid`, а есть `jti`?

Короткий ответ:

В этой реализации `jti` и есть идентификатор access-сессии (`access_jti`), по которому идет lookup в БД. Отдельное поле `sid` не обязательно.

Код:

- Access содержит `jti`: `app/token_service.py:60-66`
- Lookup в БД идет по `payload.jti`: `app/dependencies.py:178`
- В `auth_sessions` хранится `access_jti`: `app/models.py:52`

---

## 8. Чем access и refresh отличаются по назначению?

Короткий ответ:

- `access_token`: доступ к защищенным методам (`/me`, `/out`, `/tokens`, `/out_all`).
- `refresh_token`: только обновление пары токенов через `/refresh`.

Код:

- Защищенные методы завязаны на `get_current_user_context`: `app/auth_routes.py:120-160`
- `/refresh` принимает `RefreshRequest.refresh_token`: `app/auth_routes.py:170-187`, `app/schemas.py:128-141`

---

## 9. Где хранится refresh в БД? Храним ли мы raw refresh?

Короткий ответ:

Raw refresh в БД не хранится. Хранится только HMAC-хеш в `auth_sessions.refresh_hash`.

Код:

- Поле `refresh_hash`: `app/models.py:53`
- Хеширование: `app/token_service.py:262-270`
- Сохранение хеша в сессию: `app/auth_service.py:317-327`

---

## 10. Почему `/register` может вернуть `422` на дубли username/email?

Короткий ответ:

Потому что дубликаты проверяются еще на этапе request-валидации (до сервиса), и ошибка возвращается как validation error по полям.

Код:

- Dependency-валидация уникальности: `app/dependencies.py:46-90`
- Подключение dependency в роуте: `app/auth_routes.py:85-94`
- Дополнительно DB-уникальность индексами: `app/models.py:31-34`

---

## 11. Почему `POST /register` с access-токеном дает `403`?

Короткий ответ:

`/register` реализован как guest-only: если уже есть валидная активная сессия, доступ запрещен.

Код:

- guest-only dependency на роуте: `app/auth_routes.py:85-90`
- Логика guest-only: `app/dependencies.py:93-129`

---

## 12. В чем разница `401` и `403` в проекте?

Коротко:

- `401 Unauthorized`: не смогли аутентифицировать (нет/битый токен, неверные credentials).
- `403 Forbidden`: пользователь распознан, но доступ запрещен (revoked session, guest-only, refresh compromise).

Код-примеры:

- `401` при неверном логине: `app/auth_routes.py:47-48`
- `403` при revoked access session: `app/dependencies.py:198-203`
- `403` при compromised refresh: `app/auth_routes.py:51-53`

---

## 13. Что делает `/out` и `/out_all`?

Коротко:

- `/out`: отзывает только текущую сессию (по access `jti`).
- `/out_all`: отзывает все активные сессии пользователя.

Код:

- `/out` роут: `app/auth_routes.py:129-145`
- `logout_current_session`: `app/auth_service.py:154-168`
- `/out_all` роут: `app/auth_routes.py:156-167`
- `logout_all_sessions`: `app/auth_service.py:170-175`

---

## 14. Что такое refresh rotation и one-time refresh в этой реализации?

Короткий ответ:

Каждый refresh одноразовый: после успешного использования старая refresh-сессия помечается использованной и отзывается, создается новая сессия с новой парой токенов.

Код:

- Пометка `refresh_used_at`: `app/auth_service.py:275`
- Отзыв старой сессии при ротации: `app/auth_service.py:277-279`
- Создание новой пары: `app/auth_service.py:280-287`

---

## 15. Что если refresh подпись невалидна, но из payload читаются `sub/access_jti`?

Короткий ответ:

Это трактуется как подозрительный случай. Если такой токен можно связать с существующей сессией пользователя, сервис отзывает все сессии пользователя и возвращает `403`.

Код:

- Decode refresh с перехватом ошибки: `app/auth_service.py:187-193`
- Unverified identity extract: `app/token_service.py:226-260`
- Поиск связанной сессии и `revoke all`: `app/auth_service.py:196-221`

---

## 16. Есть ли сейчас rate limiter?

Короткий ответ:

Нет, rate limiter убран из текущей реализации.

Что ограничивает злоупотребление сессиями:

- лимит одновременно активных сессий (`MAX_ACTIVE_SESSIONS`), а не частота вызова `/login`.

Код:

- Лимит сессий: `app/config.py:52-56`, `app/auth_service.py:379-403`

---

## 17. Как объяснить преподавателю путь проверки access на защищенном endpoint?

Готовый ответ:

1. Клиент передает `Authorization: Bearer <access_token>`.
2. Проверяется формат Bearer, header JWT (`alg/typ`), подпись и срок действия.
3. Из payload берется `sub` и `jti`.
4. По `jti` ищется server-side сессия в `auth_sessions`.
5. Проверяем, что сессия принадлежит `sub`, не отозвана и не истекла.
6. Только после этого endpoint выполняется.

Код:

- Bearer extraction: `app/dependencies.py:132-150`
- JWT header/payload проверка: `app/dependencies.py:153-170`
- Server-side session check: `app/dependencies.py:172-216`

---

## 18. Какие обязательные поля у токенов (что могут попросить перечислить)?

`access_token`:

- `sub`, `jti`, `iat`, `exp`, `type=access`.

`refresh_token`:

- `sub`, `access_jti`, `jti`, `iat`, `exp`, `type=refresh`.

Код:

- Access require claims: `app/token_service.py:121-126`, `app/token_service.py:132-155`
- Refresh require claims: `app/token_service.py:182-190`, `app/token_service.py:196-224`

---

## 19. Что из данных клиента сохраняется и зачем?

Коротко:

В сессию сохраняются `ip` и `user_agent` как метаданные (для аудита/управления сессиями), но не в JWT.

Код:

- Комментарий в создании сессии: `app/auth_service.py:322-334`
- Валидация IP/UA: `app/auth_service.py:455-491`

---

## 20. Что отвечать на вопрос “почему вы не полагаетесь только на JWT?”

Готовый ответ:

Потому что только JWT не дает мгновенно отзывать сессию. У нас server-side `auth_sessions` позволяет:

- инвалидировать токен сразу (`/out`, `/out_all`);
- контролировать лимит одновременных сессий;
- делать refresh rotation/reuse detection;
- реагировать на компрометацию `revoke all`.

Код:

- Проверка доступа через БД-сессию: `app/dependencies.py:172-216`
- Отзывы/лимит/refresh-rotation: `app/auth_service.py:154-175`, `app/auth_service.py:177-296`, `app/auth_service.py:379-403`

---

## 21. Мини-шпаргалка ответов “в одну фразу”

- Как получить новый access? -> Через `/refresh` с валидным неиспользованным refresh; если refresh истек, только новый `/login`.
- Можно ли логиниться >5 раз? -> Да, но активных сессий максимум 5, старые отзываются автоматически.
- Почему `GET /me` иногда 401, иногда 403? -> `401` при проблеме аутентификации, `403` когда сессия уже отозвана/запрещена.
- Как refresh находит пользователя? -> По `sub` + `access_jti` внутри подписанного refresh JWT.
- Где хранятся токены? -> Access/refresh выдаются клиенту, в БД хранится только `refresh_hash` и метаданные сессии.

---

## 22. Вопросы, которые еще могут задать

1. Почему уникальность username/email проверяется и в валидации, и индексами БД?
Ответ: pre-check дает понятный `422` по полям, а БД-индекс остается последней гарантией целостности при гонках.
Код: `app/dependencies.py:46-90`, `app/models.py:31-34`.

2. Что будет, если отправить access вместо refresh в `/refresh`?
Ответ: провалится проверка claim `type`, вернется ошибка невалидного refresh.
Код: `app/token_service.py:196-199`.

3. Почему в `refresh` сначала decode c `verify_exp=False`, а потом отдельные проверки?
Ответ: чтобы корректно обработать incident-response сценарий и при необходимости сделать targeted revoke-all даже когда токен уже не проходит стандартную валидацию.
Код: `app/auth_service.py:187-223`.

4. Как устроена транзакционная надежность?
Ответ: все операции коммитятся через единый `_commit_or_rollback`, при ошибках БД идет rollback и понятная доменная ошибка.
Код: `app/auth_service.py:404-415`.

5. Почему `register` делает `403` для авторизованного пользователя, а не `401`?
Ответ: потому что пользователь аутентифицирован, но действие ему запрещено по правилу guest-only.
Код: `app/dependencies.py:126-129`.

---

## 23. Практический сценарий для демонстрации на защите

1. `POST /register` -> `201`.
2. `POST /login` -> получить `access_1`, `refresh_1`.
3. `GET /me` с `access_1` -> `200`.
4. `POST /refresh` с `refresh_1` -> получить `access_2`, `refresh_2`.
5. Повторно `POST /refresh` с `refresh_1` -> `403` (reuse/compromise).
6. `POST /login` 6 раз подряд -> активных сессий останется 5.
7. Попробовать refresh от самой старой сессии -> `403` и отзыв активных сессий.

Подтверждающий код:

- login + лимит: `app/auth_service.py:94-126`, `app/auth_service.py:379-403`
- refresh rotation + reuse reaction: `app/auth_service.py:275-290`, `app/auth_service.py:251-269`

---

## 24. Если попросят показать “где это в Swagger”

- Защищенные методы без body: `GET /me`, `POST /out`, `GET /tokens`, `POST /out_all`.
- Токен вводится через `Authorize` (global security) или в поле `Authorization` конкретного метода.
- Формат заголовка: `Authorization: Bearer <access_token>`.

Код и документы:

- Security dependency (`HTTPBearer`): `app/dependencies.py:32`, `app/dependencies.py:153-170`
- Swagger checks: `docs/AUTH_SWAGGER_CHECKS.md:5-9`, `docs/AUTH_SWAGGER_CHECKS.md:189-196`

---

## 25. Что повторить перед сдачей

- Разница `401` vs `403`.
- Отличие access и refresh, и где какой используется.
- Почему храним refresh как hash.
- Как работает refresh rotation и почему reuse => revoke all.
- Почему максимум 5 активных сессий и что происходит при 6-й авторизации.

