"""저장 위치와 기본값."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_DATA_DIR = "./data"
DEFAULT_LIST_LIMIT = 10
DEFAULT_TOP_N = 3
BUDGET_WARNING_RATE = 80.0  # 예산 사용률이 이 값(%) 이상이면 summary 에 [주의] 를 붙인다
SEARCH_UNLIMITED_NOTICE_COUNT = 1000  # --limit 없는 search 결과가 이보다 많으면 안내를 띄운다
# --limit 없는 search 의 기본 상한. None 이면 전체 출력. 숫자를 주면 그 건수만 보여 주고 안내한다.
SEARCH_DEFAULT_LIMIT: int | None = None
DEFAULT_CATEGORIES: tuple[str, ...] = (
    "food",
    "transport",
    "rent",
    "salary",
    "shopping",
    "etc",
)


@dataclass(frozen=True)
class DataPaths:
    """데이터 폴더 안의 파일 경로 묶음."""

    root: Path

    @property
    def transactions(self) -> Path:
        return self.root / "transactions.jsonl"

    @property
    def categories(self) -> Path:
        return self.root / "categories.jsonl"

    @property
    def budgets(self) -> Path:
        return self.root / "budgets.jsonl"

    @property
    def recurring(self) -> Path:
        return self.root / "recurring.jsonl"

    @property
    def meta(self) -> Path:
        return self.root / "meta.jsonl"

    @property
    def backups(self) -> Path:
        return self.root / "backups"

    @property
    def data_files(self) -> tuple[Path, ...]:
        return (self.transactions, self.categories, self.budgets, self.recurring, self.meta)
