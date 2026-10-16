"""명령행 인터페이스: 인자 해석과 명령 분기."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import NoReturn, Sequence

from . import commands
from .app import create_app
from .config import DEFAULT_DATA_DIR, DEFAULT_LIST_LIMIT, DEFAULT_TOP_N
from .decorators import format_error, handle_errors
from .errors import EXIT_USAGE

PROGRAM = "python -m budget_app"


class KoreanArgumentParser(argparse.ArgumentParser):
    """인자 오류도 '[오류] / [힌트]' 형식으로 출력한다."""

    def error(self, message: str) -> NoReturn:
        print(
            format_error(
                f"명령 형식이 올바르지 않습니다: {message}",
                f"사용법은 '{self.prog} --help' 로 확인하세요.",
            ),
            file=sys.stderr,
        )
        raise SystemExit(EXIT_USAGE)


@handle_errors
def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _configure_logging(args.verbose)
    ctx = create_app(Path(args.data_dir))
    for notice in ctx.notices:
        print(f"[안내] {notice}", file=sys.stderr)
    return args.handler(args, ctx)


def build_parser() -> argparse.ArgumentParser:
    parser = KoreanArgumentParser(
        prog=PROGRAM,
        description="파일(JSONL) 기반 콘솔 용돈 기입장",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--data-dir", default=DEFAULT_DATA_DIR, help=f"저장 폴더 (기본값: {DEFAULT_DATA_DIR})"
    )
    parser.add_argument("--verbose", action="store_true", help="실행 로그와 소요 시간을 출력")
    common = _common_options()
    subparsers = parser.add_subparsers(dest="command", metavar="<command>", required=True)

    def add_command(name: str, help_text: str) -> argparse.ArgumentParser:
        return subparsers.add_parser(
            name, help=help_text, description=help_text, parents=[common], allow_abbrev=False
        )

    _add_transaction_commands(add_command)
    _add_report_commands(add_command)
    _add_transfer_commands(add_command)
    _add_budget_commands(add_command("budget", "월 예산 설정/조회"), common)
    _add_category_commands(add_command("category", "카테고리 관리"), common)
    _add_recurring_commands(add_command("recurring", "반복 내역(월급/월세 등) 관리"), common)
    return parser


def _common_options() -> argparse.ArgumentParser:
    """모든 하위 명령 뒤에서도 쓸 수 있는 공통 옵션."""
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--data-dir", default=argparse.SUPPRESS, help="저장 폴더")
    common.add_argument(
        "--verbose", action="store_true", default=argparse.SUPPRESS, help="실행 로그 출력"
    )
    return common


def _add_transaction_commands(add_command) -> None:
    add = add_command("add", "거래 추가 (대화형 입력)")
    add.set_defaults(handler=commands.cmd_add)

    update = add_command("update", "거래 수정 (옵션 방식: 지정한 항목만 바뀝니다)")
    update.add_argument("--id", required=True, help="수정할 거래 id (예: TX-000012)")
    update.add_argument("--date", help="날짜 YYYY-MM-DD")
    update.add_argument("--type", help="income 또는 expense")
    update.add_argument("--category", help="등록된 카테고리")
    update.add_argument("--amount", help="금액(양수 정수)")
    update.add_argument("--memo", help='메모 ("" 를 주면 비웁니다)')
    update.add_argument("--tags", help='쉼표로 구분한 태그 ("" 를 주면 비웁니다)')
    update.set_defaults(handler=commands.cmd_update)

    delete = add_command("delete", "거래 삭제")
    delete.add_argument("--id", required=True, help="삭제할 거래 id (예: TX-000012)")
    delete.set_defaults(handler=commands.cmd_delete)


def _add_report_commands(add_command) -> None:
    listing = add_command("list", "거래 목록 (최신순)")
    listing.add_argument(
        "--limit", default=str(DEFAULT_LIST_LIMIT), help=f"출력 건수 (기본값: {DEFAULT_LIST_LIMIT})"
    )
    listing.set_defaults(handler=commands.cmd_list)

    search = add_command("search", "조건으로 거래 검색 (최신순)")
    search.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD", help="시작일(포함)")
    search.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD", help="종료일(포함)")
    search.add_argument("--category", help="카테고리")
    search.add_argument("--type", help="income 또는 expense")
    search.add_argument("--q", help="메모에 포함된 키워드")
    search.add_argument("--tag", help="태그")
    search.add_argument("--min-amount", metavar="금액", help="이 금액 이상(포함)")
    search.add_argument("--max-amount", metavar="금액", help="이 금액 이하(포함)")
    search.add_argument("--limit", help="출력 건수 (기본값: 전체)")
    search.set_defaults(handler=commands.cmd_search)

    summary = add_command("summary", "월별 요약 (수입/지출/잔액/예산/지출 TOP N)")
    summary.add_argument("--month", required=True, metavar="YYYY-MM", help="대상 월")
    summary.add_argument(
        "--top", default=str(DEFAULT_TOP_N), help=f"지출 상위 카테고리 수 (기본값: {DEFAULT_TOP_N})"
    )
    summary.set_defaults(handler=commands.cmd_summary)


def _add_transfer_commands(add_command) -> None:
    importing = add_command("import", "CSV 파일의 거래를 일괄 등록")
    importing.add_argument("--from", dest="source", required=True, metavar="CSV", help="가져올 CSV")
    importing.add_argument(
        "--strict",
        action="store_true",
        help="잘못된 행이 하나라도 있으면 아무것도 등록하지 않음 (기본: 올바른 행만 등록)",
    )
    importing.set_defaults(handler=commands.cmd_import)

    export = add_command("export", "조건에 맞는 거래를 CSV 로 저장")
    export.add_argument("--out", required=True, metavar="CSV", help="저장할 CSV 경로")
    export.add_argument("--month", metavar="YYYY-MM", help="대상 월")
    export.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD", help="시작일(포함)")
    export.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD", help="종료일(포함)")
    export.set_defaults(handler=commands.cmd_export)

    backup = add_command("backup", "데이터 파일을 타임스탬프 폴더로 백업")
    backup.set_defaults(handler=commands.cmd_backup)


def _add_budget_commands(budget: argparse.ArgumentParser, common: argparse.ArgumentParser) -> None:
    actions = budget.add_subparsers(dest="action", metavar="<set|show|list>", required=True)

    setting = actions.add_parser("set", help="월 예산 저장", parents=[common], allow_abbrev=False)
    setting.add_argument("--month", required=True, metavar="YYYY-MM", help="대상 월")
    setting.add_argument("--amount", required=True, help="예산 금액(양수 정수)")
    setting.set_defaults(handler=commands.cmd_budget_set)

    show = actions.add_parser("show", help="월 예산 조회", parents=[common], allow_abbrev=False)
    show.add_argument("--month", required=True, metavar="YYYY-MM", help="대상 월")
    show.set_defaults(handler=commands.cmd_budget_show)

    listing = actions.add_parser("list", help="전체 예산 목록", parents=[common])
    listing.set_defaults(handler=commands.cmd_budget_list)


def _add_category_commands(
    category: argparse.ArgumentParser, common: argparse.ArgumentParser
) -> None:
    actions = category.add_subparsers(dest="action", metavar="<add|list|remove>", required=True)

    adding = actions.add_parser("add", help="카테고리 추가", parents=[common], allow_abbrev=False)
    adding.add_argument("--name", help="카테고리명 (생략하면 대화형으로 입력)")
    adding.set_defaults(handler=commands.cmd_category_add)

    listing = actions.add_parser("list", help="카테고리 목록", parents=[common])
    listing.set_defaults(handler=commands.cmd_category_list)

    removing = actions.add_parser(
        "remove", help="카테고리 삭제", parents=[common], allow_abbrev=False
    )
    removing.add_argument("--name", help="카테고리명 (생략하면 대화형으로 입력)")
    removing.add_argument(
        "--replace-with", metavar="CATEGORY", help="사용 중인 거래를 옮길 대체 카테고리"
    )
    removing.set_defaults(handler=commands.cmd_category_remove)


def _add_recurring_commands(
    recurring: argparse.ArgumentParser, common: argparse.ArgumentParser
) -> None:
    actions = recurring.add_subparsers(
        dest="action", metavar="<add|list|remove|apply>", required=True
    )

    adding = actions.add_parser("add", help="반복 규칙 등록", parents=[common], allow_abbrev=False)
    adding.add_argument("--day", required=True, help="매월 반복 일자 (1~31)")
    adding.add_argument("--type", required=True, help="income 또는 expense")
    adding.add_argument("--category", required=True, help="등록된 카테고리")
    adding.add_argument("--amount", required=True, help="금액(양수 정수)")
    adding.add_argument("--memo", help="메모")
    adding.set_defaults(handler=commands.cmd_recurring_add)

    listing = actions.add_parser("list", help="반복 규칙 목록", parents=[common])
    listing.set_defaults(handler=commands.cmd_recurring_list)

    removing = actions.add_parser(
        "remove", help="반복 규칙 삭제", parents=[common], allow_abbrev=False
    )
    removing.add_argument("--id", required=True, help="규칙 id (예: RC-0001)")
    removing.set_defaults(handler=commands.cmd_recurring_remove)

    applying = actions.add_parser(
        "apply", help="해당 월의 반복 내역을 거래로 생성", parents=[common], allow_abbrev=False
    )
    applying.add_argument("--month", required=True, metavar="YYYY-MM", help="대상 월")
    applying.set_defaults(handler=commands.cmd_recurring_apply)


def _configure_logging(is_verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if is_verbose else logging.WARNING,
        format="[log] %(message)s",
        stream=sys.stderr,
        force=True,
    )
