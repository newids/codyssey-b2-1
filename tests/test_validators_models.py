from __future__ import annotations

import dataclasses
import unittest

from budget_app.errors import ValidationError
from budget_app.models import (
    Budget,
    MonthlySummary,
    SearchCriteria,
    Transaction,
    TransactionInput,
    id_number,
)
from budget_app.validators import (
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


class ValidatorTests(unittest.TestCase):
    def test_accepts_real_date(self) -> None:
        self.assertEqual(parse_date(" 2024-02-29 "), "2024-02-29")

    def test_rejects_impossible_or_malformed_dates(self) -> None:
        for text in ("2024-13-40", "2023-02-29", "20240115", "2024-1-5", "", "어제"):
            with self.subTest(text=text), self.assertRaises(ValidationError) as caught:
                parse_date(text)
            self.assertIn("2024-01-15", caught.exception.hint)

    def test_month_must_be_yyyy_mm(self) -> None:
        self.assertEqual(parse_month("2024-01"), "2024-01")
        for text in ("2024-13", "2024-1", "2024-01-01"):
            with self.subTest(text=text), self.assertRaises(ValidationError):
                parse_month(text)

    def test_month_range_knows_leap_year(self) -> None:
        self.assertEqual(month_range("2024-02"), ("2024-02-01", "2024-02-29"))
        self.assertEqual(month_range("2023-02"), ("2023-02-01", "2023-02-28"))

    def test_amount_must_be_positive_integer(self) -> None:
        self.assertEqual(parse_amount("15,000"), 15000)
        for text in ("0", "-5", "1.5", "abc", ""):
            with self.subTest(text=text), self.assertRaises(ValidationError):
                parse_amount(text)

    def test_type_is_normalized_and_restricted(self) -> None:
        self.assertEqual(parse_type(" Expense "), "expense")
        with self.assertRaises(ValidationError):
            parse_type("spend")

    def test_tags_are_trimmed_and_deduplicated_in_order(self) -> None:
        self.assertEqual(parse_tags(" meal, ,work,meal "), ("meal", "work"))
        self.assertEqual(parse_tags(""), ())

    def test_category_name_rules(self) -> None:
        self.assertEqual(parse_category_name(" 식비 "), "식비")
        for text in ("", "a,b", "a|b", "two words", "x" * 31):
            with self.subTest(text=text), self.assertRaises(ValidationError):
                parse_category_name(text)

    def test_positive_int_and_recurring_day_bounds(self) -> None:
        self.assertEqual(parse_positive_int("3", "--limit"), 3)
        self.assertEqual(parse_recurring_day("31"), 31)
        for call in (
            lambda: parse_positive_int("0", "--limit"),
            lambda: parse_recurring_day("32"),
            lambda: parse_recurring_day("0"),
        ):
            with self.assertRaises(ValidationError):
                call()


class ModelTests(unittest.TestCase):
    def test_transaction_round_trips_through_dict(self) -> None:
        tx = Transaction("TX-000001", "expense", "2024-01-15", 15000, "food", "점심", ("meal",))

        self.assertEqual(Transaction.from_dict(tx.to_dict()), tx)

    def test_transaction_is_immutable(self) -> None:
        tx = Transaction("TX-000001", "expense", "2024-01-15", 15000, "food")

        with self.assertRaises(dataclasses.FrozenInstanceError):
            tx.amount = 1  # type: ignore[misc]

    def test_model_rejects_invalid_state_even_when_built_directly(self) -> None:
        invalid_inputs = (
            dict(type="gift", date="2024-01-15", amount=1, category="food"),
            dict(type="expense", date="2024-01-32", amount=1, category="food"),
            dict(type="expense", date="2024-01-15", amount=0, category="food"),
            dict(type="expense", date="2024-01-15", amount=True, category="food"),
            dict(type="expense", date="2024-01-15", amount=1, category=""),
        )
        for fields in invalid_inputs:
            with self.subTest(fields=fields), self.assertRaises(ValidationError):
                TransactionInput(**fields)

    def test_replace_revalidates(self) -> None:
        tx = Transaction("TX-000001", "expense", "2024-01-15", 15000, "food")

        with self.assertRaises(ValidationError):
            dataclasses.replace(tx, amount=-1)

    def test_sort_key_orders_by_date_then_id_number(self) -> None:
        older = Transaction("TX-000009", "expense", "2024-01-15", 1, "food")
        newer = Transaction("TX-000010", "expense", "2024-01-15", 1, "food")

        self.assertLess(older.sort_key, newer.sort_key)
        self.assertEqual(id_number("TX-000012"), 12)
        self.assertEqual(id_number("broken"), 0)

    def test_budget_requires_positive_amount_and_valid_month(self) -> None:
        with self.assertRaises(ValidationError):
            Budget(month="2024-01", amount=0)
        with self.assertRaises(ValidationError):
            Budget(month="2024-1", amount=1000)

    def test_criteria_filters_every_condition(self) -> None:
        tx = Transaction("TX-000001", "expense", "2024-01-15", 15000, "food", "회사 점심", ("meal",))

        self.assertTrue(SearchCriteria().matches(tx))
        self.assertTrue(
            SearchCriteria("2024-01-15", "2024-01-15", "food", "expense", "점심", "meal").matches(tx)
        )
        for criteria in (
            SearchCriteria(date_from="2024-01-16"),
            SearchCriteria(date_to="2024-01-14"),
            SearchCriteria(category="rent"),
            SearchCriteria(type="income"),
            SearchCriteria(keyword="저녁"),
            SearchCriteria(tag="mea"),
        ):
            with self.subTest(criteria=criteria):
                self.assertFalse(criteria.matches(tx))

    def test_criteria_rejects_reversed_range(self) -> None:
        with self.assertRaises(ValidationError):
            SearchCriteria(date_from="2024-02-01", date_to="2024-01-01")

    def test_summary_derives_balance_and_budget_usage(self) -> None:
        summary = MonthlySummary("2024-01", 3, 1000, 600, (("food", 600),), budget=500)

        self.assertEqual(summary.balance, 400)
        self.assertAlmostEqual(summary.usage_rate or 0, 120.0)
        self.assertTrue(summary.is_over_budget)
        self.assertIsNone(MonthlySummary("2024-01", 0, 0, 0, ()).usage_rate)


if __name__ == "__main__":
    unittest.main()
