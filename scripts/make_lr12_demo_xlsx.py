from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook


OUTPUT_PATH = Path("tmp/lr12_attendance_demo.xlsx")


def main() -> None:
    """Создаёт demo .xlsx для проверки ЛР12 через Swagger."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Посещаемость"
    worksheet.append(
        [
            "Группа",
            "Подгруппа",
            "ФИО",
            "Дата",
            "Время",
            "Тип занятия",
            "Номер занятия",
            "Посещение",
            "Выполнено лаб",
            "Зачёт автоматом",
        ]
    )

    lessons = [
        ("23.09.2024", "18:15", "lect", 1),
        ("23.09.2024", "19:45", "lab", 1),
        ("30.09.2024", "18:15", "lect", 2),
        ("30.09.2024", "19:45", "lab", 2),
        ("07.10.2024", "18:15", "lab", 3),
    ]
    students = [
        ("101б", 1, "Иванов Иван Иванович", [1, 1, 1, 1, 1], 5, 0),
        ("101б", "", "Петров Пётр Петрович", [1, 0, 0, 0, 0], 2, 0),
        ("102б", 2, "Сидорова Анна Сергеевна", ["нет", "нет", "нет", "нет", "нет"], 0, "да"),
    ]

    for group_name, subgroup, student_name, visits, success_labs, already_auto_credit in students:
        for lesson, visit in zip(lessons, visits, strict=True):
            date, time, lesson_type, lesson_number = lesson
            worksheet.append(
                [
                    group_name,
                    subgroup,
                    student_name,
                    date,
                    time,
                    lesson_type,
                    lesson_number,
                    visit,
                    success_labs,
                    already_auto_credit,
                ]
            )

    workbook.save(OUTPUT_PATH)


if __name__ == "__main__":
    main()
