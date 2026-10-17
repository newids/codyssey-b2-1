"""CSV 가져오기/내보내기. 스키마: date,type,category,amount,memo,tags (UTF-8, 헤더 포함)."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, NamedTuple

from .decorators import log_call, timed
from .errors import DataFileError, NotFoundError, ValidationError
from .models import SearchCriteria, Transaction, TransactionInput
from .services import BudgetService
from .storage import atomic_open
from .validators import parse_amount, parse_date, parse_tags, parse_type

CSV_COLUMNS: tuple[str, ...] = ("date", "type", "category", "amount", "memo", "tags")
REQUIRED_COLUMNS: tuple[str, ...] = ("date", "type", "category", "amount")
TAG_SEPARATOR = ","
MAX_STRICT_REASONS = 5
# 엑셀이 저장한 UTF-8 파일의 BOM 도 읽을 수 있게 한다.
CSV_READ_ENCODING = "utf-8-sig"


@dataclass(frozen=True)
class ImportResult:
    imported: int
    skipped: tuple[str, ...]


DuplicateKey = tuple[str, str, str, int, str]


@log_call
@timed
def import_transactions(
    ledger: BudgetService, source: Path, strict: bool = False, skip_duplicates: bool = False
) -> ImportResult:
    """CSV 의 거래를 일괄 등록한다.

    기본(부분 성공): 올바른 행만 등록하고 잘못된 행은 사유와 함께 건너뛴다.
    strict(롤백): 잘못된 행이 하나라도 있으면 아무것도 등록하지 않고 사유를 모두 알려 준다.
    skip_duplicates: 날짜·타입·카테고리·금액·메모가 같은 거래가 이미 저장된 개수만큼 건너뛴다.
    저장된 1건에 CSV 의 같은 행 1개가 상쇄되므로, 같은 파일을 다시 넣으면 전부 건너뛰고
    같은 날 같은 금액을 실제로 두 번 쓴 행은 남는다. 중복은 잘못된 행이 아니므로 strict 의 실패 사유가 아니다.
    어느 쪽이든 검증을 모두 마친 뒤에 파일에 쓰므로, 검증 실패로 절반만 쓰이는 일은 없다.
    """
    if not source.is_file():
        raise NotFoundError(
            f"가져올 파일을 찾을 수 없습니다: {source}", hint="--from 경로를 확인하세요."
        )
    rows = _classify_rows(ledger, source, skip_duplicates)
    if strict and rows.invalid:
        reasons = [_format_skip(row) for row in rows.invalid]
        raise ValidationError(
            f"잘못된 행이 {len(rows.invalid)}건 있어 아무것도 등록하지 않았습니다 (--strict). "
            + " / ".join(reasons[:MAX_STRICT_REASONS]),
            hint="해당 행을 고친 뒤 다시 실행하거나, --strict 없이 실행해 올바른 행만 등록하세요.",
        )
    created = ledger.add_transactions(rows.valid)
    skipped = sorted([*rows.invalid, *rows.duplicates], key=lambda row: row[0])
    return ImportResult(imported=len(created), skipped=tuple(_format_skip(row) for row in skipped))


class ClassifiedRows(NamedTuple):
    valid: list[TransactionInput]
    invalid: list[tuple[int, str]]  # (행 번호, 사유)
    duplicates: list[tuple[int, str]]


def _classify_rows(ledger: BudgetService, source: Path, skip_duplicates: bool) -> ClassifiedRows:
    """행을 (등록할 것, 잘못된 것, 중복) 으로 나눈다.

    중복 검사는 저장된 거래의 키 개수를 세어 두고, CSV 행 하나가 나올 때마다 하나씩 상쇄한다.
    """
    remaining = _stored_key_counts(ledger) if skip_duplicates else Counter()
    rows = ClassifiedRows([], [], [])
    for row_number, row in _read_rows(source):
        try:
            item = _row_to_input(ledger, row)
        except ValidationError as error:
            rows.invalid.append((row_number, error.message))
            continue
        key = _duplicate_key(item)
        if remaining[key] > 0:
            remaining[key] -= 1
            rows.duplicates.append(
                (row_number, f"이미 있는 거래 ({item.date} {item.category} {item.amount}원)")
            )
            continue
        rows.valid.append(item)
    return rows


def _stored_key_counts(ledger: BudgetService) -> Counter[DuplicateKey]:
    """저장된 거래의 중복 판정 키별 개수. 한 번 스트리밍하며 키만 센다(태그는 제외)."""
    return Counter(_duplicate_key(tx) for tx in ledger.iter_matching(SearchCriteria()))


def _duplicate_key(item: TransactionInput | Transaction) -> DuplicateKey:
    # 메모는 앞뒤 공백을 무시한다(손으로 고친 저장 파일이나 반복 규칙의 메모와도 맞도록).
    return (item.date, item.type, item.category, item.amount, item.memo.strip())


def _format_skip(row: tuple[int, str]) -> str:
    row_number, reason = row
    return f"{row_number}행: {reason}"


@log_call
@timed
def export_transactions(ledger: BudgetService, target: Path, criteria: SearchCriteria) -> int:
    """조건에 맞는 거래를 스트리밍으로 CSV 에 쓴다. 기록한 건수를 반환한다."""
    count = 0
    with atomic_open(target, newline="") as file:
        writer = csv.writer(file)
        writer.writerow(CSV_COLUMNS)
        for tx in ledger.iter_matching(criteria):
            writer.writerow(_transaction_to_row(tx))
            count += 1
    return count


def _read_rows(source: Path) -> Iterator[tuple[int, dict[str, str]]]:
    """(줄 번호, 행) 을 하나씩 내보내는 제너레이터."""
    try:
        with source.open("r", encoding=CSV_READ_ENCODING, newline="") as file:
            reader = csv.DictReader(file)
            # 'Date', ' type ' 처럼 대소문자·공백만 다른 헤더는 같은 컬럼으로 본다.
            reader.fieldnames = [name.strip().lower() for name in (reader.fieldnames or [])]
            missing = [name for name in REQUIRED_COLUMNS if name not in reader.fieldnames]
            if missing:
                raise DataFileError(
                    f"CSV 헤더에 필수 컬럼이 없습니다: {', '.join(missing)}",
                    hint=f"첫 줄을 {','.join(CSV_COLUMNS)} 로 맞추세요.",
                )
            for row in reader:
                yield reader.line_num, {name: (row.get(name) or "") for name in CSV_COLUMNS}
    except (UnicodeDecodeError, csv.Error) as error:
        raise DataFileError(
            f"CSV 파일을 읽을 수 없습니다: {source}",
            hint="UTF-8 로 저장된 CSV 파일인지 확인하세요.",
        ) from error


def _row_to_input(ledger: BudgetService, row: dict[str, str]) -> TransactionInput:
    return TransactionInput(
        date=parse_date(row["date"]),
        type=parse_type(row["type"]),
        category=ledger.require_category(row["category"]),
        amount=parse_amount(row["amount"]),
        memo=row["memo"].strip(),
        tags=parse_tags(row["tags"]),
    )


def _transaction_to_row(tx: Transaction) -> list[str]:
    return [tx.date, tx.type, tx.category, str(tx.amount), tx.memo, TAG_SEPARATOR.join(tx.tags)]
