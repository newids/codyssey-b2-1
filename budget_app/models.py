"""데이터 구조(모델). 모두 불변(frozen) dataclass 이며 생성 시점에 스스로를 검증한다."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .validators import (
    TRANSACTION_TYPES,
    parse_category_name,
    parse_date,
    parse_month,
    parse_recurring_day,
)

TRANSACTION_ID_PREFIX = "TX-"
RECURRING_ID_PREFIX = "RC-"
EXPENSE = "expense"
INCOME = "income"

_ID_NUMBER_PATTERN = re.compile(r"[A-Z]+-(\d+)")


def format_transaction_id(sequence: int) -> str:
    return f"{TRANSACTION_ID_PREFIX}{sequence:06d}"


def format_recurring_id(sequence: int) -> str:
    return f"{RECURRING_ID_PREFIX}{sequence:04d}"


def id_number(identifier: str) -> int:
    """'TX-000012' -> 12. 형식이 다르면 0."""
    matched = _ID_NUMBER_PATTERN.fullmatch(identifier)
    return int(matched.group(1)) if matched else 0


def _validate_money_fields(type_: str, amount: int, category: str) -> None:
    if type_ not in TRANSACTION_TYPES:
        raise ValidationError(
            f"허용되지 않은 타입입니다: {type_}", hint="income 또는 expense 를 사용하세요."
        )
    if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
        raise ValidationError("금액은 0보다 큰 정수여야 합니다.", hint="예: 15000")
    parse_category_name(category)


@dataclass(frozen=True)
class TransactionInput:
    """아직 id 가 없는 거래(저장 요청)."""

    type: str
    date: str
    amount: int
    category: str
    memo: str = ""
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_money_fields(self.type, self.amount, self.category)
        parse_date(self.date)


@dataclass(frozen=True)
class Transaction:
    """저장된 거래 1건."""

    id: str
    type: str
    date: str
    amount: int
    category: str
    memo: str = ""
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_money_fields(self.type, self.amount, self.category)
        parse_date(self.date)

    @property
    def month(self) -> str:
        return self.date[:7]

    @property
    def sort_key(self) -> tuple[str, int]:
        """최신순 정렬 기준: 날짜가 같으면 나중에 만든 id 가 더 최신이다."""
        return self.date, id_number(self.id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "date": self.date,
            "amount": self.amount,
            "category": self.category,
            "memo": self.memo,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Transaction:
        return cls(
            id=str(raw["id"]),
            type=raw["type"],
            date=raw["date"],
            amount=raw["amount"],
            category=raw["category"],
            memo=str(raw.get("memo", "")),
            tags=tuple(str(tag) for tag in raw.get("tags", ())),
        )

    @classmethod
    def from_input(cls, tx_id: str, data: TransactionInput) -> Transaction:
        return cls(
            id=tx_id,
            type=data.type,
            date=data.date,
            amount=data.amount,
            category=data.category,
            memo=data.memo,
            tags=data.tags,
        )


@dataclass(frozen=True)
class Budget:
    """월 예산."""

    month: str
    amount: int

    def __post_init__(self) -> None:
        parse_month(self.month)
        if isinstance(self.amount, bool) or not isinstance(self.amount, int) or self.amount <= 0:
            raise ValidationError("예산은 0보다 큰 정수여야 합니다.", hint="예: --amount 500000")

    def to_dict(self) -> dict[str, Any]:
        return {"month": self.month, "amount": self.amount}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Budget:
        return cls(month=raw["month"], amount=raw["amount"])


@dataclass(frozen=True)
class RecurringRule:
    """매월 같은 날 반복되는 거래 규칙(월급, 월세 등)."""

    id: str
    day: int
    type: str
    amount: int
    category: str
    memo: str = ""

    def __post_init__(self) -> None:
        _validate_money_fields(self.type, self.amount, self.category)
        parse_recurring_day(str(self.day))

    @property
    def marker_tag(self) -> str:
        """이 규칙으로 생성된 거래에 붙는 태그(중복 생성 방지에 사용)."""
        return f"recurring:{self.id}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "day": self.day,
            "type": self.type,
            "amount": self.amount,
            "category": self.category,
            "memo": self.memo,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> RecurringRule:
        return cls(
            id=str(raw["id"]),
            day=raw["day"],
            type=raw["type"],
            amount=raw["amount"],
            category=raw["category"],
            memo=str(raw.get("memo", "")),
        )


@dataclass(frozen=True)
class SearchCriteria:
    """검색 조건. None 인 항목은 조건에서 제외한다."""

    date_from: str | None = None
    date_to: str | None = None
    category: str | None = None
    type: str | None = None
    keyword: str | None = None
    tag: str | None = None
    min_amount: int | None = None
    max_amount: int | None = None

    def __post_init__(self) -> None:
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValidationError(
                f"시작일({self.date_from})이 종료일({self.date_to})보다 늦습니다.",
                hint="--from 은 --to 보다 같거나 빠른 날짜여야 합니다.",
            )
        if (
            self.min_amount is not None
            and self.max_amount is not None
            and self.min_amount > self.max_amount
        ):
            raise ValidationError(
                f"최소 금액({self.min_amount:,})이 최대 금액({self.max_amount:,})보다 큽니다.",
                hint="--min-amount 는 --max-amount 보다 같거나 작아야 합니다.",
            )

    def matches(self, tx: Transaction) -> bool:
        if self.date_from and tx.date < self.date_from:
            return False
        if self.date_to and tx.date > self.date_to:
            return False
        if self.category and tx.category != self.category:
            return False
        if self.type and tx.type != self.type:
            return False
        if self.keyword and self.keyword.lower() not in tx.memo.lower():
            return False
        if self.tag and self.tag not in tx.tags:
            return False
        if self.min_amount is not None and tx.amount < self.min_amount:
            return False
        if self.max_amount is not None and tx.amount > self.max_amount:
            return False
        return True


@dataclass(frozen=True)
class MonthlySummary:
    """월별 요약 결과."""

    month: str
    count: int
    total_income: int
    total_expense: int
    top_expenses: tuple[tuple[str, int], ...]
    budget: int | None = None

    @property
    def has_data(self) -> bool:
        return self.count > 0

    @property
    def balance(self) -> int:
        return self.total_income - self.total_expense

    @property
    def usage_rate(self) -> float | None:
        """예산 대비 지출 사용률(%). 예산이 없으면 None."""
        if self.budget is None:
            return None
        return self.total_expense / self.budget * 100

    @property
    def is_over_budget(self) -> bool:
        return self.budget is not None and self.total_expense > self.budget
