"""테스트 공용 도구: 임시 데이터 폴더와 CLI 실행기."""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence
from unittest import mock

from budget_app.app import AppContext, create_app
from budget_app.cli import main
from budget_app.models import TransactionInput


@dataclass(frozen=True)
class CliResult:
    code: int
    out: str
    err: str


def expense(date: str, amount: int, category: str = "food", **extra) -> TransactionInput:
    return TransactionInput(type="expense", date=date, amount=amount, category=category, **extra)


def income(date: str, amount: int, category: str = "salary", **extra) -> TransactionInput:
    return TransactionInput(type="income", date=date, amount=amount, category=category, **extra)


class DataDirTestCase(unittest.TestCase):
    """테스트마다 독립된 임시 데이터 폴더를 쓴다."""

    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.work_dir = Path(temp.name)
        self.data_dir = self.work_dir / "data"

    def app(self) -> AppContext:
        return create_app(self.data_dir)

    def run_cli(self, *argv: str, inputs: Sequence[str] = ()) -> CliResult:
        """실제 진입점(main)을 호출한다. inputs 는 input() 에 차례로 공급된다."""
        answers: Iterator[str] = iter(inputs)

        def fake_input(prompt: str = "") -> str:
            try:
                return next(answers)
            except StopIteration:
                raise EOFError from None

        out, err = io.StringIO(), io.StringIO()
        with mock.patch("builtins.input", fake_input), redirect_stdout(out), redirect_stderr(err):
            try:
                code = main(["--data-dir", str(self.data_dir), *argv])
            except SystemExit as exit_signal:
                code = int(exit_signal.code or 0)
        return CliResult(code=code, out=out.getvalue(), err=err.getvalue())
