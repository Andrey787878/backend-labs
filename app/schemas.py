import re
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.dto import (
    ChangePasswordInputDTO,
    LoginInputDTO,
    RefreshInputDTO,
    RegisterInputDTO,
)


USERNAME_REGEX = re.compile(r"^[A-Z][A-Za-z]{6,}$")
BIRTHDAY_FORMAT_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_username(value: str) -> str:
    if not USERNAME_REGEX.fullmatch(value):
        raise ValueError(
            "username должен содержать только латинские буквы, начинаться с заглавной "
            "буквы и иметь длину не менее 7 символов."
        )
    return value


def _validate_non_blank(value: str, field_name: str) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} не должен быть пустым.")
    return value


def _validate_password_complexity(value: str) -> str:
    if len(value) < 8:
        raise ValueError("password должен содержать минимум 8 символов.")
    if not any(char.isdigit() for char in value):
        raise ValueError("password должен содержать минимум одну цифру.")
    if not any(char.islower() for char in value):
        raise ValueError("password должен содержать минимум один символ в нижнем регистре.")
    if not any(char.isupper() for char in value):
        raise ValueError("password должен содержать минимум один символ в верхнем регистре.")
    if not any(not char.isalnum() for char in value):
        raise ValueError("password должен содержать минимум один специальный символ.")
    return value


def _validate_min_age_14(value: date) -> date:
    today = date.today()
    age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
    if age < 14:
        raise ValueError("Возраст на момент регистрации должен быть не менее 14 лет.")
    return value


class LoginRequest(BaseModel):
    """Логин"""

    model_config = ConfigDict(extra="forbid")

    username: str = Field(..., min_length=7, max_length=64)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return _validate_username(value)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return _validate_password_complexity(value)

    def to_dto(self) -> LoginInputDTO:
        return LoginInputDTO(
            username=self.username,
            password=self.password,
        )


class RegisterRequest(BaseModel):
    """Регистрация"""

    model_config = ConfigDict(extra="forbid")

    username: str = Field(..., min_length=7, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    c_password: str = Field(..., min_length=8, max_length=128)
    birthday: date

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return _validate_username(value)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return _validate_password_complexity(value)

    @field_validator("birthday", mode="before")
    @classmethod
    def validate_birthday_format(cls, value: Any) -> Any:
        if isinstance(value, str) and not BIRTHDAY_FORMAT_REGEX.fullmatch(value):
            raise ValueError("birthday должен быть в формате YYYY-MM-DD.")
        return value

    @field_validator("birthday")
    @classmethod
    def validate_birthday_age(cls, value: date) -> date:
        return _validate_min_age_14(value)

    @model_validator(mode="after")
    def validate_password_match(self) -> "RegisterRequest":
        if self.password != self.c_password:
            raise ValueError("c_password должен совпадать с password.")
        return self

    def to_dto(self) -> RegisterInputDTO:
        return RegisterInputDTO(
            username=self.username,
            email=self.email,
            password=self.password,
            birthday=self.birthday,
        )


class RefreshRequest(BaseModel):
    """Обновления пары токенов"""

    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(..., min_length=1)

    @field_validator("refresh_token")
    @classmethod
    def validate_refresh_token(cls, value: str) -> str:
        return _validate_non_blank(value, "refresh_token").strip()

    def to_dto(self) -> RefreshInputDTO:
        return RefreshInputDTO(refresh_token=self.refresh_token)


class ChangePasswordRequest(BaseModel):
    """Изменение пароля"""

    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(..., min_length=8, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)
    c_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return _validate_password_complexity(value)

    @model_validator(mode="after")
    def validate_password_match(self) -> "ChangePasswordRequest":
        if self.new_password != self.c_password:
            raise ValueError("c_password должен совпадать с new_password.")
        return self

    def to_dto(self) -> ChangePasswordInputDTO:
        return ChangePasswordInputDTO(
            current_password=self.current_password,
            new_password=self.new_password,
        )
