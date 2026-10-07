"""크기가 작은 보조 데이터(카테고리, 예산, 반복 규칙, 일련번호)의 파일 저장소."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator, Sequence

from .models import Budget, RecurringRule, format_recurring_id, id_number
from .storage import append_jsonl, read_jsonl, write_jsonl_atomic

RECURRING_SEQUENCE_KEY = "recurring"


class SequenceStore:
    """마지막으로 발급한 일련번호를 보관한다(삭제 후에도 id 가 재사용되지 않게 한다)."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def get(self, key: str) -> int | None:
        return self._load().get(key)

    def set(self, key: str, value: int) -> None:
        values = {**self._load(), key: value}
        write_jsonl_atomic(
            self._path, ({"key": name, "value": number} for name, number in values.items())
        )

    def _load(self) -> dict[str, int]:
        return dict(read_jsonl(self._path, _decode_sequence))


def _decode_sequence(raw: dict[str, Any]) -> tuple[str, int]:
    return str(raw["key"]), int(raw["value"])


class CategoryStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def names(self) -> list[str]:
        return list(read_jsonl(self._path, lambda raw: str(raw["name"])))

    def exists(self, name: str) -> bool:
        return name in self.names()

    def add(self, name: str) -> None:
        append_jsonl(self._path, [{"name": name}])

    def remove(self, name: str) -> None:
        remaining = [existing for existing in self.names() if existing != name]
        write_jsonl_atomic(self._path, ({"name": existing} for existing in remaining))

    def replace_all(self, names: tuple[str, ...]) -> None:
        write_jsonl_atomic(self._path, ({"name": name} for name in names))


class BudgetStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def iter_all(self) -> Iterator[Budget]:
        return read_jsonl(self._path, Budget.from_dict)

    def get(self, month: str) -> Budget | None:
        return next((budget for budget in self.iter_all() if budget.month == month), None)

    def upsert(self, budget: Budget) -> None:
        others = [existing for existing in self.iter_all() if existing.month != budget.month]
        ordered = sorted([*others, budget], key=lambda item: item.month)
        write_jsonl_atomic(self._path, (item.to_dict() for item in ordered))


class RecurringStore:
    def __init__(self, path: Path, sequence: SequenceStore) -> None:
        self._path = path
        self._sequence = sequence

    def rules(self) -> list[RecurringRule]:
        return list(read_jsonl(self._path, RecurringRule.from_dict))

    def next_id(self) -> str:
        last = self._sequence.get(RECURRING_SEQUENCE_KEY)
        if last is None:
            last = max((id_number(rule.id) for rule in self.rules()), default=0)
        self._sequence.set(RECURRING_SEQUENCE_KEY, last + 1)
        return format_recurring_id(last + 1)

    def add(self, rule: RecurringRule) -> None:
        append_jsonl(self._path, [rule.to_dict()])

    def remove(self, rule_id: str) -> None:
        self.replace_all([rule for rule in self.rules() if rule.id != rule_id])

    def replace_all(self, rules: Sequence[RecurringRule]) -> None:
        write_jsonl_atomic(self._path, (rule.to_dict() for rule in rules))
