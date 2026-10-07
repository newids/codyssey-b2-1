"""화면 출력용 문자열을 만든다(외부 라이브러리 없이 한글 폭까지 고려한 표 정렬)."""

from __future__ import annotations

import unicodedata
from typing import Sequence

from .config import BUDGET_WARNING_RATE
from .models import MonthlySummary, RecurringRule, Transaction

COLUMN_SEPARATOR = " | "
TRANSACTION_HEADERS: tuple[str, ...] = ("ID", "날짜", "타입", "카테고리", "금액", "메모", "태그")
AMOUNT_COLUMN = 4
_WIDE_CHARACTER_KINDS = ("W", "F")


def display_width(text: str) -> int:
    """터미널에서 차지하는 칸 수. 한글 같은 전각 문자는 2칸으로 센다."""
    return sum(
        2 if unicodedata.east_asian_width(ch) in _WIDE_CHARACTER_KINDS else 1 for ch in text
    )


def printable(text: str) -> str:
    """줄바꿈과 제어 문자를 공백으로 바꿔 표가 깨지거나 터미널 제어 코드가 실행되지 않게 한다."""
    return "".join(" " if unicodedata.category(ch) == "Cc" else ch for ch in text)


def pad(text: str, width: int, align_right: bool = False) -> str:
    padding = " " * max(width - display_width(text), 0)
    return padding + text if align_right else text + padding


def format_table(
    headers: Sequence[str], rows: Sequence[Sequence[str]], right_aligned: frozenset[int]
) -> list[str]:
    rows = [[printable(cell) for cell in row] for row in rows]
    widths = [
        max(display_width(row[index]) for row in (headers, *rows))
        for index in range(len(headers))
    ]

    def render(row: Sequence[str]) -> str:
        cells = (
            pad(cell, widths[index], align_right=index in right_aligned)
            for index, cell in enumerate(row)
        )
        return COLUMN_SEPARATOR.join(cells).rstrip()

    divider = "-+-".join("-" * width for width in widths)
    return [render(headers), divider, *(render(row) for row in rows)]


def format_transactions(transactions: Sequence[Transaction]) -> list[str]:
    rows = [
        (tx.id, tx.date, tx.type, tx.category, str(tx.amount), tx.memo, ",".join(tx.tags))
        for tx in transactions
    ]
    return format_table(TRANSACTION_HEADERS, rows, frozenset({AMOUNT_COLUMN}))


def format_recurring_rules(rules: Sequence[RecurringRule]) -> list[str]:
    headers = ("ID", "일자", "타입", "카테고리", "금액", "메모")
    rows = [
        (rule.id, f"매월 {rule.day}일", rule.type, rule.category, str(rule.amount), rule.memo)
        for rule in rules
    ]
    return format_table(headers, rows, frozenset({AMOUNT_COLUMN}))


def format_summary(summary: MonthlySummary, top: int) -> list[str]:
    if not summary.has_data:
        return [f"[{summary.month}] 데이터 없음", *_budget_lines(summary)]
    lines = [
        f"[{summary.month} 요약] 거래 {summary.count}건",
        f"총 수입: {summary.total_income}원",
        f"총 지출: {summary.total_expense}원",
        f"잔액: {summary.balance}원",
        *_budget_lines(summary),
        f"지출 TOP {top}",
    ]
    if not summary.top_expenses:
        return [*lines, "  (지출 내역 없음)"]
    name_width = max(display_width(name) for name, _ in summary.top_expenses)
    amount_width = max(len(str(amount)) for _, amount in summary.top_expenses)
    ranking = [
        f"{rank}) {pad(name, name_width)} {str(amount).rjust(amount_width)}원"
        for rank, (name, amount) in enumerate(summary.top_expenses, start=1)
    ]
    return [*lines, *ranking]


def _budget_lines(summary: MonthlySummary) -> list[str]:
    if summary.budget is None or summary.usage_rate is None:
        return []
    lines = [f"예산: {summary.budget}원 (사용률 {summary.usage_rate:.1f}%)"]
    if summary.is_over_budget:
        over = summary.total_expense - summary.budget
        lines.append(f"[경고] 예산을 {over}원 초과했습니다!")
    elif summary.usage_rate >= BUDGET_WARNING_RATE:
        lines.append(f"[주의] 예산의 {BUDGET_WARNING_RATE:.0f}% 이상을 사용했습니다.")
    return lines
