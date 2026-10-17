"""공통 관심사(예외 처리 / 실행 로그 / 실행 시간 측정)를 분리한 데코레이터."""

from __future__ import annotations

import functools
import logging
import os
import sys
import time
from typing import Callable, ParamSpec, TypeVar

from .errors import (
    EXIT_ERROR,
    EXIT_INTERRUPTED,
    EXIT_UNEXPECTED,
    BudgetAppError,
)

P = ParamSpec("P")
R = TypeVar("R")

logger = logging.getLogger("budget_app")


def format_error(message: str, hint: str = "") -> str:
    lines = [f"[오류] {message}"]
    if hint:
        lines.append(f"[힌트] {hint}")
    return "\n".join(lines)


def handle_errors(func: Callable[P, int]) -> Callable[P, int]:
    """예외를 스택트레이스 대신 '원인 + 힌트'로 출력하고 종료 코드로 바꾼다.

    예외 → 종료 코드 매핑(위에서부터 먼저 맞는 것):

        BudgetAppError 계열 (ValidationError, NotFoundError, DataFileError, ...) → 1, message/hint 그대로
        KeyboardInterrupt (Ctrl+C)                                             → 130
        BrokenPipeError (`| head` 처럼 받는 쪽이 먼저 닫힘)                     → 1, 메시지 없음
        OSError (권한, 경로, 디스크 공간)                                       → 1, strerror + 파일명
        그 밖의 Exception                                                      → 3, 예외 이름만 노출
        (argparse 형식 오류는 KoreanArgumentParser.error 가 2 로 끝낸다)

    사용 예::

        @handle_errors
        def main(argv=None) -> int:
            ...            # BudgetAppError 를 던지면 "[오류] ... / [힌트] ..." 두 줄과 코드 1
            return EXIT_OK
    """

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> int:
        try:
            return func(*args, **kwargs)
        except BudgetAppError as error:
            print(format_error(error.message, error.hint), file=sys.stderr)
            return error.exit_code
        except KeyboardInterrupt:
            print("\n" + format_error("사용자가 실행을 중단했습니다."), file=sys.stderr)
            return EXIT_INTERRUPTED
        except BrokenPipeError:
            # `... | head -1` 처럼 출력을 받는 쪽이 먼저 닫힌 경우: 오류 메시지 없이 끝낸다.
            _silence_stdout()
            return EXIT_ERROR
        except OSError as error:
            target = f" ({error.filename})" if error.filename else ""
            print(
                format_error(
                    f"파일을 처리할 수 없습니다: {error.strerror or error}{target}",
                    "경로가 맞는지, 읽기/쓰기 권한이 있는지 확인하세요.",
                ),
                file=sys.stderr,
            )
            return EXIT_ERROR
        except Exception as error:  # 마지막 방어선: 어떤 경우에도 스택트레이스를 노출하지 않는다
            print(
                format_error(
                    f"예기치 못한 오류가 발생했습니다: {type(error).__name__}: {error}",
                    "backup 명령으로 데이터를 보존한 뒤, 실행한 명령 전체와 --verbose 를 붙여 다시 실행한 "
                    "출력(표준 오류)을 함께 확인하세요. 마지막 [log] 줄이 멈춘 단계입니다.",
                ),
                file=sys.stderr,
            )
            return EXIT_UNEXPECTED

    return wrapper


def _silence_stdout() -> None:
    """인터프리터가 종료하며 버퍼를 비울 때 같은 오류가 다시 나지 않게 출력을 버린다."""
    try:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
    except (OSError, ValueError):
        pass


def log_call(func: Callable[P, R]) -> Callable[P, R]:
    """함수의 시작/성공/실패를 로그로 남긴다(--verbose 일 때 화면에 보인다)."""

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        logger.debug("시작: %s", func.__qualname__)
        try:
            result = func(*args, **kwargs)
        except Exception as error:
            logger.debug("실패: %s (%s)", func.__qualname__, type(error).__name__)
            raise
        logger.debug("완료: %s", func.__qualname__)
        return result

    return wrapper


def timed(func: Callable[P, R]) -> Callable[P, R]:
    """함수 실행 시간을 측정해 로그로 남긴다."""

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        started = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.debug("소요 시간: %s %.2fms", func.__qualname__, elapsed_ms)

    return wrapper
