from __future__ import annotations

from app.attendance_calculator import CalculatedStudent
from app.dto import (
    AttendanceAutoSuccessStudentDTO,
    AttendanceCalculateResponseDTO,
    AttendanceGroupDTO,
    AttendanceGroupResultDTO,
)


class AttendanceResponseBuilder:
    """Собирает рассчитанных студентов в итоговый JSON-ответ ЛР12."""

    def build(self, calculated_students: list[CalculatedStudent]) -> AttendanceCalculateResponseDTO:
        """Группирует студентов по группам и добавляет список зачётников."""
        group_map: dict[str, list[CalculatedStudent]] = {}
        for calculated_student in calculated_students:
            group_map.setdefault(calculated_student.group_name, []).append(calculated_student)

        groups: list[AttendanceGroupDTO] = []
        automatic_success_students: list[AttendanceAutoSuccessStudentDTO] = []

        for group_name in sorted(group_map):
            group_students = sorted(
                group_map[group_name],
                key=lambda item: item.student.name,
            )
            success_count = sum(1 for item in group_students if item.student.result)

            for item in group_students:
                if item.student.result:
                    automatic_success_students.append(
                        AttendanceAutoSuccessStudentDTO(
                            group_name=group_name,
                            name=item.student.name,
                        )
                    )

            groups.append(
                AttendanceGroupDTO(
                    group_name=group_name,
                    students=[item.student for item in group_students],
                    result=AttendanceGroupResultDTO(
                        success=success_count,
                        unsuccessfully=len(group_students) - success_count,
                    ),
                )
            )

        return AttendanceCalculateResponseDTO(
            groups=groups,
            automatic_success_students=sorted(
                automatic_success_students,
                key=lambda item: (item.group_name, item.name),
            ),
        )
