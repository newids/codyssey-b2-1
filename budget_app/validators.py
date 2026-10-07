"""문자열 입력을 검증해 정규화된 값으로 바꾸는 순수 함수 모음.

대화형 입력, 옵션 인자, CSV 가져오기, 저장 파일 읽기가 모두 같은 규칙을 쓴다.
"""

from __future__ import annotations

import calendar
import re
import unicodedata
from datetime import date

from .errors import ValidationError

TRANSACTION_TYPES: tuple[str, ...] = ("income", "expense")
MAX_CATEGORY_LENGTH = 30
FORBIDDEN_CATEGORY_CHARS = ",|"
MIN_RECURRING_DAY = 1
MAX_RECURRING_DAY = 31

MAX_AMOUNT_DIGITS = 15

_DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_MONTH_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}")
_DIGITS_PATTERN = re.compile(rf"[0-9]{{1,{MAX_AMOUNT_DIGITS}}}")
_GROUPED_DIGITS_PATTERN = re.compile(r"[0-9]{1,3}(,[0-9]{3})+")


def parse_date(text: str) -> str:
    value = text.strip()
    if not _DATE_PATTERN.fullmatch(value) or not _is_real_date(value):
        raise ValidationError(
            "날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).", hint="예: 2024-01-15"
        )
    return value


def parse_month(text: str) -> str:
    value = text.strip()
    if not _MONTH_PATTERN.fullmatch(value) or not _is_real_date(f"{value}-01"):
        raise ValidationError(
            "월 형식이 올바르지 않습니다 (YYYY-MM).", hint="예: 2024-01"
        )
    return value


def month_range(month: str) -> tuple[str, str]:
    """'2024-02' -> ('2024-02-01', '2024-02-29')"""
    year, month_number = (int(part) for part in month.split("-"))
    last_day = calendar.monthrange(year, month_number)[1]
    return f"{month}-01", f"{month}-{last_day:02d}"


def parse_amount(text: str) -> int:
    value = text.strip()
    if _GROUPED_DIGITS_PATTERN.fullmatch(value):
        value = value.replace(",", "")
    if not _DIGITS_PATTERN.fullmatch(value) or int(value) <= 0:
        raise ValidationError(
            f"금액은 0보다 큰 정수여야 합니다 (최대 {MAX_AMOUNT_DIGITS}자리).",
            hint="예: 15000 (기호나 소수점 없이 입력)",
        )
    return int(value)


def parse_type(text: str) -> str:
    value = text.strip().lower()
    if value not in TRANSACTION_TYPES:
        raise ValidationError(
            f"타입은 {' 또는 '.join(TRANSACTION_TYPES)} 만 사용할 수 있습니다.",
            hint="수입은 income, 지출은 expense 를 입력하세요.",
        )
    return value


def parse_tags(text: str) -> tuple[str, ...]:
    """쉼표로 구분된 문자열을 중복 없는 태그 튜플로 바꾼다(입력 순서 유지)."""
    names = (part.strip() for part in text.split(","))
    return tuple(dict.fromkeys(name for name in names if name))


def normalize_name(text: str) -> str:
    """앞뒤 공백을 떼고 한글 자모 분리(NFD) 표기를 완성형(NFC)으로 통일한다."""
    return unicodedata.normalize("NFC", text.strip())


def parse_category_name(text: str) -> str:
    value = normalize_name(text)
    if not value:
        raise ValidationError("카테고리명이 비어 있습니다.", hint="예: food")
    if len(value) > MAX_CATEGORY_LENGTH:
        raise ValidationError(
            f"카테고리명은 {MAX_CATEGORY_LENGTH}자 이하여야 합니다.",
            hint="더 짧은 이름을 사용하세요.",
        )
    if any(ch in FORBIDDEN_CATEGORY_CHARS or ch.isspace() for ch in value):
        raise ValidationError(
            "카테고리명에는 공백, 쉼표(,), 세로선(|)을 쓸 수 없습니다.",
            hint="예: food, living-cost",
        )
    return value


def parse_positive_int(text: str, label: str) -> int:
    value = text.strip()
    if not _DIGITS_PATTERN.fullmatch(value) or int(value) <= 0:
        raise ValidationError(
            f"{label} 값은 1 이상의 정수여야 합니다.", hint=f"예: {label} 10"
        )
    return int(value)


def parse_recurring_day(text: str) -> int:
    value = text.strip()
    if not _DIGITS_PATTERN.fullmatch(value) or not (
        MIN_RECURRING_DAY <= int(value) <= MAX_RECURRING_DAY
    ):
        raise ValidationError(
            f"반복 일자는 {MIN_RECURRING_DAY}~{MAX_RECURRING_DAY} 사이의 정수여야 합니다.",
            hint="예: --day 25 (해당 월에 없는 날짜는 말일로 조정됩니다)",
        )
    return int(value)


def _is_real_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True
