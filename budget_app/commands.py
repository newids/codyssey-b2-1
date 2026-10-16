"""명령별 처리기. 인자를 검증해 서비스에 넘기고 결과를 출력한다. 반환값은 종료 코드."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

from .app import AppContext
from .backup import create_backup
from .csv_io import export_transactions, import_transactions
from .errors import EXIT_ERROR, EXIT_OK, NotFoundError, ValidationError
from .formatter import format_recurring_rules, format_summary, format_transactions
from .models import SearchCriteria, TransactionInput
from .prompts import ask
from .validators import (
    month_range,
    parse_amount,
    parse_category_name,
    parse_date,
    parse_month,
    parse_positive_int,
    parse_recurring_day,
    parse_tags,
    parse_type,
)

MAX_SKIP_REASONS_SHOWN = 10


def cmd_add(args: argparse.Namespace, ctx: AppContext) -> int:
    data = TransactionInput(
        date=ask("날짜(YYYY-MM-DD)", parse_date),
        type=ask("타입(income/expense)", parse_type),
        category=ask("카테고리", ctx.ledger.require_category),
        amount=ask("금액(양수)", parse_amount),
        memo=ask("메모(선택)", str.strip),
        tags=ask("태그(쉼표로 구분, 없으면 엔터)", parse_tags),
    )
    created = ctx.ledger.add_transaction(data)
    print(f"[저장 완료] id={created.id}")
    return EXIT_OK


def cmd_list(args: argparse.Namespace, ctx: AppContext) -> int:
    limit = parse_positive_int(args.limit, "--limit")
    transactions = ctx.ledger.list_recent(limit)
    if not transactions:
        print("거래 내역이 없습니다. add 명령으로 첫 거래를 등록하세요.")
        return EXIT_OK
    print("\n".join(format_transactions(transactions)))
    return EXIT_OK


def cmd_search(args: argparse.Namespace, ctx: AppContext) -> int:
    criteria = SearchCriteria(
        date_from=_optional(args.date_from, parse_date),
        date_to=_optional(args.date_to, parse_date),
        category=_optional(args.category, ctx.ledger.require_category),
        type=_optional(args.type, parse_type),
        keyword=_optional(args.q, str.strip),
        tag=_optional(args.tag, str.strip),
        min_amount=_optional(args.min_amount, parse_amount),
        max_amount=_optional(args.max_amount, parse_amount),
    )
    limit = _optional(args.limit, lambda text: parse_positive_int(text, "--limit"))
    transactions = ctx.ledger.search(criteria, limit)
    if not transactions:
        print("조건에 맞는 거래가 없습니다.")
        return EXIT_OK
    print("\n".join(format_transactions(transactions)))
    print(f"(총 {len(transactions)}건)")
    return EXIT_OK


def cmd_summary(args: argparse.Namespace, ctx: AppContext) -> int:
    month = parse_month(args.month)
    top = parse_positive_int(args.top, "--top")
    print("\n".join(format_summary(ctx.ledger.summarize(month, top), top)))
    return EXIT_OK


def cmd_budget_set(args: argparse.Namespace, ctx: AppContext) -> int:
    budget = ctx.ledger.set_budget(parse_month(args.month), parse_amount(args.amount))
    print(f"[저장 완료] {budget.month} 예산 {budget.amount}원")
    return EXIT_OK


def cmd_budget_show(args: argparse.Namespace, ctx: AppContext) -> int:
    month = parse_month(args.month)
    budget = ctx.ledger.get_budget(month)
    if budget is None:
        raise NotFoundError(
            f"{month} 예산이 설정되어 있지 않습니다.",
            hint=f"budget set --month {month} --amount <금액> 으로 설정하세요.",
        )
    print(f"{budget.month} 예산 {budget.amount}원")
    return EXIT_OK


def cmd_budget_list(args: argparse.Namespace, ctx: AppContext) -> int:
    budgets = ctx.ledger.list_budgets()
    if not budgets:
        print("설정된 예산이 없습니다.")
        return EXIT_OK
    for budget in budgets:
        print(f"- {budget.month}: {budget.amount}원")
    return EXIT_OK


def cmd_category_add(args: argparse.Namespace, ctx: AppContext) -> int:
    name = (
        parse_category_name(args.name)
        if args.name is not None
        else ask("카테고리명", parse_category_name)
    )
    print(f"[저장 완료] category={ctx.ledger.add_category(name)}")
    return EXIT_OK


def cmd_category_list(args: argparse.Namespace, ctx: AppContext) -> int:
    for name in ctx.ledger.list_categories():
        print(f"- {name}")
    return EXIT_OK


def cmd_category_remove(args: argparse.Namespace, ctx: AppContext) -> int:
    name = args.name.strip() if args.name is not None else ask("삭제할 카테고리명", str.strip)
    replace_with = _optional(args.replace_with, str.strip)
    moved = ctx.recurring.remove_category(name, replace_with)
    if moved.transactions:
        print(f"[안내] 거래 {moved.transactions}건을 '{replace_with}' 카테고리로 옮겼습니다.")
    if moved.rules:
        print(f"[안내] 반복 규칙 {moved.rules}건을 '{replace_with}' 카테고리로 옮겼습니다.")
    print(f"[삭제 완료] category={name}")
    return EXIT_OK


def cmd_update(args: argparse.Namespace, ctx: AppContext) -> int:
    changes = _collect_changes(args, ctx)
    updated = ctx.ledger.update_transaction(args.id.strip(), changes)
    print(f"[수정 완료] id={updated.id}")
    print("\n".join(format_transactions([updated])))
    return EXIT_OK


def cmd_delete(args: argparse.Namespace, ctx: AppContext) -> int:
    deleted = ctx.ledger.delete_transaction(args.id.strip())
    print(f"[삭제 완료] id={deleted.id} ({deleted.date} {deleted.category} {deleted.amount}원)")
    return EXIT_OK


def cmd_import(args: argparse.Namespace, ctx: AppContext) -> int:
    result = import_transactions(ctx.ledger, Path(args.source), strict=args.strict)
    print(f"[완료] imported={result.imported}, skipped={len(result.skipped)}")
    for reason in result.skipped[:MAX_SKIP_REASONS_SHOWN]:
        print(f"  - 건너뜀 {reason}")
    hidden = len(result.skipped) - MAX_SKIP_REASONS_SHOWN
    if hidden > 0:
        print(f"  - ... 외 {hidden}건")
    return EXIT_OK


def cmd_export(args: argparse.Namespace, ctx: AppContext) -> int:
    criteria = _export_criteria(args)
    count = export_transactions(ctx.ledger, Path(args.out), criteria)
    print(f"[완료] {args.out} ({count} records)")
    return EXIT_OK


def cmd_backup(args: argparse.Namespace, ctx: AppContext) -> int:
    copied = create_backup(ctx.paths, datetime.now())
    if not copied:
        print("백업할 데이터 파일이 없습니다.")
        return EXIT_OK
    print(f"[백업 완료] {copied[0].parent} ({len(copied)} files)")
    for path in copied:
        print(f"- {path.name}")
    return EXIT_OK


def cmd_recurring_add(args: argparse.Namespace, ctx: AppContext) -> int:
    rule = ctx.recurring.add_rule(
        day=parse_recurring_day(args.day),
        type_=parse_type(args.type),
        category=args.category.strip(),
        amount=parse_amount(args.amount),
        memo=(args.memo or "").strip(),
    )
    print(f"[저장 완료] id={rule.id} (매월 {rule.day}일 {rule.category} {rule.amount}원)")
    return EXIT_OK


def cmd_recurring_list(args: argparse.Namespace, ctx: AppContext) -> int:
    rules = ctx.recurring.list_rules()
    if not rules:
        print("등록된 반복 규칙이 없습니다.")
        return EXIT_OK
    print("\n".join(format_recurring_rules(rules)))
    return EXIT_OK


def cmd_recurring_remove(args: argparse.Namespace, ctx: AppContext) -> int:
    removed = ctx.recurring.remove_rule(args.id.strip())
    print(f"[삭제 완료] id={removed.id}")
    return EXIT_OK


def cmd_recurring_apply(args: argparse.Namespace, ctx: AppContext) -> int:
    month = parse_month(args.month)
    result = ctx.recurring.apply(month)
    print(
        f"[완료] {month} 반복 내역: created={len(result.created)}, "
        f"already_applied={len(result.already_applied)}, failed={len(result.failed)}"
    )
    for tx in result.created:
        print(f"  - 생성 {tx.id} {tx.date} {tx.category} {tx.amount}원")
    for reason in result.failed:
        print(f"  - 실패 {reason}")
    return EXIT_ERROR if result.failed else EXIT_OK


def _optional(value: str | None, parse: Any) -> Any:
    return None if value is None else parse(value)


def _collect_changes(args: argparse.Namespace, ctx: AppContext) -> dict[str, Any]:
    """지정된 옵션만 골라 수정 내용으로 만든다(빈 문자열은 '비우기'로 취급)."""
    candidates = {
        "date": _optional(args.date, parse_date),
        "type": _optional(args.type, parse_type),
        "category": _optional(args.category, ctx.ledger.require_category),
        "amount": _optional(args.amount, parse_amount),
        "memo": _optional(args.memo, str.strip),
        "tags": _optional(args.tags, parse_tags),
    }
    return {name: value for name, value in candidates.items() if value is not None}


def _export_criteria(args: argparse.Namespace) -> SearchCriteria:
    has_range = args.date_from is not None or args.date_to is not None
    if args.month is not None and has_range:
        raise ValidationError(
            "--month 와 --from/--to 는 함께 쓸 수 없습니다.", hint="둘 중 한 가지 방식만 지정하세요."
        )
    if args.month is not None:
        first_day, last_day = month_range(parse_month(args.month))
        return SearchCriteria(date_from=first_day, date_to=last_day)
    if has_range:
        return SearchCriteria(
            date_from=_optional(args.date_from, parse_date),
            date_to=_optional(args.date_to, parse_date),
        )
    raise ValidationError(
        "내보낼 기간을 지정해야 합니다.",
        hint="--month YYYY-MM 또는 --from YYYY-MM-DD --to YYYY-MM-DD 를 지정하세요.",
    )
