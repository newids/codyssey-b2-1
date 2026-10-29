"""가계부의 업무 규칙. 화면 출력이나 파일 형식은 모른다."""

from __future__ import annotations

import heapq
from dataclasses import replace
from typing import Any, Iterator, Mapping, Sequence

from .decorators import log_call, timed
from .errors import BudgetAppError, NotFoundError, StepFailedError, ValidationError
from .models import (
    EXPENSE,
    Budget,
    MonthlySummary,
    SearchCriteria,
    Transaction,
    TransactionInput,
)
from .repository import TransactionRepository
from .stores import BudgetStore, CategoryStore
from .validators import normalize_name, parse_category_name

UPDATABLE_FIELDS = frozenset({"date", "type", "category", "amount", "memo", "tags"})


class BudgetService:
    """가계부의 업무 규칙(카테고리 확인, 최신순, 집계, 예산 비교, 삭제 정책)을 맡는다.

    파일 형식과 화면 출력은 모르며, 저장소는 생성자로 받는다(의존성 주입).
    """

    def __init__(
        self,
        transactions: TransactionRepository,
        categories: CategoryStore,
        budgets: BudgetStore,
    ) -> None:
        self._transactions = transactions
        self._categories = categories
        self._budgets = budgets

    # ----- 거래 -----

    def add_transaction(self, data: TransactionInput) -> Transaction:
        return self.add_transactions([data])[0]

    def add_transactions(self, items: Sequence[TransactionInput]) -> list[Transaction]:
        for item in items:
            self.require_category(item.category)
        return self._transactions.add_many(items)

    @log_call
    @timed
    def list_recent(self, limit: int) -> list[Transaction]:
        """최신순 상위 limit 건. 스트림을 한 번만 훑으며 limit 건만 메모리에 둔다."""
        return heapq.nlargest(limit, self._transactions.iter_all(), key=_sort_key)

    def iter_matching(self, criteria: SearchCriteria) -> Iterator[Transaction]:
        """조건에 맞는 거래를 저장 순서대로 하나씩 내보낸다(제너레이터)."""
        return (tx for tx in self._transactions.iter_all() if criteria.matches(tx))

    @log_call
    @timed
    def search(self, criteria: SearchCriteria, limit: int | None = None) -> list[Transaction]:
        if criteria.tx_id is not None:
            # id 는 유일하므로 첫 일치에서 읽기를 멈추고, 나머지 조건은 그 한 건에만 적용한다.
            found = self._transactions.find_by_id(criteria.tx_id)
            return [found] if found is not None and criteria.matches(found) else []
        matches = self.iter_matching(criteria)
        if limit is None:
            return sorted(matches, key=_sort_key, reverse=True)
        return heapq.nlargest(limit, matches, key=_sort_key)

    def update_transaction(self, tx_id: str, changes: Mapping[str, Any]) -> Transaction:
        unknown = set(changes) - UPDATABLE_FIELDS
        if unknown:
            raise ValidationError(f"수정할 수 없는 항목입니다: {', '.join(sorted(unknown))}")
        if not changes:
            raise ValidationError(
                "수정할 항목이 없습니다.",
                hint="--date, --type, --category, --amount, --memo, --tags 중 하나 이상을 지정하세요.",
            )
        current = self.require_transaction(tx_id)
        updated = replace(current, **changes)
        self.require_category(updated.category)
        self._transactions.rewrite(lambda tx: updated if tx.id == tx_id else tx)
        return updated

    def delete_transaction(self, tx_id: str) -> Transaction:
        target = self.require_transaction(tx_id)
        self._transactions.rewrite(lambda tx: None if tx.id == tx_id else tx)
        return target

    # ----- 요약 / 예산 -----

    @log_call
    @timed
    def summarize(self, month: str, top: int) -> MonthlySummary:
        """해당 월 거래를 한 번의 스트리밍 순회로 집계한다."""
        count = 0
        total_income = 0
        total_expense = 0
        expense_by_category: dict[str, int] = {}
        for tx in self._transactions.iter_all():
            if tx.month != month:
                continue
            count += 1
            if tx.type == EXPENSE:
                total_expense += tx.amount
                expense_by_category[tx.category] = (
                    expense_by_category.get(tx.category, 0) + tx.amount
                )
            else:
                total_income += tx.amount
        ranked = sorted(expense_by_category.items(), key=lambda item: (-item[1], item[0]))
        budget = self._budgets.get(month)
        return MonthlySummary(
            month=month,
            count=count,
            total_income=total_income,
            total_expense=total_expense,
            top_expenses=tuple(ranked[:top]),
            budget=budget.amount if budget else None,
        )

    def set_budget(self, month: str, amount: int) -> Budget:
        budget = Budget(month=month, amount=amount)
        self._budgets.upsert(budget)
        return budget

    def get_budget(self, month: str) -> Budget | None:
        return self._budgets.get(month)

    def list_budgets(self) -> list[Budget]:
        return list(self._budgets.iter_all())

    def remove_budget(self, month: str) -> Budget:
        """월 예산을 지운다. 이후 summary 는 그 달의 예산 줄과 경고를 출력하지 않는다."""
        budget = self._budgets.get(month)
        if budget is None:
            raise NotFoundError(
                f"{month} 예산이 설정되어 있지 않습니다.", hint="budget list 로 설정된 달을 확인하세요."
            )
        self._budgets.remove(month)
        return budget

    # ----- 카테고리 -----

    def list_categories(self) -> list[str]:
        return self._categories.names()

    def add_category(self, name: str) -> str:
        normalized = parse_category_name(name)
        if self._categories.exists(normalized):
            raise ValidationError(
                f"이미 등록된 카테고리입니다: {normalized}",
                hint="category list 로 현재 목록을 확인하세요.",
            )
        self._categories.add(normalized)
        return normalized

    def check_category_removal(self, name: str, replace_with: str | None) -> None:
        """삭제할 카테고리가 등록되어 있고, 대체 카테고리(있다면)도 등록된 다른 이름인지 확인한다."""
        self.require_category(name)
        if replace_with is None:
            return
        if replace_with == name:
            raise ValidationError(
                "대체 카테고리가 삭제할 카테고리와 같습니다.",
                hint="--replace-with 에 다른 카테고리를 지정하세요.",
            )
        self.require_category(replace_with)

    def remove_category(self, name: str, replace_with: str | None = None) -> int:
        """카테고리를 삭제한다. 사용 중이면 대체 카테고리가 있어야 한다.

        거래를 먼저 옮기고 카테고리는 마지막에 지우므로, 도중에 멈춰도
        지워진 카테고리를 가리키는 거래는 생기지 않는다. 옮긴 거래 수를 반환한다.
        """
        self.check_category_removal(name, replace_with)
        in_use = sum(1 for tx in self._transactions.iter_all() if tx.category == name)
        if in_use and replace_with is None:
            raise ValidationError(
                f"'{name}' 카테고리를 사용하는 거래가 {in_use}건 있어 삭제할 수 없습니다.",
                hint=f"category remove --name {name} --replace-with <대체 카테고리> 로 "
                "거래를 옮긴 뒤 삭제할 수 있습니다.",
            )
        action = "카테고리 삭제" if replace_with is None else "카테고리 대체"
        move = f"거래 {in_use}건을 '{replace_with}' 로 이동" if in_use else ""
        delete = f"카테고리 '{name}' 삭제"
        try:
            if move and replace_with is not None:
                self._transactions.rewrite(
                    lambda tx: replace(tx, category=replace_with) if tx.category == name else tx
                )
        except (OSError, BudgetAppError) as error:
            raise StepFailedError(action, error, done="", remaining=f"{move}, {delete}") from error
        try:
            self._categories.remove(name)
        except (OSError, BudgetAppError) as error:
            raise StepFailedError(action, error, done=move, remaining=delete) from error
        return in_use

    def require_category(self, name: str) -> str:
        """등록된 카테고리면 이름을 그대로 돌려주고, 아니면 오류를 낸다."""
        normalized = normalize_name(name)
        registered = self._categories.names()
        if normalized not in registered:
            raise ValidationError(
                f"등록되지 않은 카테고리입니다: {normalized or '(빈 값)'}",
                hint=f"사용 가능: {', '.join(registered) or '(없음)'} / "
                "새로 만들려면 category add 를 실행하세요.",
            )
        return normalized

    def require_transaction(self, tx_id: str) -> Transaction:
        """id 로 거래 한 건을 찾는다. 없으면 NotFoundError."""
        found = self._transactions.find_by_id(tx_id)
        if found is None:
            raise NotFoundError(
                f"없는 데이터입니다: id={tx_id}",
                hint="list 또는 search 명령으로 id 를 확인하세요. (예: TX-000012)",
            )
        return found


def _sort_key(tx: Transaction) -> tuple[str, int]:
    return tx.sort_key
