from __future__ import annotations

import itertools
import time
import unicodedata
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from unittest import mock

from budget_app import repository
from budget_app.backup import create_backup
from budget_app.csv_io import export_transactions, import_transactions
from budget_app.errors import BudgetAppError, DataFileError, NotFoundError, ValidationError
from budget_app.models import SearchCriteria
from budget_app.repository import TransactionRepository
from budget_app.stores import CategoryStore

from .helpers import DataDirTestCase, expense, income

LARGE_CSV_ROWS = 10_000
LARGE_CSV_TIME_LIMIT_SECONDS = 10.0


class LedgerTests(DataDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.ctx = self.app()
        self.ledger = self.ctx.ledger

    def seed(self) -> None:
        self.ledger.add_transactions(
            [
                expense("2024-01-12", 20000, "transport"),
                income("2024-01-14", 3000000),
                expense("2024-01-15", 15000, memo="회사 점심", tags=("meal",)),
                expense("2024-01-05", 150000, "rent", memo="월세"),
                expense("2024-01-20", 30000, memo="저녁", tags=("meal", "friends")),
                expense("2024-02-01", 9000),
            ]
        )

    def test_first_run_creates_files_and_default_categories(self) -> None:
        self.assertTrue(self.ctx.notices)
        self.assertIn("food", self.ledger.list_categories())
        for path in (self.ctx.paths.transactions, self.ctx.paths.categories, self.ctx.paths.budgets):
            self.assertTrue(path.exists())
        self.assertEqual(self.app().notices, ())

    def test_add_rejects_unregistered_category(self) -> None:
        with self.assertRaises(ValidationError) as caught:
            self.ledger.add_transaction(expense("2024-01-01", 1000, "unknown"))

        self.assertIn("category add", caught.exception.hint)
        self.assertEqual(self.ledger.list_recent(10), [])

    def test_bulk_add_is_all_or_nothing_on_validation(self) -> None:
        with self.assertRaises(ValidationError):
            self.ledger.add_transactions([expense("2024-01-01", 1), expense("2024-01-02", 2, "nope")])

        self.assertEqual(self.ledger.list_recent(10), [])

    def test_list_recent_is_newest_first_and_limited(self) -> None:
        self.seed()

        recent = self.ledger.list_recent(3)

        self.assertEqual([tx.date for tx in recent], ["2024-02-01", "2024-01-20", "2024-01-15"])

    def test_same_day_transactions_show_latest_id_first(self) -> None:
        self.ledger.add_transactions([expense("2024-01-01", 1), expense("2024-01-01", 2)])

        self.assertEqual([tx.amount for tx in self.ledger.list_recent(2)], [2, 1])

    def test_search_combines_conditions_newest_first(self) -> None:
        self.seed()

        by_tag = self.ledger.search(SearchCriteria(tag="meal"))
        by_range = self.ledger.search(
            SearchCriteria(date_from="2024-01-10", date_to="2024-01-15", type="expense")
        )
        limited = self.ledger.search(SearchCriteria(category="food"), limit=1)

        self.assertEqual([tx.date for tx in by_tag], ["2024-01-20", "2024-01-15"])
        self.assertEqual([tx.date for tx in by_range], ["2024-01-15", "2024-01-12"])
        self.assertEqual([tx.date for tx in limited], ["2024-02-01"])
        self.assertEqual(self.ledger.search(SearchCriteria(keyword="없는말")), [])

    def test_search_filters_by_amount_range_inclusive(self) -> None:
        self.ledger.add_transactions(
            [expense("2024-03-01", 4999), expense("2024-03-02", 5000), expense("2024-03-03", 20000)]
        )

        at_least = self.ledger.search(SearchCriteria(min_amount=5000))
        at_most = self.ledger.search(SearchCriteria(max_amount=5000))
        between = self.ledger.search(SearchCriteria(min_amount=5000, max_amount=19999))

        self.assertEqual([tx.amount for tx in at_least], [20000, 5000])
        self.assertEqual([tx.amount for tx in at_most], [5000, 4999])
        self.assertEqual([tx.amount for tx in between], [5000])

    def test_search_rejects_min_amount_greater_than_max(self) -> None:
        with self.assertRaises(ValidationError):
            SearchCriteria(min_amount=10000, max_amount=9999)

    def test_update_changes_only_given_fields(self) -> None:
        self.seed()

        updated = self.ledger.update_transaction("TX-000003", {"amount": 18000, "tags": ()})

        stored = self.ledger.search(SearchCriteria(keyword="회사"))[0]
        self.assertEqual(stored, updated)
        self.assertEqual((stored.amount, stored.tags, stored.memo), (18000, (), "회사 점심"))
        self.assertEqual(len(self.ledger.list_recent(100)), 6)

    def test_update_failures_leave_data_untouched(self) -> None:
        self.seed()
        before = self.ctx.paths.transactions.read_text(encoding="utf-8")

        with self.assertRaises(NotFoundError):
            self.ledger.update_transaction("TX-999999", {"amount": 1})
        with self.assertRaises(ValidationError):
            self.ledger.update_transaction("TX-000001", {})
        with self.assertRaises(ValidationError):
            self.ledger.update_transaction("TX-000001", {"category": "unknown"})
        with self.assertRaises(ValidationError):
            self.ledger.update_transaction("TX-000001", {"amount": -1})
        with self.assertRaises(ValidationError):
            self.ledger.update_transaction("TX-000001", {"id": "TX-000002"})

        self.assertEqual(self.ctx.paths.transactions.read_text(encoding="utf-8"), before)

    def test_delete_removes_one_and_unknown_id_is_not_found(self) -> None:
        self.seed()

        deleted = self.ledger.delete_transaction("TX-000001")

        self.assertEqual(deleted.category, "transport")
        self.assertEqual(len(self.ledger.list_recent(100)), 5)
        with self.assertRaises(NotFoundError) as caught:
            self.ledger.delete_transaction("TX-000001")
        self.assertIn("없는 데이터", caught.exception.message)

    def test_summary_totals_and_top_categories(self) -> None:
        self.seed()

        summary = self.ledger.summarize("2024-01", top=2)

        self.assertEqual((summary.count, summary.total_income, summary.total_expense), (5, 3000000, 215000))
        self.assertEqual(summary.balance, 2785000)
        self.assertEqual(summary.top_expenses, (("rent", 150000), ("food", 45000)))
        self.assertIsNone(summary.budget)

    def test_summary_of_empty_month_has_no_data(self) -> None:
        self.seed()

        self.assertFalse(self.ledger.summarize("2023-12", top=3).has_data)

    def test_budget_is_persisted_and_reflected_in_summary(self) -> None:
        self.seed()
        self.ledger.set_budget("2024-01", 500000)
        self.ledger.set_budget("2024-01", 200000)

        summary = self.app().ledger.summarize("2024-01", top=3)

        self.assertEqual(summary.budget, 200000)
        self.assertAlmostEqual(summary.usage_rate or 0, 107.5)
        self.assertTrue(summary.is_over_budget)
        self.assertEqual(len(self.ledger.list_budgets()), 1)

    def test_budget_remove_drops_month_and_summary_loses_budget_line(self) -> None:
        self.seed()
        self.ledger.set_budget("2024-01", 500000)
        self.ledger.set_budget("2024-02", 100000)

        removed = self.ledger.remove_budget("2024-01")

        self.assertEqual(removed.amount, 500000)
        self.assertIsNone(self.ledger.summarize("2024-01", 3).budget)
        self.assertEqual([b.month for b in self.ledger.list_budgets()], ["2024-02"])
        with self.assertRaises(NotFoundError):
            self.ledger.remove_budget("2024-01")

    def test_category_add_rejects_duplicates(self) -> None:
        self.assertEqual(self.ledger.add_category(" hobby "), "hobby")
        with self.assertRaises(ValidationError):
            self.ledger.add_category("hobby")

    def test_category_in_use_cannot_be_removed_without_replacement(self) -> None:
        self.seed()

        with self.assertRaises(ValidationError) as caught:
            self.ledger.remove_category("food")

        self.assertIn("--replace-with", caught.exception.hint)
        self.assertIn("food", self.ledger.list_categories())

    def test_category_removal_with_replacement_moves_transactions(self) -> None:
        self.seed()

        moved = self.ledger.remove_category("food", replace_with="etc")

        self.assertEqual(moved, 3)
        self.assertNotIn("food", self.ledger.list_categories())
        self.assertEqual(len(self.ledger.search(SearchCriteria(category="etc"))), 3)

    def test_category_removal_guards(self) -> None:
        self.assertEqual(self.ledger.remove_category("shopping"), 0)
        with self.assertRaises(ValidationError):
            self.ledger.remove_category("shopping")
        with self.assertRaises(ValidationError):
            self.ledger.remove_category("food", replace_with="food")
        with self.assertRaises(ValidationError):
            self.ledger.remove_category("food", replace_with="unknown")


class CsvTransferTests(DataDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.ledger = self.app().ledger
        self.csv_path = self.work_dir / "data.csv"

    def test_export_then_import_round_trips(self) -> None:
        self.ledger.add_transactions(
            [
                expense("2024-01-15", 15000, memo='쉼표, "따옴표" 메모', tags=("meal", "work")),
                income("2024-01-14", 3000000),
                expense("2024-02-01", 9000),
            ]
        )

        exported = export_transactions(
            self.ledger, self.csv_path, SearchCriteria(date_from="2024-01-01", date_to="2024-01-31")
        )
        result = import_transactions(self.ledger, self.csv_path)

        self.assertEqual(exported, 2)
        self.assertEqual((result.imported, result.skipped), (2, ()))
        self.assertTrue(self.csv_path.read_text(encoding="utf-8").startswith("date,type,category,amount,memo,tags"))
        copies = self.ledger.search(SearchCriteria(keyword="따옴표"))
        self.assertEqual(len(copies), 2)
        self.assertEqual(copies[0].tags, ("meal", "work"))

    def test_import_skips_invalid_rows_with_reasons(self) -> None:
        self.csv_path.write_text(
            "date,type,category,amount,memo,tags\n"
            "2024-01-15,expense,food,15000,점심,meal\n"
            "2024-13-40,expense,food,15000,,\n"
            "2024-01-16,expense,unknown,15000,,\n"
            "2024-01-17,expense,food,-1,,\n"
            "2024-01-18,income,salary,100\n",
            encoding="utf-8",
        )

        result = import_transactions(self.ledger, self.csv_path)

        self.assertEqual(result.imported, 2)
        self.assertEqual([reason.split(":")[0] for reason in result.skipped], ["3행", "4행", "5행"])

    def test_strict_import_registers_nothing_when_any_row_is_invalid(self) -> None:
        self.csv_path.write_text(
            "date,type,category,amount,memo,tags\n"
            "2024-01-15,expense,food,15000,점심,meal\n"
            "2024-13-40,expense,food,15000,,\n",
            encoding="utf-8",
        )

        with self.assertRaises(ValidationError) as caught:
            import_transactions(self.ledger, self.csv_path, strict=True)

        self.assertIn("3행", caught.exception.message)
        self.assertEqual(self.ledger.list_recent(10), [])

    def test_strict_import_succeeds_when_every_row_is_valid(self) -> None:
        self.csv_path.write_text(
            "date,type,category,amount\n2024-01-15,expense,food,15000\n", encoding="utf-8"
        )

        result = import_transactions(self.ledger, self.csv_path, strict=True)

        self.assertEqual((result.imported, result.skipped), (1, ()))

    def test_skip_duplicates_ignores_rows_already_stored_and_repeated_in_file(self) -> None:
        self.ledger.add_transaction(expense("2024-01-15", 15000, memo="점심", tags=("old",)))
        self.csv_path.write_text(
            "date,type,category,amount,memo,tags\n"
            "2024-01-15,expense,food,15000, 점심 ,new\n"    # 저장된 거래와 같음(태그·메모 공백은 무시)
            "2024-01-16,expense,food,15000,점심,\n"         # 날짜가 다르므로 새 거래
            "2024-01-16,expense,food,15000,점심,\n"         # 같은 날 같은 금액을 실제로 두 번 쓴 경우: 남는다
            "2024-01-16,expense,food,15000,저녁,\n"         # 메모가 다르므로 새 거래
            "2024-13-40,expense,food,1,,\n",                 # 잘못된 행
            encoding="utf-8",
        )

        first = import_transactions(self.ledger, self.csv_path, skip_duplicates=True)
        again = import_transactions(self.ledger, self.csv_path, skip_duplicates=True)
        plain = import_transactions(self.ledger, self.csv_path)

        self.assertEqual(first.imported, 3)
        self.assertEqual([reason.split(":")[0] for reason in first.skipped], ["2행", "6행"])
        self.assertIn("이미 있는 거래", first.skipped[0])
        self.assertEqual(again.imported, 0)  # 같은 파일을 다시 넣으면 저장된 개수만큼 모두 상쇄된다
        self.assertEqual(len(again.skipped), 5)
        self.assertEqual(plain.imported, 4)  # 옵션이 없으면 전부 다시 등록된다

    def test_strict_import_with_skip_duplicates_only_fails_on_invalid_rows(self) -> None:
        self.ledger.add_transaction(expense("2024-01-15", 15000))
        self.csv_path.write_text(
            "date,type,category,amount\n2024-01-15,expense,food,15000\n2024-01-16,expense,food,1\n",
            encoding="utf-8",
        )

        result = import_transactions(self.ledger, self.csv_path, strict=True, skip_duplicates=True)

        self.assertEqual((result.imported, len(result.skipped)), (1, 1))

    def test_import_accepts_excel_bom_and_optional_columns_missing(self) -> None:
        self.csv_path.write_text(
            "date,type,category,amount\n2024-01-15,expense,food,15000\n", encoding="utf-8-sig"
        )

        self.assertEqual(import_transactions(self.ledger, self.csv_path).imported, 1)

    def test_import_tolerates_header_case_and_decomposed_korean(self) -> None:
        self.ledger.add_category("식비")
        decomposed = unicodedata.normalize("NFD", "식비")
        self.csv_path.write_text(
            f"Date, Type ,CATEGORY,amount\n2024-01-15,expense,{decomposed},15000\n", encoding="utf-8"
        )

        result = import_transactions(self.ledger, self.csv_path)

        self.assertEqual((result.imported, result.skipped), (1, ()))
        self.assertEqual(self.ledger.list_recent(1)[0].category, "식비")

    def test_import_rejects_bad_files(self) -> None:
        with self.assertRaises(NotFoundError):
            import_transactions(self.ledger, self.work_dir / "none.csv")

        self.csv_path.write_text("date,type,amount\n2024-01-15,expense,1\n", encoding="utf-8")
        with self.assertRaises(DataFileError) as caught:
            import_transactions(self.ledger, self.csv_path)
        self.assertIn("category", caught.exception.message)

        self.csv_path.write_bytes("date,type,category,amount\n2024-01-15,expense,food,1,점심\n".encode("cp949"))
        with self.assertRaises(DataFileError):
            import_transactions(self.ledger, self.csv_path)

    def test_large_csv_import_registers_every_row_in_one_append(self) -> None:
        rows = "".join(
            f"2024-{1 + index % 12:02d}-{1 + index % 28:02d},expense,food,{100 + index},메모 {index},bulk\n"
            for index in range(LARGE_CSV_ROWS)
        )
        self.csv_path.write_text("date,type,category,amount,memo,tags\n" + rows, encoding="utf-8")

        started = time.perf_counter()
        result = import_transactions(self.ledger, self.csv_path)
        elapsed = time.perf_counter() - started

        self.assertEqual((result.imported, result.skipped), (LARGE_CSV_ROWS, ()))
        self.assertEqual(sum(1 for _ in self.ledger.iter_matching(SearchCriteria())), LARGE_CSV_ROWS)
        self.assertLess(elapsed, LARGE_CSV_TIME_LIMIT_SECONDS, msg=f"import took {elapsed:.2f}s")

    def test_interrupted_import_leaves_readable_file_and_never_reuses_ids(self) -> None:
        self.csv_path.write_text(
            "date,type,category,amount\n"
            "2024-01-01,expense,food,1\n"
            "2024-01-02,expense,food,2\n"
            "2024-01-03,expense,food,3\n",
            encoding="utf-8",
        )
        real_append = repository.append_jsonl

        def append_two_then_fail(path: Path, records: Iterable[dict[str, Any]]) -> int:
            real_append(path, itertools.islice(records, 2))
            raise OSError(28, "No space left on device")

        with mock.patch.object(repository, "append_jsonl", append_two_then_fail):
            with self.assertRaises(OSError):
                import_transactions(self.ledger, self.csv_path)
        partial = [tx.id for tx in self.ledger.iter_matching(SearchCriteria())]
        retried = import_transactions(self.ledger, self.csv_path)
        all_ids = [tx.id for tx in self.ledger.iter_matching(SearchCriteria())]

        self.assertEqual(partial, ["TX-000001", "TX-000002"])
        self.assertEqual(retried.imported, 3)
        self.assertEqual(all_ids[2:], ["TX-000004", "TX-000005", "TX-000006"])
        self.assertEqual(len(all_ids), len(set(all_ids)))


class RecurringAndBackupTests(DataDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.ctx = self.app()

    def test_apply_creates_once_and_clamps_day_to_month_end(self) -> None:
        rule = self.ctx.recurring.add_rule(31, "expense", "rent", 500000, "월세")
        self.ctx.recurring.add_rule(25, "income", "salary", 3000000, "월급")

        first = self.ctx.recurring.apply("2024-02")
        second = self.ctx.recurring.apply("2024-02")

        self.assertEqual([tx.date for tx in first.created], ["2024-02-29", "2024-02-25"])
        self.assertEqual(first.created[0].tags, (rule.marker_tag,))
        self.assertEqual((len(second.created), len(second.already_applied)), (0, 2))
        self.assertEqual(len(self.ctx.recurring.apply("2024-03").created), 2)

    def test_rule_with_removed_category_is_reported_not_crashed(self) -> None:
        self.ctx.ledger.add_category("gym")
        self.ctx.recurring.add_rule(1, "expense", "gym", 50000, "")
        self.ctx.ledger.remove_category("gym")

        result = self.ctx.recurring.apply("2024-01")

        self.assertEqual((len(result.created), len(result.failed)), (0, 1))

    def test_rule_management(self) -> None:
        with self.assertRaises(ValidationError):
            self.ctx.recurring.add_rule(1, "expense", "unknown", 1, "")
        rule = self.ctx.recurring.add_rule(1, "expense", "rent", 1, "")

        self.assertEqual(self.ctx.recurring.remove_rule(rule.id), rule)
        self.assertEqual(self.ctx.recurring.list_rules(), [])
        with self.assertRaises(NotFoundError):
            self.ctx.recurring.remove_rule(rule.id)
        self.assertEqual(self.ctx.recurring.add_rule(1, "expense", "rent", 1, "").id, "RC-0002")

    def test_interrupted_category_replacement_leaves_no_dangling_reference(self) -> None:
        self.ctx.ledger.add_category("gym")
        self.ctx.ledger.add_transaction(expense("2024-01-10", 50000, "gym"))
        self.ctx.recurring.add_rule(1, "expense", "gym", 50000, "헬스장")

        with mock.patch.object(
            TransactionRepository,
            "rewrite",
            autospec=True,
            side_effect=OSError(5, "Input/output error"),
        ):
            with self.assertRaises(BudgetAppError) as caught:
                self.ctx.recurring.remove_category("gym", replace_with="etc")
        transaction_after_failure = self.ctx.ledger.list_recent(1)[0]
        rule_after_failure = self.ctx.recurring.list_rules()[0]
        categories_after_failure = self.ctx.ledger.list_categories()
        retried = self.ctx.recurring.remove_category("gym", replace_with="etc")

        # 규칙 → 거래 → 카테고리 순서로 처리하므로, 중간에 멈춰도 지워진 카테고리를 가리키는 데이터가 없다.
        # 재실행은 남은 단계만 수행하므로 이미 옮겨진 규칙은 0건으로 보고된다.
        self.assertIn("Input/output error", caught.exception.message)
        self.assertIn("완료: 반복 규칙 1건", caught.exception.hint)
        self.assertIn("남음: 거래 1건을 'etc' 로 이동, 카테고리 'gym' 삭제", caught.exception.hint)
        self.assertEqual(rule_after_failure.category, "etc")
        self.assertEqual(transaction_after_failure.category, "gym")
        self.assertIn("gym", categories_after_failure)
        self.assertEqual((retried.transactions, retried.rules), (1, 0))
        self.assertEqual(self.ctx.ledger.list_recent(1)[0].category, "etc")
        self.assertNotIn("gym", self.ctx.ledger.list_categories())

    def test_failure_at_last_step_reports_moved_counts_and_remaining_step(self) -> None:
        self.ctx.ledger.add_category("gym")
        self.ctx.ledger.add_transaction(expense("2024-01-10", 50000, "gym"))

        with mock.patch.object(
            CategoryStore, "remove", autospec=True, side_effect=OSError(5, "Input/output error")
        ):
            with self.assertRaises(BudgetAppError) as caught:
                self.ctx.recurring.remove_category("gym", replace_with="etc")

        self.assertIn("완료: 거래 1건", caught.exception.hint)
        self.assertIn("남음: 카테고리 'gym' 삭제", caught.exception.hint)
        self.assertEqual(self.ctx.ledger.list_recent(1)[0].category, "etc")
        self.assertIn("gym", self.ctx.ledger.list_categories())

    def test_failure_before_any_step_reports_nothing_done(self) -> None:
        self.ctx.ledger.add_category("gym")

        with mock.patch.object(
            CategoryStore, "remove", autospec=True, side_effect=OSError(5, "Input/output error")
        ):
            with self.assertRaises(BudgetAppError) as caught:
                self.ctx.recurring.remove_category("gym")

        self.assertIn("카테고리 삭제 도중 실패", caught.exception.message)
        self.assertIn("완료: 없음 / 남음: 카테고리 'gym' 삭제", caught.exception.hint)

    def test_backup_copies_data_files_into_timestamped_folder(self) -> None:
        self.ctx.ledger.add_transaction(expense("2024-01-01", 1000))
        moment = datetime(2024, 1, 31, 23, 59, 58)

        copied = create_backup(self.ctx.paths, moment)

        self.assertEqual(copied[0].parent.name, "20240131-235958")
        self.assertEqual(
            (copied[0].parent / "transactions.jsonl").read_text(encoding="utf-8"),
            self.ctx.paths.transactions.read_text(encoding="utf-8"),
        )
        with self.assertRaises(BudgetAppError):
            create_backup(self.ctx.paths, moment)


if __name__ == "__main__":
    unittest.main()
