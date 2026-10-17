"""객체 조립: 저장 폴더를 준비하고 저장소와 서비스를 연결한다."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import DEFAULT_CATEGORIES, DataPaths
from .recurring import RecurringService
from .repository import TransactionRepository
from .services import BudgetService
from .stores import BudgetStore, CategoryStore, RecurringStore, SequenceStore


@dataclass(frozen=True)
class AppContext:
    """한 번의 명령 실행에 필요한 객체 묶음. 명령 처리기는 이 안의 서비스만 호출한다."""

    paths: DataPaths
    ledger: BudgetService
    recurring: RecurringService
    notices: tuple[str, ...]


def create_app(data_dir: Path) -> AppContext:
    paths = DataPaths(root=data_dir)
    notices = _initialize_storage(paths)
    sequence = SequenceStore(paths.meta)
    ledger = BudgetService(
        transactions=TransactionRepository(paths.transactions, sequence),
        categories=CategoryStore(paths.categories),
        budgets=BudgetStore(paths.budgets),
    )
    recurring = RecurringService(RecurringStore(paths.recurring, sequence), ledger)
    return AppContext(paths=paths, ledger=ledger, recurring=recurring, notices=notices)


def _initialize_storage(paths: DataPaths) -> tuple[str, ...]:
    """없는 폴더/파일을 만들고, 카테고리가 비어 있으면 기본 카테고리를 채운다."""
    notices: list[str] = []
    paths.root.mkdir(parents=True, exist_ok=True)
    missing = [path for path in paths.data_files if not path.exists()]
    for path in missing:
        path.touch()
    if missing:
        notices.append(f"저장 파일 {len(missing)}개를 새로 만들었습니다: {paths.root}")
    categories = CategoryStore(paths.categories)
    if not categories.names():
        categories.replace_all(DEFAULT_CATEGORIES)
        notices.append(f"기본 카테고리를 등록했습니다: {', '.join(DEFAULT_CATEGORIES)}")
    return tuple(notices)
