"""데이터 파일 백업: 타임스탬프 폴더에 현재 저장 파일을 그대로 복사한다."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from .config import DataPaths
from .errors import BudgetAppError

BACKUP_TIMESTAMP_FORMAT = "%Y%m%d-%H%M%S"


def create_backup(paths: DataPaths, now: datetime) -> tuple[Path, ...]:
    """backups/<타임스탬프>/ 아래에 복사하고, 만들어진 백업 파일 경로들을 반환한다."""
    target_dir = paths.backups / now.strftime(BACKUP_TIMESTAMP_FORMAT)
    if target_dir.exists():
        raise BudgetAppError(
            f"같은 시각의 백업이 이미 있습니다: {target_dir}", hint="1초 뒤에 다시 실행하세요."
        )
    target_dir.mkdir(parents=True)
    sources = [source for source in paths.data_files if source.exists()]
    return tuple(Path(shutil.copy2(source, target_dir / source.name)) for source in sources)
