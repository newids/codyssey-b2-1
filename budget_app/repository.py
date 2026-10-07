"""거래 내역 저장소. 거래 파일은 계속 커질 수 있으므로 항상 스트리밍으로 다룬다."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterator, Sequence

from .decorators import log_call, timed
from .models import Transaction, TransactionInput, format_transaction_id, id_number
from .storage import append_jsonl, read_jsonl, write_jsonl_atomic
from .stores import SequenceStore

TRANSACTION_SEQUENCE_KEY = "transaction"

Transform = Callable[[Transaction], "Transaction | None"]


class TransactionRepository:
    def __init__(self, path: Path, sequence: SequenceStore) -> None:
        self._path = path
        self._sequence = sequence

    def iter_all(self) -> Iterator[Transaction]:
        """저장된 순서대로 거래를 하나씩 내보낸다(제너레이터)."""
        yield from read_jsonl(self._path, Transaction.from_dict)

    def find_by_id(self, tx_id: str) -> Transaction | None:
        return next((tx for tx in self.iter_all() if tx.id == tx_id), None)

    def add_many(self, items: Sequence[TransactionInput]) -> list[Transaction]:
        if not items:
            return []
        first = self._reserve_sequences(len(items))
        created = [
            Transaction.from_input(format_transaction_id(first + offset), item)
            for offset, item in enumerate(items)
        ]
        append_jsonl(self._path, (tx.to_dict() for tx in created))
        return created

    @log_call
    @timed
    def rewrite(self, transform: Transform) -> int:
        """모든 거래에 transform 을 적용해 파일을 원자적으로 다시 쓴다.

        transform 이 None 을 돌려주면 그 거래는 삭제되고, 다른 객체를 돌려주면 교체된다.
        바뀐(삭제 포함) 거래 수를 반환한다.
        """
        changed = 0

        def transformed() -> Iterator[dict]:
            nonlocal changed
            for tx in self.iter_all():
                result = transform(tx)
                if result is not tx:
                    changed += 1
                if result is not None:
                    yield result.to_dict()

        write_jsonl_atomic(self._path, transformed())
        return changed

    def _reserve_sequences(self, count: int) -> int:
        """count 개의 일련번호를 예약하고 첫 번호를 반환한다.

        거래를 쓰기 전에 번호부터 저장한다. 중간에 중단되면 번호가 건너뛸 뿐
        같은 id 가 두 번 발급되는 일은 없다.
        """
        last = self._sequence.get(TRANSACTION_SEQUENCE_KEY)
        if last is None:
            last = max((id_number(tx.id) for tx in self.iter_all()), default=0)
        self._sequence.set(TRANSACTION_SEQUENCE_KEY, last + count)
        return last + 1
