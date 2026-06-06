from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.dto import AttendanceLessonDTO, AttendanceRowDTO, AttendanceStudentDTO


@dataclass(frozen=True)
class LessonKey:
    """Уникальный ключ занятия по требованиям ЛР12."""

    date: str
    time: str
    lesson_type: str
    number: int


@dataclass(frozen=True)
class CalculatedStudent:
    """Студент с рассчитанным результатом и названием группы."""

    group_name: str
    student: AttendanceStudentDTO


class AttendanceCalculator:
    """Рассчитывает посещаемость, выполненные лабораторные и автоматический зачёт."""

    def __init__(self, *, required_labs: int, attendance_percent_threshold: int) -> None:
        self._required_labs = required_labs
        self._attendance_percent_threshold = attendance_percent_threshold

    def calculate(self, rows: list[AttendanceRowDTO]) -> list[CalculatedStudent]:
        """Возвращает рассчитанных студентов по всем строкам файла."""
        lesson_keys = self._collect_lesson_keys(rows)
        grouped_rows = self._group_student_rows(rows)

        calculated: list[CalculatedStudent] = []
        for group_name, student_name in sorted(grouped_rows):
            student_rows = grouped_rows[(group_name, student_name)]
            calculated.append(
                CalculatedStudent(
                    group_name=group_name,
                    student=self._calculate_student(
                        student_name=student_name,
                        student_rows=student_rows,
                        lesson_keys=lesson_keys,
                    ),
                )
            )

        return calculated

    def _calculate_student(
        self,
        *,
        student_name: str,
        student_rows: list[AttendanceRowDTO],
        lesson_keys: list[LessonKey],
    ) -> AttendanceStudentDTO:
        subgroup = student_rows[0].subgroup
        success_labs = max(row.success_labs for row in student_rows)
        already_auto_credit = any(row.already_auto_credit for row in student_rows)
        visited_lessons = {
            self._lesson_key(row)
            for row in student_rows
            if row.visited
        }
        lessons = [
            AttendanceLessonDTO(
                date=lesson_key.date,
                time=lesson_key.time,
                type=lesson_key.lesson_type,
                number=lesson_key.number,
                subgroups=subgroup,
                visit=lesson_key in visited_lessons,
            )
            for lesson_key in lesson_keys
        ]

        total_lessons = len(lesson_keys)
        visited_count = sum(1 for lesson in lessons if lesson.visit)
        visit_percent = round((visited_count / total_lessons) * 100) if total_lessons else 0
        success_labs_percent = round((success_labs / self._required_labs) * 100)
        result = already_auto_credit or (
            visit_percent >= self._attendance_percent_threshold
            and success_labs >= self._required_labs
        )

        return AttendanceStudentDTO(
            name=student_name,
            subgroup=subgroup,
            leasons=lessons,
            visit_percent=visit_percent,
            success_labs_percent=success_labs_percent,
            success_labs=success_labs,
            result=result,
        )

    def _collect_lesson_keys(self, rows: list[AttendanceRowDTO]) -> list[LessonKey]:
        lesson_keys = {self._lesson_key(row) for row in rows}
        return sorted(lesson_keys, key=self._lesson_sort_key)

    @staticmethod
    def _group_student_rows(rows: list[AttendanceRowDTO]) -> dict[tuple[str, str], list[AttendanceRowDTO]]:
        grouped_rows: dict[tuple[str, str], list[AttendanceRowDTO]] = {}
        for row in rows:
            key = (row.group_name, row.student_name)
            grouped_rows.setdefault(key, []).append(row)
        return grouped_rows

    @staticmethod
    def _lesson_key(row: AttendanceRowDTO) -> LessonKey:
        return LessonKey(
            date=row.date,
            time=row.time,
            lesson_type=row.lesson_type,
            number=row.lesson_number,
        )

    @staticmethod
    def _lesson_sort_key(lesson_key: LessonKey) -> tuple[datetime, str, int]:
        lesson_datetime = datetime.strptime(
            f"{lesson_key.date} {lesson_key.time}",
            "%d.%m.%Y %H:%M",
        )
        return lesson_datetime, lesson_key.lesson_type, lesson_key.number
