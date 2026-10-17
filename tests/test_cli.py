"""진입점(main)을 통한 종단 간(E2E) 테스트: 명령 → 파일 저장 → 출력/종료 코드."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from budget_app import config
from budget_app.config import SEARCH_UNLIMITED_NOTICE_COUNT
from budget_app.decorators import handle_errors, log_call, timed
from budget_app.formatter import display_width, format_table, pad

from .helpers import DataDirTestCase, expense

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LUNCH = ("2024-01-15", "expense", "food", "15000", "점심", "meal")
SALARY = ("2024-01-14", "income", "salary", "3000000", "", "")
RENT = ("2024-01-05", "expense", "rent", "150000", "월세", "")


class CliFlowTests(DataDirTestCase):
    def add(self, *answers: str) -> None:
        self.assertEqual(self.run_cli("add", inputs=answers).code, 0)

    def test_add_prints_generated_id_and_persists(self) -> None:
        result = self.run_cli("add", inputs=LUNCH)

        self.assertEqual(result.code, 0)
        self.assertIn("[저장 완료] id=TX-000001", result.out)
        self.assertIn('"memo": "점심"', (self.data_dir / "transactions.jsonl").read_text("utf-8"))

    def test_add_reprompts_until_each_field_is_valid(self) -> None:
        answers = ("2024-13-40", "2024-01-15", "gift", "expense", "nope", "food", "0", "15000", "", "")

        result = self.run_cli("add", inputs=answers)

        self.assertEqual(result.code, 0)
        self.assertEqual(result.err.count("[오류]"), 4)
        self.assertIn("[힌트] 예: 2024-01-15", result.err)

    def test_add_cancelled_by_end_of_input_saves_nothing(self) -> None:
        result = self.run_cli("add", inputs=("2024-01-15", "expense"))

        self.assertEqual(result.code, 1)
        self.assertIn("[오류]", result.err)
        self.assertEqual((self.data_dir / "transactions.jsonl").read_text("utf-8"), "")

    def test_list_shows_newest_first_with_limit(self) -> None:
        for answers in (RENT, LUNCH, SALARY):
            self.add(*answers)

        result = self.run_cli("list", "--limit", "2")

        rows = [line for line in result.out.splitlines() if line.startswith("TX-")]
        self.assertEqual([row.split(" | ")[1] for row in rows], ["2024-01-15", "2024-01-14"])

    def test_list_on_empty_data_and_invalid_limit(self) -> None:
        self.assertIn("거래 내역이 없습니다", self.run_cli("list").out)
        self.assertEqual(self.run_cli("list", "--limit", "0").code, 1)

    def test_search_by_options(self) -> None:
        for answers in (RENT, LUNCH, SALARY):
            self.add(*answers)

        by_keyword = self.run_cli("search", "--q", "점심")
        by_range = self.run_cli("search", "--from", "2024-01-10", "--to", "2024-01-31", "--type", "income")
        nothing = self.run_cli("search", "--tag", "none")
        reversed_range = self.run_cli("search", "--from", "2024-02-01", "--to", "2024-01-01")

        self.assertIn("(총 1건)", by_keyword.out)
        self.assertIn("salary", by_range.out)
        self.assertNotIn("food", by_range.out)
        self.assertIn("조건에 맞는 거래가 없습니다", nothing.out)
        self.assertEqual(reversed_range.code, 1)

    def test_search_by_amount_range(self) -> None:
        for answers in (RENT, LUNCH, SALARY):
            self.add(*answers)

        large = self.run_cli("search", "--min-amount", "100,000")
        small_expense = self.run_cli("search", "--type", "expense", "--max-amount", "15000")
        inverted = self.run_cli("search", "--min-amount", "200", "--max-amount", "100")
        invalid = self.run_cli("search", "--min-amount", "abc")

        self.assertIn("(총 2건)", large.out)
        self.assertNotIn("food", large.out)
        self.assertIn("(총 1건)", small_expense.out)
        self.assertIn("점심", small_expense.out)
        self.assertEqual(inverted.code, 1)
        self.assertIn("최소 금액", inverted.err)
        self.assertEqual(invalid.code, 1)

    def test_budget_and_summary_with_warning(self) -> None:
        for answers in (RENT, LUNCH, SALARY):
            self.add(*answers)

        saved = self.run_cli("budget", "set", "--month", "2024-01", "--amount", "100000")
        summary = self.run_cli("summary", "--month", "2024-01", "--top", "1")

        self.assertIn("[저장 완료] 2024-01 예산 100000원", saved.out)
        for expected in ("총 수입: 3000000원", "총 지출: 165000원", "잔액: 2835000원",
                         "사용률 165.0%", "[경고] 예산을 65000원 초과", "1) rent 150000원"):
            self.assertIn(expected, summary.out)
        self.assertNotIn("food", summary.out)
        self.assertIn("2024-01 예산 100000원", self.run_cli("budget", "show", "--month", "2024-01").out)
        self.assertIn("- 2024-01: 100000원", self.run_cli("budget", "list").out)
        self.assertEqual(self.run_cli("budget", "show", "--month", "2030-01").code, 1)

    def test_budget_remove_command(self) -> None:
        self.run_cli("budget", "set", "--month", "2024-01", "--amount", "100000")

        removed = self.run_cli("budget", "remove", "--month", "2024-01")
        again = self.run_cli("budget", "remove", "--month", "2024-01")
        summary = self.run_cli("summary", "--month", "2024-01")

        self.assertIn("[삭제 완료] 2024-01 예산 100000원", removed.out)
        self.assertEqual(again.code, 1)
        self.assertIn("설정된 예산이 없습니다", self.run_cli("budget", "list").out)
        self.assertNotIn("예산", summary.out)

    def test_summary_without_data_says_so(self) -> None:
        result = self.run_cli("summary", "--month", "2020-01")

        self.assertEqual(result.code, 0)
        self.assertIn("데이터 없음", result.out)

    def test_category_commands(self) -> None:
        added = self.run_cli("category", "add", inputs=("hobby",))
        listed = self.run_cli("category", "list")
        self.add("2024-01-15", "expense", "hobby", "5000", "", "")
        blocked = self.run_cli("category", "remove", "--name", "hobby")
        moved = self.run_cli("category", "remove", "--name", "hobby", "--replace-with", "etc")

        self.assertIn("[저장 완료] category=hobby", added.out)
        self.assertIn("- hobby", listed.out)
        self.assertEqual(blocked.code, 1)
        self.assertIn("1건을 'etc' 카테고리로", moved.out)
        self.assertNotIn("hobby", self.run_cli("category", "list").out)

    def test_update_and_delete_by_id(self) -> None:
        self.add(*LUNCH)

        updated = self.run_cli("update", "--id", "TX-000001", "--amount", "18000", "--memo", "")
        missing_update = self.run_cli("update", "--id", "TX-000404", "--amount", "1")
        deleted = self.run_cli("delete", "--id", "TX-000001")
        missing_delete = self.run_cli("delete", "--id", "TX-000001")

        self.assertIn("[수정 완료] id=TX-000001", updated.out)
        self.assertIn("18000", updated.out)
        self.assertNotIn("점심", updated.out)
        self.assertEqual(missing_update.code, 1)
        self.assertIn("[삭제 완료] id=TX-000001", deleted.out)
        self.assertEqual(missing_delete.code, 1)
        self.assertIn("없는 데이터", missing_delete.err)
        self.assertIn("[힌트]", missing_delete.err)

    def test_export_and_import_report_counts(self) -> None:
        for answers in (RENT, LUNCH, SALARY):
            self.add(*answers)
        target = self.work_dir / "export.csv"

        exported = self.run_cli("export", "--out", str(target), "--month", "2024-01")
        imported = self.run_cli("import", "--from", str(target))
        no_period = self.run_cli("export", "--out", str(target))
        both = self.run_cli("export", "--out", str(target), "--month", "2024-01", "--from", "2024-01-01")

        self.assertIn("(3 records)", exported.out)
        self.assertIn("[완료] imported=3, skipped=0", imported.out)
        self.assertEqual((no_period.code, both.code), (1, 1))
        self.assertEqual(self.run_cli("import", "--from", "missing.csv").code, 1)

    def test_recurring_and_backup_commands(self) -> None:
        added = self.run_cli("recurring", "add", "--day", "25", "--type", "income",
                             "--category", "salary", "--amount", "3000000", "--memo", "월급")
        applied = self.run_cli("recurring", "apply", "--month", "2024-03")
        again = self.run_cli("recurring", "apply", "--month", "2024-03")
        backup = self.run_cli("backup")

        self.assertIn("id=RC-0001", added.out)
        self.assertIn("created=1", applied.out)
        self.assertIn("created=0, already_applied=1", again.out)
        self.assertIn("RC-0001", self.run_cli("recurring", "list").out)
        self.assertIn("[백업 완료]", backup.out)
        self.assertEqual(self.run_cli("recurring", "remove", "--id", "RC-0001").code, 0)

    def test_empty_states_are_explained(self) -> None:
        self.assertIn("설정된 예산이 없습니다", self.run_cli("budget", "list").out)
        self.assertIn("등록된 반복 규칙이 없습니다", self.run_cli("recurring", "list").out)

    def test_budget_near_limit_shows_caution_and_income_only_month_has_no_ranking(self) -> None:
        self.add(*LUNCH)
        self.add("2024-02-01", "income", "salary", "100", "", "")
        self.run_cli("budget", "set", "--month", "2024-01", "--amount", "16000")

        near_limit = self.run_cli("summary", "--month", "2024-01")
        income_only = self.run_cli("summary", "--month", "2024-02")

        self.assertIn("[주의] 예산의 80% 이상", near_limit.out)
        self.assertNotIn("[경고]", near_limit.out)
        self.assertIn("(지출 내역 없음)", income_only.out)

    def test_category_add_by_option_and_import_skip_reasons(self) -> None:
        source = self.work_dir / "in.csv"
        bad_rows = "".join(f"2024-01-{day:02d},expense,nope,1,,\n" for day in range(1, 13))
        source.write_text("date,type,category,amount,memo,tags\n" + bad_rows, encoding="utf-8")

        added = self.run_cli("category", "add", "--name", "hobby")
        imported = self.run_cli("import", "--from", str(source))

        self.assertIn("category=hobby", added.out)
        self.assertIn("imported=0, skipped=12", imported.out)
        self.assertIn("건너뜀 2행", imported.out)
        self.assertIn("외 2건", imported.out)

    def test_strict_import_exits_with_error_and_writes_nothing(self) -> None:
        source = self.work_dir / "mixed.csv"
        source.write_text(
            "date,type,category,amount\n2024-01-15,expense,food,1\n2024-99-99,expense,food,1\n",
            encoding="utf-8",
        )

        result = self.run_cli("import", "--from", str(source), "--strict")

        self.assertEqual(result.code, 1)
        self.assertIn("--strict", result.err)
        self.assertIn("거래 내역이 없습니다", self.run_cli("list").out)

    def test_export_by_date_range_and_recurring_failure_report(self) -> None:
        for answers in (RENT, LUNCH):
            self.add(*answers)
        target = self.work_dir / "range.csv"
        self.run_cli("category", "add", "--name", "gym")
        self.run_cli("recurring", "add", "--day", "1", "--type", "expense",
                     "--category", "gym", "--amount", "50000")
        blocked = self.run_cli("category", "remove", "--name", "gym")
        (self.data_dir / "categories.jsonl").write_text('{"name": "food"}\n', encoding="utf-8")

        exported = self.run_cli("export", "--out", str(target), "--from", "2024-01-10")
        applied = self.run_cli("recurring", "apply", "--month", "2024-01")

        self.assertEqual(blocked.code, 1)
        self.assertIn("반복 규칙이 1건", blocked.err)
        self.assertIn("(1 records)", exported.out)
        self.assertEqual(applied.code, 1)
        self.assertIn("failed=1", applied.out)
        self.assertIn("실패 RC-0001", applied.out)

    def test_category_replacement_also_moves_recurring_rules(self) -> None:
        self.run_cli("category", "add", "--name", "gym")
        self.run_cli("recurring", "add", "--day", "1", "--type", "expense",
                     "--category", "gym", "--amount", "50000")

        removed = self.run_cli("category", "remove", "--name", "gym", "--replace-with", "etc")
        applied = self.run_cli("recurring", "apply", "--month", "2024-01")

        self.assertIn("반복 규칙 1건을 'etc' 카테고리로", removed.out)
        self.assertEqual(applied.code, 0)
        self.assertIn("etc 50000원", applied.out)

    def test_hostile_values_are_rejected_as_validation_errors(self) -> None:
        huge = "9" * 5000
        for argv in (
            ["budget", "set", "--month", "2024-01", "--amount", huge],
            ["list", "--limit", huge],
            ["budget", "set", "--month", "2024-01", "--amount", "١٢٣"],
            ["budget", "set", "--month", "2024-01", "--amount", "1,5,0"],
        ):
            with self.subTest(argv=argv[:3]):
                result = self.run_cli(*argv)
                self.assertEqual(result.code, 1)
                self.assertIn("[힌트]", result.err)

    def test_control_characters_in_memo_cannot_break_the_table(self) -> None:
        self.add(*LUNCH)
        self.run_cli("update", "--id", "TX-000001", "--memo", "a\nb\x1b[31mred")

        listed = self.run_cli("list")

        self.assertEqual(len(listed.out.splitlines()), 3)
        self.assertNotIn("\x1b", listed.out)

    def test_unreadable_data_files_are_data_errors_not_unexpected_errors(self) -> None:
        self.add(*LUNCH)
        target = self.data_dir / "transactions.jsonl"
        broken_contents = (
            b"\xff\xfe\n",
            b'{"id": "TX-000001", "type": "expense", "date": 5, "amount": 1, "category": "food"}\n',
            b'{"id": "TX-000001", "type": "expense", "date": "2024-01-01", "amount": 1, "category": ["a"]}\n',
            b"[1, 2]\n",
        )
        for content in broken_contents:
            with self.subTest(content=content):
                target.write_bytes(content)
                result = self.run_cli("list")
                self.assertEqual(result.code, 1)
                self.assertIn("저장 파일", result.err)

    def test_every_command_supports_help(self) -> None:
        commands = (
            [], ["add"], ["list"], ["search"], ["summary"], ["update"], ["delete"], ["import"],
            ["export"], ["backup"], ["budget"], ["budget", "set"], ["budget", "remove"], ["category"],
            ["category", "remove"], ["recurring"], ["recurring", "apply"],
        )
        for command in commands:
            with self.subTest(command=command):
                result = self.run_cli(*command, "--help")
                self.assertEqual(result.code, 0)
                self.assertIn("usage:", result.out)
        self.assertFalse(self.data_dir.exists())

    def test_usage_errors_exit_with_2_and_hint(self) -> None:
        for argv in (["unknown"], [], ["delete"], ["list", "--lim", "3"]):
            with self.subTest(argv=argv):
                result = self.run_cli(*argv)
                self.assertEqual(result.code, 2)
                self.assertIn("[오류]", result.err)
                self.assertIn("[힌트]", result.err)

    def test_corrupted_data_file_is_reported_without_traceback(self) -> None:
        self.add(*LUNCH)
        (self.data_dir / "transactions.jsonl").write_text("{broken\n", encoding="utf-8")

        result = self.run_cli("list")

        self.assertEqual(result.code, 1)
        self.assertIn("1번째 줄", result.err)
        self.assertNotIn("Traceback", result.err)

    def test_data_dir_option_also_works_after_the_command(self) -> None:
        other = self.work_dir / "other"

        result = self.run_cli("category", "list", "--data-dir", str(other))

        self.assertEqual(result.code, 0)
        self.assertTrue((other / "categories.jsonl").exists())

    def test_search_without_limit_suggests_limit_when_result_is_large(self) -> None:
        ctx = self.app()
        ctx.ledger.add_transactions(
            [expense("2024-01-01", 1) for _ in range(SEARCH_UNLIMITED_NOTICE_COUNT + 1)]
        )

        unlimited = self.run_cli("search", "--category", "food")
        limited = self.run_cli("search", "--category", "food", "--limit", "5")

        self.assertIn(f"(총 {SEARCH_UNLIMITED_NOTICE_COUNT + 1}건)", unlimited.out)
        self.assertIn(f"[안내] 결과가 {SEARCH_UNLIMITED_NOTICE_COUNT + 1}건", unlimited.err)
        self.assertIn("--limit", unlimited.err)
        self.assertEqual(limited.err, "")

    def test_search_default_cap_from_config_applies_when_limit_is_omitted(self) -> None:
        ctx = self.app()
        ctx.ledger.add_transactions([expense("2024-01-01", 1) for _ in range(5)])

        with mock.patch.object(config, "SEARCH_DEFAULT_LIMIT", 2):
            capped = self.run_cli("search", "--category", "food")
            explicit = self.run_cli("search", "--category", "food", "--limit", "4")

        self.assertIn("(총 2건)", capped.out)
        self.assertIn("기본 상한 2건", capped.err)
        self.assertIn("(총 4건)", explicit.out)
        self.assertEqual(explicit.err, "")

    def test_import_skip_duplicates_option_reports_duplicates(self) -> None:
        source = self.work_dir / "dup.csv"
        source.write_text(
            "date,type,category,amount\n2024-01-15,expense,food,1\n2024-01-15,expense,food,1\n",
            encoding="utf-8",
        )

        first = self.run_cli("import", "--from", str(source), "--skip-duplicates")
        second = self.run_cli("import", "--from", str(source), "--skip-duplicates")

        self.assertIn("imported=2, skipped=0", first.out)  # 파일 안의 반복은 실제 거래로 본다
        self.assertIn("imported=0, skipped=2", second.out)
        self.assertIn("이미 있는 거래", second.out)

    def test_exit_codes_per_failure_case(self) -> None:
        """핵심 명령의 실패 사례마다 기대 종료 코드를 한 표로 고정한다."""
        self.add(*LUNCH)
        cases: list[tuple[tuple[str, ...], tuple[str, ...], int]] = [
            (("list",), (), 0),
            (("list", "--limit", "0"), (), 1),
            (("list", "--limit", "x"), (), 1),
            (("search", "--from", "2024-02-01", "--to", "2024-01-01"), (), 1),
            (("search", "--category", "nope"), (), 1),
            (("summary", "--month", "2024-1"), (), 1),
            (("summary",), (), 2),
            (("budget", "set", "--month", "2024-01", "--amount", "0"), (), 1),
            (("budget", "show", "--month", "2030-01"), (), 1),
            (("budget", "remove", "--month", "2030-01"), (), 1),
            (("category", "add", "--name", "food"), (), 1),
            (("category", "remove", "--name", "food"), (), 1),
            (("category", "remove", "--name", "food", "--replace-with", "food"), (), 1),
            (("update", "--id", "TX-000001"), (), 1),
            (("update", "--id", "TX-000001", "--category", "nope"), (), 1),
            (("update", "--id", "TX-999999", "--amount", "1"), (), 1),
            (("delete", "--id", "TX-999999"), (), 1),
            (("delete",), (), 2),
            (("import", "--from", str(self.work_dir / "missing.csv")), (), 1),
            (("import", "--from", str(self.work_dir)), (), 1),
            (("export", "--out", str(self.work_dir / "x.csv")), (), 1),
            (("export", "--out", str(self.work_dir / "no" / "dir" / "x.csv"), "--month", "2024-01"), (), 0),
            (("export", "--out", str(self.work_dir), "--month", "2024-01"), (), 1),
            (("recurring", "add", "--day", "32", "--type", "expense", "--category", "food", "--amount", "1"), (), 1),
            (("recurring", "remove", "--id", "RC-9999"), (), 1),
            (("recurring", "apply", "--month", "2024-01"), (), 0),
            (("add",), ("2024-01-15", "expense", "food", "100", "", ""), 0),
            (("add",), ("2024-01-15",), 1),
            (("nope",), (), 2),
        ]
        for argv, inputs, expected in cases:
            with self.subTest(argv=argv):
                self.assertEqual(self.run_cli(*argv, inputs=inputs).code, expected)

    def test_verbose_prints_log_and_elapsed_time(self) -> None:
        result = self.run_cli("list", "--verbose")

        self.assertIn("[log] 시작: BudgetService.list_recent", result.err)
        self.assertIn("소요 시간", result.err)


class ProcessTests(DataDirTestCase):
    def test_module_entry_point_returns_exit_codes(self) -> None:
        def run(*argv: str) -> subprocess.CompletedProcess:
            return subprocess.run(
                [sys.executable, "-m", "budget_app", "--data-dir", str(self.data_dir), *argv],
                cwd=PROJECT_ROOT, capture_output=True, text=True, encoding="utf-8", check=False,
            )

        ok = run("category", "list")
        failed = run("delete", "--id", "TX-000001")

        self.assertEqual(ok.returncode, 0)
        self.assertIn("- food", ok.stdout)
        self.assertEqual(failed.returncode, 1)
        self.assertNotIn("Traceback", failed.stderr)


class DecoratorAndFormatterTests(unittest.TestCase):
    def test_handle_errors_converts_exceptions_to_exit_codes(self) -> None:
        def raising(error: BaseException):
            @handle_errors
            def command() -> int:
                raise error
            return command

        with mock.patch("sys.stderr"):
            self.assertEqual(raising(KeyboardInterrupt())(), 130)
            self.assertEqual(raising(PermissionError(13, "Permission denied", "x"))(), 1)
            self.assertEqual(raising(RuntimeError("boom"))(), 3)
        self.assertEqual(handle_errors(lambda: 0)(), 0)

    def test_decorators_preserve_function_identity_and_result(self) -> None:
        @log_call
        @timed
        def double(value: int) -> int:
            """두 배."""
            return value * 2

        self.assertEqual(double(4), 8)
        self.assertEqual((double.__name__, double.__doc__), ("double", "두 배."))

    def test_log_call_reraises_after_logging(self) -> None:
        @log_call
        def fail() -> None:
            raise ValueError("x")

        with self.assertLogs("budget_app", level="DEBUG") as logs, self.assertRaises(ValueError):
            fail()
        self.assertTrue(any("실패" in line for line in logs.output))

    def test_table_alignment_counts_korean_as_double_width(self) -> None:
        self.assertEqual(display_width("점심a"), 5)
        self.assertEqual(pad("점심", 6), "점심  ")
        self.assertEqual(pad("15", 5, align_right=True), "   15")

        lines = format_table(("이름", "금액"), [("식비", "100"), ("rent", "20000")], frozenset({1}))

        self.assertEqual(len({display_width(line) for line in lines}), 1)


if __name__ == "__main__":
    unittest.main()
