"""사용자에게 '원인 + 해결 힌트'로 보여 줄 예외 계층."""

from __future__ import annotations

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_UNEXPECTED = 3
EXIT_INTERRUPTED = 130


class BudgetAppError(Exception):
    """프로그램이 의도적으로 발생시키는 모든 오류의 부모."""

    exit_code = EXIT_ERROR

    def __init__(self, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


class ValidationError(BudgetAppError):
    """입력값이 규칙에 맞지 않을 때."""


class NotFoundError(BudgetAppError):
    """요청한 데이터(id, 파일 등)가 없을 때."""


class DataFileError(BudgetAppError):
    """저장 파일을 해석할 수 없을 때."""


class InputCancelledError(BudgetAppError):
    """대화형 입력 도중 입력이 끝났을 때(EOF)."""
