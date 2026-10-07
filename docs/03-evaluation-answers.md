# 평가 답변서 — B2-1 나만의 용돈 기입장

과제 문서 "3. 과제 목표"의 다섯 항목에 대한 답변과, 평가에서 나올 수 있는 추가 질문의 답변입니다.
각 답변은 실제 코드 위치를 근거로 듭니다.

---

## 1부. 과제 목표 5문항

### Q1. 파일 기반 저장으로 데이터를 영구 저장하고 CRUD/검색/요약/입출력을 어떻게 구현했는가?

**저장 방식.** JSONL을 선택했습니다. 한 줄이 JSON 객체 하나이므로 한 줄씩 읽을 수 있고, 추가는 파일 끝에 한 줄을 붙이면 되며,
태그 같은 목록 값도 그대로 담깁니다. 파일은 역할별로 나눴습니다.

| 파일 | 내용 |
| --- | --- |
| `transactions.jsonl` | 거래 내역 |
| `categories.jsonl` | 카테고리 |
| `budgets.jsonl` | 월 예산 |
| `recurring.jsonl`, `meta.jsonl` | 반복 규칙, 마지막 발급 일련번호 |

**기능별 구현.**

| 기능 | 구현 방법 | 위치 |
| --- | --- | --- |
| Create (`add`, `import`) | 일련번호를 예약한 뒤 파일 끝에 덧붙임 | `repository.add_many`, `storage.append_jsonl` |
| Read (`list`, `search`) | 제너레이터로 한 줄씩 읽어 필터링, `heapq.nlargest` 로 최신 N건 선택 | `services.list_recent`, `services.search` |
| Update / Delete | 스트림을 변환하며 임시 파일에 쓰고 `os.replace` 로 교체 | `repository.rewrite`, `storage.atomic_open` |
| 요약 (`summary`) | 한 번의 순회로 수입·지출 합계와 카테고리별 지출을 누적 | `services.summarize` |
| 내보내기 | 조건에 맞는 거래를 스트리밍으로 CSV에 기록 | `csv_io.export_transactions` |
| 가져오기 | 행마다 검증해 올바른 행만 등록, 나머지는 사유와 함께 건너뜀 | `csv_io.import_transactions` |

**영구 저장의 안전장치.** 수정·삭제는 원본을 직접 고치지 않습니다. 같은 폴더의 임시 파일에 전체를 쓰고
`flush` + `fsync` 로 디스크에 내린 뒤 `os.replace` 로 한 번에 바꿉니다. 도중에 예외가 나면 임시 파일을 지우고 원본은 그대로 둡니다.
이 동작은 `tests/test_storage.py` 의 `test_failed_atomic_write_keeps_original_and_leaves_no_temp_file` 로 검증했습니다.

### Q2. 클래스/모듈 구조와 각 계층의 책임은 무엇인가?

네 계층으로 나누고 의존 방향을 CLI → 서비스 → 저장소 → 모델 한쪽으로만 두었습니다.

| 계층 | 모듈 | 주요 클래스 | 책임 |
| --- | --- | --- | --- |
| 모델 | `models.py`, `validators.py` | `Transaction`, `TransactionInput`, `Budget`, `SearchCriteria`, `MonthlySummary` | 데이터 구조와 자기 검증. 잘못된 값으로는 객체가 만들어지지 않는다 |
| 저장소 | `storage.py`, `repository.py`, `stores.py` | `TransactionRepository`, `CategoryStore`, `BudgetStore`, `SequenceStore` | 파일을 읽고 쓰는 방법. 업무 규칙은 모른다 |
| 서비스 | `services.py`, `recurring.py`, `csv_io.py`, `backup.py` | `BudgetService`, `RecurringService` | 업무 규칙(카테고리 확인, 최신순, 집계, 예산 비교, 삭제 정책). 화면과 파일 형식은 모른다 |
| CLI | `cli.py`, `commands.py`, `prompts.py`, `formatter.py` | `KoreanArgumentParser` | 인자 해석, 대화형 입력, 출력, 종료 코드 |

**이렇게 나눈 효과를 구체적으로 말하면:**

- 저장 포맷을 CSV나 SQLite로 바꾸려면 저장소 계층만 바꾸면 됩니다. 서비스는 `iter_all()`, `add_many()`, `rewrite()` 만 호출하기 때문입니다.
- 서비스가 `print` 와 `input` 을 쓰지 않으므로, 테스트에서 화면 없이 `ledger.summarize("2024-01", 3)` 의 반환값만 검증할 수 있습니다.
- 객체 조립은 `app.create_app` 한 곳에서 합니다. 서비스는 저장소를 생성자로 받으므로(의존성 주입) 테스트마다 임시 폴더의 저장소를 넣을 수 있습니다.

### Q3. `yield` 기반 제너레이터로 스트리밍 처리하는 이유와 동작 방식은?

**이유.** 거래 파일은 계속 커집니다. `readlines()` 로 전부 읽으면 메모리 사용량이 파일 크기에 비례하지만,
한 줄씩 처리하면 파일 크기와 상관없이 일정합니다. 거래 30만 건(40.4MB) 파일로 직접 측정한 결과입니다.

| 방식 | 최대 메모리 (`tracemalloc`) |
| --- | --- |
| 스트리밍 `list_recent(10)` | 약 147KB |
| 전부 리스트로 읽은 뒤 정렬 | 약 182MB |

**동작 방식.** 제너레이터 함수는 호출해도 본문이 실행되지 않고 제너레이터 객체만 돌려줍니다.
`next()` 가 호출될 때마다 다음 `yield` 까지 실행하고 값을 내보낸 뒤 그 자리에서 멈춥니다. 지역 변수와 파일 위치는 그대로 보존됩니다.

```python
# storage.py — 한 줄 읽고, 객체로 바꿔, 한 건 내보내고 멈춘다
def read_jsonl(path, decode):
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            yield _decode_line(path, line_number, line, decode)
```

`list --limit 3` 을 실행하면 아래 단계가 한 건씩 맞물려 돌아갑니다.

```text
파일 한 줄 → read_jsonl(yield) → Transaction → heapq.nlargest(3, ...) 가 최신 3건만 보관
```

**정렬과의 충돌을 어떻게 풀었는가.** 최신순으로 보여 주려면 모든 거래를 봐야 하지만, 모두 기억할 필요는 없습니다.
`heapq.nlargest(limit, 스트림, key=(날짜, id번호))` 는 스트림을 한 번 훑으면서 상위 `limit` 건만 유지합니다.
`search` 도 필터를 제너레이터 식으로 연결하고, `summary` 는 합계만 누적하며, `export` 는 읽는 즉시 CSV에 씁니다.
`update`/`delete` 도 읽으면서 임시 파일에 쓰므로 전체를 메모리에 올리지 않습니다.

**한계.** `search` 에 `--limit` 을 주지 않으면 조건에 맞는 결과를 모두 모아 정렬합니다. 메모리는 파일 전체가 아니라 "일치한 건수"에 비례합니다.

### Q4. 데코레이터로 공통 관심사를 분리한 구조와 이유는?

`decorators.py` 에 세 개를 만들어 실제로 적용했습니다.

| 데코레이터 | 하는 일 | 적용한 곳 |
| --- | --- | --- |
| `handle_errors` | 예외를 `[오류]` / `[힌트]` 메시지와 종료 코드로 변환 | `cli.main` |
| `log_call` | 함수의 시작/완료/실패를 로그로 남김 | 서비스의 `list_recent`, `search`, `summarize`, 저장소의 `rewrite`, CSV 입출력 |
| `timed` | 실행 시간을 측정해 로그로 남김 | 위와 동일 |

**이유.** 예외 처리, 로그, 시간 측정은 모든 명령에 똑같이 필요하지만 가계부 로직과는 관계가 없습니다.
명령마다 `try/except` 를 넣으면 같은 코드가 열 번 넘게 반복되고, 한 곳이라도 빠지면 스택트레이스가 노출됩니다.
데코레이터로 한 곳에 모으면 오류 출력 형식을 바꿀 때 `handle_errors` 만 고치면 되고, 업무 함수에는 업무 코드만 남습니다.

**구조.**

```python
def handle_errors(func: Callable[P, int]) -> Callable[P, int]:
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> int:
        try:
            return func(*args, **kwargs)
        except BudgetAppError as error:           # 예상한 오류: 원인 + 힌트
            print(format_error(error.message, error.hint), file=sys.stderr)
            return error.exit_code
        except KeyboardInterrupt: ...             # Ctrl+C → 130
        except OSError as error: ...              # 권한, 경로 문제 → 1
        except Exception as error: ...            # 그 밖의 모든 오류 → 3, 스택트레이스 없음
    return wrapper
```

- `functools.wraps` 로 원래 함수의 이름과 문서 문자열을 보존합니다. 로그에 `BudgetService.search` 처럼 정확한 이름이 찍힙니다.
- `ParamSpec` 과 `TypeVar` 로 감싼 뒤에도 원래 함수의 인자·반환 타입이 유지됩니다.
- `@log_call @timed` 처럼 쌓으면 아래부터 적용되어 `log_call(timed(func))` 가 됩니다.
- 로그는 평소에는 보이지 않고 `--verbose` 를 줄 때만 표준 오류로 출력됩니다.

```console
$ python -m budget_app search --tag meal --verbose
[log] 시작: BudgetService.search
[log] 소요 시간: BudgetService.search 0.10ms
[log] 완료: BudgetService.search
```

### Q5. 타입 힌트로 입출력 계약을 명확히 했을 때의 이점은? (실제 코드 예)

**예 1 — 반환 타입이 사용법을 알려 준다.**

```python
def iter_all(self) -> Iterator[Transaction]: ...          # 한 번만 순회할 수 있는 흐름
def list_recent(self, limit: int) -> list[Transaction]: ...  # 여러 번 써도 되는 목록
def find_by_id(self, tx_id: str) -> Transaction | None: ...  # 없을 수 있음
```

`Iterator` 와 `list` 의 차이만 봐도 "이 값에 `len()` 을 쓰면 안 된다"는 것을 알 수 있습니다.
`| None` 은 호출하는 쪽이 없는 경우를 처리하도록 요구합니다. 실제로 `_require_transaction` 이 `None` 을 `NotFoundError` 로 바꿉니다.

**예 2 — 함수를 인자로 받을 때 모양을 고정한다.**

```python
Transform = Callable[[Transaction], "Transaction | None"]

def rewrite(self, transform: Transform) -> int: ...
```

"거래 하나를 받아, 바꾼 거래를 돌려주거나 삭제하려면 `None` 을 돌려준다"는 약속이 시그니처에 적혀 있습니다.
수정은 `lambda tx: updated if tx.id == tx_id else tx`, 삭제는 `lambda tx: None if tx.id == tx_id else tx` 로 같은 함수를 재사용합니다.

**예 3 — 데이터 구조의 계약.**

```python
@dataclass(frozen=True)
class Transaction:
    id: str
    type: str
    date: str
    amount: int
    category: str
    memo: str = ""
    tags: tuple[str, ...] = ()
```

`amount: int` 로 "금액은 정수"를, `tags: tuple[str, ...]` 로 "변경할 수 없는 문자열 목록"을 드러냅니다.
`ask(label: str, parse: Callable[[str], T]) -> T` 는 제네릭이어서, `parse_amount` 를 넘기면 결과가 `int` 로,
`parse_tags` 를 넘기면 `tuple[str, ...]` 로 추론됩니다.

**이점 정리.** 함수를 열어 보지 않고도 무엇을 넣고 무엇이 나오는지 알 수 있고, 편집기 자동 완성과 타입 검사기(mypy, pyright)가
실행 전에 실수를 잡아 주며, 계층 사이의 경계가 문서 없이도 유지됩니다.
다만 타입 힌트는 실행 중에 검사되지 않으므로, 외부에서 들어오는 값(사용자 입력, 파일 내용)은 `validators.py` 와 모델의 `__post_init__` 으로 따로 검증합니다.

---

## 2부. 예상 추가 질문

### Q6. JSONL과 CSV 중 왜 JSONL인가?

| 기준 | JSONL | CSV |
| --- | --- | --- |
| 목록 값(tags) | 배열로 그대로 저장 | 구분자 약속이 따로 필요 |
| 타입 | 숫자와 문자열이 구분됨 | 전부 문자열 |
| 메모에 쉼표·따옴표 | 문제없음 | 인용 규칙 필요 |
| 스트리밍, 덧붙이기 | 한 줄 = 한 레코드 | 가능 |
| 사람이 엑셀로 열기 | 불편 | 편함 |

내부 저장은 구조가 분명한 JSONL로 하고, 사람과 주고받는 용도는 `import`/`export` 의 CSV로 분리했습니다.

### Q7. update/delete 도중 프로그램이 죽으면 데이터는 어떻게 되는가?

원본은 손상되지 않습니다. 새 내용은 임시 파일에만 쓰이고, 마지막 `os.replace` 가 성공해야 원본이 바뀝니다.
`os.replace` 이전에 죽으면 원본이 그대로이고(임시 파일 `.transactions.jsonl.*.tmp` 만 남을 수 있음), 이후에 죽으면 새 내용이 온전히 있습니다.
임시 파일을 원본과 같은 폴더에 만드는 것은 이름 바꾸기가 같은 파일 시스템 안에서만 원자적이기 때문입니다.

### Q8. id는 어떻게 만들고, 왜 "거래 수 + 1" 이 아닌가?

`meta.jsonl` 에 마지막으로 발급한 번호를 저장하고 1씩 올립니다. "거래 수 + 1" 방식은 삭제 후 번호가 겹칩니다.
예를 들어 3건 중 2번을 지우면 다음 id가 또 `TX-000003` 이 됩니다.
번호는 거래를 쓰기 **전에** 저장합니다. 그 사이에 멈추면 번호 하나를 건너뛸 뿐이고, 반대 순서였다면 같은 id가 두 번 발급될 수 있습니다.
`meta.jsonl` 이 없어진 경우에는 거래 파일을 훑어 가장 큰 번호에서 이어 갑니다.

### Q9. 입력 검증은 어디에서 하는가? 중복되지 않는가?

두 단계입니다.

1. **경계에서 문자열 검증** — `validators.py` 의 함수들이 문자열을 받아 정규화하거나 `ValidationError(원인, 힌트)` 를 던집니다.
   대화형 입력, 옵션 인자, CSV 가져오기가 모두 같은 함수를 씁니다.
2. **모델의 자기 검증** — `Transaction.__post_init__` 이 타입·날짜·금액을 다시 확인합니다.
   저장 파일을 사람이 직접 고쳐 값이 잘못된 경우도 여기서 걸립니다.

카테고리가 등록되어 있는지는 파일을 봐야 알 수 있으므로 서비스(`require_category`)가 확인합니다.
검증 규칙 자체는 `validators.py` 한 곳에만 있어 중복되지 않습니다.

### Q10. 오류 메시지와 종료 코드는 어떻게 설계했는가?

모든 의도된 오류는 `BudgetAppError(message, hint)` 의 하위 클래스입니다(`ValidationError`, `NotFoundError`, `DataFileError`, `InputCancelledError`).
`handle_errors` 가 이를 `[오류] 원인` / `[힌트] 해결 방법` 두 줄로 출력하고 종료 코드를 돌려줍니다.
깨진 저장 파일(잘못된 JSON, UTF-8이 아닌 내용, 타입이 틀린 값)도 `DataFileError` 로 분류해 몇 번째 줄인지 알려 줍니다.
`argparse` 가 내는 형식 오류도 `KoreanArgumentParser.error` 에서 같은 형식으로 바꿉니다.
종료 코드는 0(정상), 1(입력·데이터 오류), 2(명령 형식 오류), 3(예기치 못한 오류), 130(Ctrl+C)입니다.
오류는 표준 오류로, 결과는 표준 출력으로 나가므로 `list > out.txt` 처럼 결과만 받을 수 있습니다.

### Q11. 왜 모델을 불변(frozen)으로 만들었는가?

거래 객체가 여러 계층을 지나는 동안 어디선가 값이 바뀌는 일을 원천적으로 막기 위해서입니다.
수정은 `dataclasses.replace(current, **changes)` 로 새 객체를 만들고, 이때 `__post_init__` 검증이 다시 실행되므로
`update --amount -1` 같은 잘못된 수정은 파일을 건드리기 전에 거부됩니다.

### Q12. 사용 중인 카테고리 삭제는 어떻게 처리하는가?

거래 파일을 스트리밍으로 훑어 사용 건수를 셉니다. 한 건이라도 있으면 삭제를 막고, 몇 건이 쓰고 있는지와
`--replace-with` 사용법을 힌트로 알려 줍니다. `--replace-with <카테고리>` 를 주면 해당 거래의 카테고리를 먼저 옮기고
그다음에 카테고리를 지웁니다. 이 순서라서 도중에 멈춰도 "없는 카테고리를 가리키는 거래"는 생기지 않습니다.
반복 규칙이 그 카테고리를 쓰는 경우에도 같은 규칙을 적용해, 대체 카테고리가 없으면 막고 있으면 규칙도 함께 옮깁니다(`RecurringService.remove_category`).

### Q13. 테스트는 어떻게 했는가?

외부 라이브러리를 쓸 수 없으므로 `unittest` 로 작성했습니다(91개, Python 3.13과 3.10에서 통과).

| 종류 | 대상 | 파일 |
| --- | --- | --- |
| 단위 | 검증 함수, 모델, 데코레이터, 표 정렬 | `test_validators_models.py`, `test_cli.py` |
| 통합 | 저장소·서비스·CSV를 임시 폴더의 실제 파일로 검증 | `test_storage.py`, `test_services.py` |
| E2E | `main([...])` 과 `python -m budget_app` 실행으로 출력과 종료 코드 검증 | `test_cli.py` |

테스트마다 `tempfile.TemporaryDirectory` 로 독립된 데이터 폴더를 쓰고, `input()` 은 `unittest.mock.patch` 로 대체합니다.
표준 라이브러리의 `trace` 모듈로 측정한 줄 실행률은 전체 약 99%입니다(18개 모듈 중 15개가 100%, 최저는 `prompts.py` 80%).
구현 뒤에는 독립적인 코드 리뷰를 받아 재현된 문제를 고치고 회귀 테스트를 추가했습니다([02-result-report.md](02-result-report.md) 7장).

### Q14. 이 구현의 한계와 개선 방향은?

- **동시 실행을 고려하지 않았습니다.** 여러 프로세스가 동시에 `add` 하면 같은 id가 발급될 수 있고, 수정 중에 덧붙인 거래가 사라질 수 있습니다. 개선하려면 쓰기 명령을 파일 잠금으로 감싸야 합니다.
- **반복 내역의 중복 방지는 태그에 의존합니다.** 생성된 거래의 `recurring:RC-0001` 태그를 사용자가 지우면 같은 달에 다시 생성됩니다. 규칙 id와 적용 월을 별도 파일에 기록하면 해결됩니다.
- **수정·삭제는 파일 전체를 다시 씁니다.** 한 건을 고쳐도 시간이 파일 크기에 비례합니다. 데이터가 매우 커지면 SQLite 같은 저장소가 맞습니다. 저장소 계층만 교체하면 됩니다.
- **조회는 항상 파일 전체를 훑습니다.** 인덱스가 없어 30만 건에서 `list` 가 수 초 걸립니다. 메모리는 일정하지만 시간은 선형입니다.
- **`import` 는 올바른 행을 모아 한 번에 덧붙입니다.** 가져올 CSV 자체는 메모리에 올라가고, 덧붙이는 도중 중단되면 일부만 들어갈 수 있습니다.
- **금액은 원 단위 정수만** 지원합니다. 소수 단위 통화는 다루지 않습니다.

### Q15. 보너스 과제는 무엇을 구현했는가?

| 보너스 | 구현 |
| --- | --- |
| 백업 | `backup` → `data/backups/<YYYYMMDD-HHMMSS>/` 에 모든 데이터 파일 복사 |
| 반복 내역 | `recurring add/list/remove/apply`. 생성한 거래에 `recurring:RC-0001` 태그를 붙여, 같은 달에 다시 실행해도 중복 생성하지 않음. 31일 규칙은 말일로 조정 |
| 표 정렬 | `formatter.py`. `unicodedata.east_asian_width` 로 한글을 2칸으로 계산해 열을 맞춤 |
| 저장 원자성 | 임시 파일 + `fsync` + `os.replace` (Q7) |
