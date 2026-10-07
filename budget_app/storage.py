"""JSONL 파일 입출력의 가장 낮은 계층: 스트리밍 읽기와 원자적 쓰기."""

from __future__ import annotations

import json
import os
import secrets
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, TextIO, TypeVar

from .errors import DataFileError, ValidationError

T = TypeVar("T")

ENCODING = "utf-8"


def read_jsonl(path: Path, decode: Callable[[dict[str, Any]], T]) -> Iterator[T]:
    """파일을 한 줄씩 읽어 객체로 바꿔 내보내는 제너레이터.

    파일 전체를 메모리에 올리지 않으므로 파일 크기와 무관하게 메모리 사용량이 일정하다.
    파일이 없으면 아무것도 내보내지 않는다.
    """
    if not path.exists():
        return
    line_number = 0
    try:
        with path.open("r", encoding=ENCODING) as file:
            for line_number, line in enumerate(file, start=1):
                if not line.strip():
                    continue
                yield _decode_line(path, line_number, line, decode)
    except UnicodeDecodeError as error:
        raise DataFileError(
            f"저장 파일이 UTF-8 이 아닙니다: {path} {line_number + 1}번째 줄 부근",
            hint="파일을 UTF-8 로 다시 저장하거나, backups 폴더의 백업으로 복구하세요.",
        ) from error


def _decode_line(
    path: Path, line_number: int, line: str, decode: Callable[[dict[str, Any]], T]
) -> T:
    try:
        raw = json.loads(line)
        if not isinstance(raw, dict):
            raise TypeError("JSON 객체가 아닙니다")
        return decode(raw)
    except (ValueError, KeyError, TypeError, AttributeError, ValidationError) as error:
        raise DataFileError(
            f"저장 파일을 읽을 수 없습니다: {path} {line_number}번째 줄",
            hint="파일을 직접 수정했다면 해당 줄을 고치거나, backups 폴더의 백업으로 복구하세요.",
        ) from error


def append_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> int:
    """파일 끝에 레코드를 덧붙인다. 기존 내용은 건드리지 않는다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    needs_newline = _lacks_trailing_newline(path)
    with path.open("a", encoding=ENCODING) as file:
        if needs_newline:
            file.write("\n")
        count = _write_records(file, records)
        file.flush()
        os.fsync(file.fileno())
    return count


def write_jsonl_atomic(path: Path, records: Iterable[dict[str, Any]]) -> int:
    """파일 전체를 새 내용으로 '원자적으로' 교체한다."""
    with atomic_open(path) as file:
        return _write_records(file, records)


@contextmanager
def atomic_open(path: Path, newline: str | None = None) -> Iterator[TextIO]:
    """같은 폴더의 임시 파일에 쓴 뒤 os.replace 로 한 번에 바꿔치기한다.

    쓰는 도중 오류가 나거나 프로그램이 죽어도 원본 파일은 이전 상태 그대로 남는다.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.parent / f".{path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp"
    try:
        with temp_path.open("x", encoding=ENCODING, newline=newline) as file:
            if path.exists():
                shutil.copymode(path, temp_path)
            yield file
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def _lacks_trailing_newline(path: Path) -> bool:
    """편집기로 고치다 마지막 줄바꿈이 빠진 파일에 덧붙이면 두 레코드가 한 줄로 붙는다."""
    if not path.exists() or path.stat().st_size == 0:
        return False
    with path.open("rb") as file:
        file.seek(-1, os.SEEK_END)
        return file.read(1) != b"\n"


def _write_records(file: TextIO, records: Iterable[dict[str, Any]]) -> int:
    count = 0
    for record in records:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")
        count += 1
    return count
