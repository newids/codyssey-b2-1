"""대화형 입력: 올바른 값이 들어올 때까지 다시 묻는다."""

from __future__ import annotations

import sys
from typing import Callable, TypeVar

from .decorators import format_error
from .errors import InputCancelledError, ValidationError

T = TypeVar("T")


def ask(label: str, parse: Callable[[str], T]) -> T:
    """label 을 보여 주고 입력을 받아 parse 로 검증한다. 실패하면 이유를 알려 주고 재입력받는다."""
    while True:
        try:
            raw = input(f"{label}: ")
        except EOFError as error:
            raise InputCancelledError(
                "입력이 끝나 작업을 취소했습니다. 저장된 내용은 없습니다.",
                hint="명령을 다시 실행해 모든 항목을 입력하세요.",
            ) from error
        except UnicodeDecodeError:
            print(
                format_error("입력을 읽을 수 없습니다.", "UTF-8 문자로 다시 입력하세요."),
                file=sys.stderr,
            )
            continue
        try:
            return parse(raw)
        except ValidationError as error:
            print(format_error(error.message, error.hint), file=sys.stderr)
