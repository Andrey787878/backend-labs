# ЛР12: Attendance Auto Credit

ЛР12 добавляет расчёт студентов, получающих зачёт автоматически, по Excel-файлу посещаемости.

## Где реализация

- `app/attendance_routes.py` - HTTP endpoint.
- `app/attendance_file_parser.py` - чтение и нормализация `.xlsx`.
- `app/attendance_calculator.py` - расчёт процентов и результата.
- `app/attendance_response_builder.py` - сборка итогового JSON.
- `alembic/versions/20260606_0007_add_attendance_permission.py` - permission `calculate-attendance`.
- `scripts/make_lr12_demo_xlsx.py` - генерация demo-файла для Swagger.

## Endpoint

| Метод | URL | Доступ | Ответ |
|---|---|---|---|
| `POST` | `/api/attendance/calculate` | `calculate-attendance` | `200`, JSON |

## Входной файл

Формат: `.xlsx`.

Лист: `Посещаемость`.

Обязательные колонки:

- `Группа`
- `Подгруппа`
- `ФИО`
- `Дата`
- `Время`
- `Тип занятия`
- `Номер занятия`
- `Посещение`
- `Выполнено лаб`
- `Зачёт автоматом`

## Конфигурация

```env
REQUIRED_LABS=5
ATTENDANCE_PERCENT_THRESHOLD=80
UPLOAD_MAX_SIZE_MB=10
```

## Правило результата

`result = true`, если:

- в любой строке студента `Зачёт автоматом = 1/да`;
- или `visit_percent >= ATTENDANCE_PERCENT_THRESHOLD` и `success_labs >= REQUIRED_LABS`.

## Формат ответа

```json
{
  "groups": [
    {
      "group_name": "101б",
      "students": [
        {
          "name": "Иванов Иван Иванович",
          "subgroup": 1,
          "leasons": [],
          "visit_percent": 100,
          "success_labs_percent": 100,
          "success_labs": 5,
          "result": true
        }
      ],
      "result": {
        "success": 1,
        "unsuccessfully": 0
      }
    }
  ],
  "automatic_success_students": [
    {
      "group_name": "101б",
      "name": "Иванов Иван Иванович"
    }
  ]
}
```

Поле `leasons` оставлено с написанием из ТЗ.
