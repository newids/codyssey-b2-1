"""반복 내역(월급, 월세 등): 규칙을 등록해 두고 특정 월의 거래로 생성한다."""

from __future__ import annotations

from dataclasses import dataclass, replace

from .errors import NotFoundError, StepFailedError, ValidationError
from .models import RecurringRule, SearchCriteria, Transaction, TransactionInput
from .services import BudgetService
from .stores import RecurringStore
from .validators import month_range


@dataclass(frozen=True)
class ApplyResult:
    created: tuple[Transaction, ...]
    already_applied: tuple[str, ...]
    failed: tuple[str, ...]


@dataclass(frozen=True)
class CategoryRemoval:
    """카테고리 삭제 때 대체 카테고리로 옮긴 건수."""

    transactions: int
    rules: int


class RecurringService:
    """반복 규칙의 등록·삭제와 월별 적용을 맡는다. 거래 생성은 BudgetService 에 위임한다."""

    def __init__(self, store: RecurringStore, ledger: BudgetService) -> None:
        self._store = store
        self._ledger = ledger

    def list_rules(self) -> list[RecurringRule]:
        return self._store.rules()

    def add_rule(self, day: int, type_: str, category: str, amount: int, memo: str) -> RecurringRule:
        self._ledger.require_category(category)
        rule = RecurringRule(
            id=self._store.next_id(),
            day=day,
            type=type_,
            amount=amount,
            category=category,
            memo=memo,
        )
        self._store.add(rule)
        return rule

    def remove_rule(self, rule_id: str) -> RecurringRule:
        target = next((rule for rule in self._store.rules() if rule.id == rule_id), None)
        if target is None:
            raise NotFoundError(
                f"없는 반복 규칙입니다: id={rule_id}",
                hint="recurring list 로 id 를 확인하세요. (예: RC-0001)",
            )
        self._store.remove(rule_id)
        return target

    def remove_category(self, name: str, replace_with: str | None = None) -> CategoryRemoval:
        """카테고리를 삭제한다. 거래뿐 아니라 반복 규칙이 쓰고 있어도 대체 카테고리가 필요하다.

        세 파일(규칙 → 거래 → 카테고리)을 한 트랜잭션으로 묶지는 않는다. 대신 참조하는 쪽을
        먼저 옮기고 카테고리를 마지막에 지우므로, 어느 단계에서 중단되어도 지워진 카테고리를
        가리키는 데이터는 남지 않고 같은 명령을 다시 실행하면 이어서 끝난다(이미 옮긴 건수는 0으로 보고된다).
        """
        # BudgetService.remove_category 도 같은 검사를 하지만, 규칙을 옮기기 전에 먼저 걸러야 한다.
        self._ledger.check_category_removal(name, replace_with)
        rules = self._store.rules()
        using = [rule for rule in rules if rule.category == name]
        if using and replace_with is None:
            raise ValidationError(
                f"'{name}' 카테고리를 사용하는 반복 규칙이 {len(using)}건 있어 삭제할 수 없습니다.",
                hint=f"category remove --name {name} --replace-with <대체 카테고리> 로 "
                "옮긴 뒤 삭제하거나, recurring remove 로 규칙을 먼저 지우세요.",
            )
        if using and replace_with is not None:
            self._store.replace_all(
                [
                    replace(rule, category=replace_with) if rule.category == name else rule
                    for rule in rules
                ]
            )
        moved_transactions = self._remove_after_rules(name, replace_with, len(using))
        return CategoryRemoval(transactions=moved_transactions, rules=len(using))

    def _remove_after_rules(self, name: str, replace_with: str | None, moved_rules: int) -> int:
        """거래 이동과 카테고리 삭제를 맡기고, 실패하면 이미 옮긴 규칙까지 포함해 진행 상황을 알린다."""
        try:
            return self._ledger.remove_category(name, replace_with)
        except StepFailedError as error:
            if not moved_rules:
                raise
            rules_done = f"반복 규칙 {moved_rules}건을 '{replace_with}' 로 이동"
            done = f"{rules_done}, {error.done}" if error.done else rules_done
            raise StepFailedError("카테고리 대체", error.cause, done, error.remaining) from error.cause

    def apply(self, month: str) -> ApplyResult:
        """해당 월에 아직 생성되지 않은 규칙만 거래로 만든다(여러 번 실행해도 중복되지 않는다)."""
        first_day, last_day = month_range(month)
        in_month = SearchCriteria(date_from=first_day, date_to=last_day)
        applied_tags = {
            tag for tx in self._ledger.iter_matching(in_month) for tag in tx.tags
        }
        created: list[Transaction] = []
        already_applied: list[str] = []
        failed: list[str] = []
        for rule in self._store.rules():
            if rule.marker_tag in applied_tags:
                already_applied.append(rule.id)
                continue
            try:
                created.append(self._ledger.add_transaction(_to_input(rule, month, last_day)))
            except ValidationError as error:
                failed.append(f"{rule.id}: {error.message}")
        return ApplyResult(tuple(created), tuple(already_applied), tuple(failed))


def _to_input(rule: RecurringRule, month: str, last_day: str) -> TransactionInput:
    # 31일 규칙을 2월에 적용하면 말일로 당긴다.
    day = min(rule.day, int(last_day[-2:]))
    return TransactionInput(
        type=rule.type,
        date=f"{month}-{day:02d}",
        amount=rule.amount,
        category=rule.category,
        memo=rule.memo,
        tags=(rule.marker_tag,),
    )
