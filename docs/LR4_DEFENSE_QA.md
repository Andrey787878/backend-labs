# ЛР4: короткие ответы для защиты

## Что реализовано в ЛР4?

Автоматическое аудит-логирование мутаций `users`, `roles`, `permissions` (create/update/delete/restore), API истории (`story`) и undo (`restore from log`).

## Как обеспечена транзакционность?

Лог пишется SQLAlchemy listeners внутри той же транзакции, где выполняется мутация. Ошибка на сохранении лога приводит к rollback всей операции.

## Почему `changed_fields` содержит только diff?

В БД храним `before/after`, а при сериализации `ChangeLogDTO` вычисляем различающиеся ключи и отдаем только их.

## Как защищены маршруты истории?

Через RBAC permissions: `get-story-user`, `get-story-role`, `get-story-permission`.

## Как защищен undo?

`POST /api/ref/changelog/{log_id}/restore` проверяет `restore-*` право в зависимости от `entity_type` записи лога.

## Почему добавлены PATCH/DELETE/RESTORE для User?

Чтобы полностью закрыть требование ЛР4 по lifecycle мутациям для всех трех сущностей: `User`, `Role`, `Permission`.

## Где находится реализация ЛР4?

- Миграции: `alembic/versions/20260520_0003_*`, `20260520_0004_*`
- Audit API: `app/audit_routes.py`
- Audit service + undo: `app/audit_service.py`
- Audit listeners: `app/audit_events.py`
- Audit context: `app/audit_context.py`
- Расширение RBAC user lifecycle: `app/rbac_service.py`, `app/rbac_routes.py`
