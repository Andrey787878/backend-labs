# LR12 Excel Demo Files

Файлы для демонстрации ручки `POST /api/attendance/calculate` в Swagger.

| Файл | Что показывает | Ожидаемый результат |
| --- | --- | --- |
| `01_valid_attendance.xlsx` | Полный успешный расчет: несколько групп, пустая подгруппа, авто-зачет, одинаковое ФИО в разных группах | `200 OK` |
| `02_missing_sheet.xlsx` | Нет листа `Посещаемость` | `422` |
| `03_missing_fio_header.xlsx` | Нет обязательной колонки `ФИО` | `422` |
| `04_bad_lesson_type.xlsx` | Неверный тип занятия `seminar` | `422` |
| `05_bad_date.xlsx` | Неверный формат даты | `422` |
| `06_bad_subgroup.xlsx` | Неверная подгруппа `0` | `422` |
| `07_broken_not_excel.xlsx` | Расширение `.xlsx`, но внутри не Excel | `422`, без `500` |

Для показа: сначала авторизуйся админом, затем в Swagger открой `attendance` -> `POST /api/attendance/calculate` и загрузи файл в поле `file`.
