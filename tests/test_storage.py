from __future__ import annotations

import types
import unittest

from budget_app.errors import DataFileError
from budget_app.models import Budget, Transaction
from budget_app.repository import TransactionRepository
from budget_app.storage import append_jsonl, atomic_open, read_jsonl, write_jsonl_atomic
from budget_app.stores import BudgetStore, CategoryStore, SequenceStore

from .helpers import DataDirTestCase, expense


class JsonlStorageTests(DataDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.path = self.work_dir / "items.jsonl"

    def test_read_is_a_lazy_generator(self) -> None:
        append_jsonl(self.path, [{"n": 1}, {"n": 2}])

        stream = read_jsonl(self.path, lambda raw: raw["n"])

        self.assertIsInstance(stream, types.GeneratorType)
        self.assertEqual(next(stream), 1)
        self.assertEqual(list(stream), [2])

    def test_missing_file_reads_as_empty(self) -> None:
        self.assertEqual(list(read_jsonl(self.path, dict)), [])

    def test_blank_lines_are_ignored_and_korean_is_stored_readable(self) -> None:
        self.path.write_text('{"memo": "점심"}\n\n{"memo": "저녁"}\n', encoding="utf-8")

        self.assertEqual(list(read_jsonl(self.path, lambda raw: raw["memo"])), ["점심", "저녁"])
        append_jsonl(self.path, [{"memo": "야식"}])
        self.assertIn("야식", self.path.read_text(encoding="utf-8"))

    def test_corrupted_line_reports_file_and_line_number(self) -> None:
        self.path.write_text('{"n": 1}\n{broken\n', encoding="utf-8")

        with self.assertRaises(DataFileError) as caught:
            list(read_jsonl(self.path, dict))

        self.assertIn("2번째 줄", caught.exception.message)
        self.assertTrue(caught.exception.hint)

    def test_record_with_missing_field_is_a_data_file_error(self) -> None:
        self.path.write_text('{"id": "TX-000001"}\n', encoding="utf-8")

        with self.assertRaises(DataFileError):
            list(read_jsonl(self.path, Transaction.from_dict))

    def test_atomic_write_replaces_whole_file(self) -> None:
        append_jsonl(self.path, [{"n": 1}, {"n": 2}])

        count = write_jsonl_atomic(self.path, [{"n": 3}])

        self.assertEqual(count, 1)
        self.assertEqual(list(read_jsonl(self.path, lambda raw: raw["n"])), [3])

    def test_failed_atomic_write_keeps_original_and_leaves_no_temp_file(self) -> None:
        append_jsonl(self.path, [{"n": 1}])

        def exploding_records():
            yield {"n": 2}
            raise RuntimeError("쓰는 도중 장애")

        with self.assertRaises(RuntimeError):
            write_jsonl_atomic(self.path, exploding_records())

        self.assertEqual(list(read_jsonl(self.path, lambda raw: raw["n"])), [1])
        self.assertEqual([path.name for path in self.work_dir.iterdir()], ["items.jsonl"])

    def test_append_repairs_missing_trailing_newline(self) -> None:
        self.path.write_text('{"n": 1}', encoding="utf-8")

        append_jsonl(self.path, [{"n": 2}])

        self.assertEqual(list(read_jsonl(self.path, lambda raw: raw["n"])), [1, 2])

    def test_atomic_write_keeps_file_permissions(self) -> None:
        append_jsonl(self.path, [{"n": 1}])
        self.path.chmod(0o640)

        write_jsonl_atomic(self.path, [{"n": 2}])

        self.assertEqual(self.path.stat().st_mode & 0o777, 0o640)

    def test_atomic_open_creates_parent_directory(self) -> None:
        target = self.work_dir / "nested" / "out.csv"

        with atomic_open(target) as file:
            file.write("ok")

        self.assertEqual(target.read_text(encoding="utf-8"), "ok")


class StoreTests(DataDirTestCase):
    def test_sequence_store_keeps_keys_independent(self) -> None:
        store = SequenceStore(self.work_dir / "meta.jsonl")

        self.assertIsNone(store.get("transaction"))
        store.set("transaction", 7)
        store.set("recurring", 2)
        store.set("transaction", 8)

        self.assertEqual((store.get("transaction"), store.get("recurring")), (8, 2))

    def test_category_store_add_and_remove(self) -> None:
        store = CategoryStore(self.work_dir / "categories.jsonl")
        store.add("food")
        store.add("rent")

        store.remove("food")

        self.assertEqual(store.names(), ["rent"])
        self.assertFalse(store.exists("food"))

    def test_budget_upsert_overwrites_same_month(self) -> None:
        store = BudgetStore(self.work_dir / "budgets.jsonl")
        store.upsert(Budget("2024-02", 100))
        store.upsert(Budget("2024-01", 200))
        store.upsert(Budget("2024-02", 300))

        self.assertEqual(list(store.iter_all()), [Budget("2024-01", 200), Budget("2024-02", 300)])
        self.assertIsNone(store.get("2024-03"))


class TransactionRepositoryTests(DataDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.sequence = SequenceStore(self.work_dir / "meta.jsonl")
        self.repo = TransactionRepository(self.work_dir / "transactions.jsonl", self.sequence)

    def test_ids_are_sequential(self) -> None:
        created = self.repo.add_many([expense("2024-01-01", 1), expense("2024-01-02", 2)])

        self.assertEqual([tx.id for tx in created], ["TX-000001", "TX-000002"])
        self.assertIsInstance(self.repo.iter_all(), types.GeneratorType)

    def test_deleted_id_is_never_reused(self) -> None:
        self.repo.add_many([expense("2024-01-01", 1), expense("2024-01-02", 2)])
        self.repo.rewrite(lambda tx: None if tx.id == "TX-000002" else tx)

        created = self.repo.add_many([expense("2024-01-03", 3)])

        self.assertEqual(created[0].id, "TX-000003")

    def test_sequence_recovers_from_data_when_meta_is_lost(self) -> None:
        self.repo.add_many([expense("2024-01-01", 1), expense("2024-01-02", 2)])
        (self.work_dir / "meta.jsonl").unlink()

        created = self.repo.add_many([expense("2024-01-03", 3)])

        self.assertEqual(created[0].id, "TX-000003")

    def test_rewrite_counts_changes_and_preserves_others(self) -> None:
        self.repo.add_many([expense("2024-01-01", 1), expense("2024-01-02", 2)])

        changed = self.repo.rewrite(lambda tx: None if tx.amount == 1 else tx)

        self.assertEqual(changed, 1)
        self.assertEqual([tx.id for tx in self.repo.iter_all()], ["TX-000002"])
        self.assertIsNone(self.repo.find_by_id("TX-000001"))

    def test_adding_nothing_does_not_touch_files(self) -> None:
        self.assertEqual(self.repo.add_many([]), [])
        self.assertIsNone(self.sequence.get("transaction"))


if __name__ == "__main__":
    unittest.main()
