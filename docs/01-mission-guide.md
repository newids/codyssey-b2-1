# 미션 수행 가이드 — B2-1 나만의 용돈 기입장

이 문서는 미션을 처음부터 끝까지 수행하는 순서를 정리한 것입니다.
무엇을 먼저 결정하고, 어떤 순서로 만들고, 각 단계가 끝났는지 어떻게 확인하는지를 다룹니다.
완성된 코드는 `budget_app/`, 실행 결과는 [02-result-report.md](02-result-report.md),
평가 질문 답변은 [03-evaluation-answers.md](03-evaluation-answers.md)에 있습니다.

## 1. 미션을 한 문장으로

> 기능이 많은 프로그램이 아니라, **예외 상황에서도 데이터가 안전하고 구조가 설명 가능한** 콘솔 가계부를 만든다.

평가에서 보는 것은 다섯 가지입니다. 구현할 때 항상 이 다섯 가지를 "코드의 어느 줄로 설명할 것인가"를 염두에 둡니다.

| 과제 목표 | 이 프로젝트에서 보여 줄 곳 |
| --- | --- |
| 파일 기반 영구 저장 + CRUD/검색/요약/입출력 | `storage.py`, `repository.py`, `services.py`, `csv_io.py` |
| 계층(모델/저장소/서비스/CLI)의 책임 | 파일 구조 전체, README 7장 |
| 제너레이터 스트리밍의 이유와 동작 | `storage.read_jsonl`, `services.list_recent` |
| 데코레이터로 공통 관심사 분리 | `decorators.py` |
| 타입 힌트로 계약 명확화 | `models.py`, 모든 함수 시그니처 |

## 2. 요구사항 분석

### 2.1 반드시 지켜야 하는 제약

- Python 3.10 이상, **표준 라이브러리만** 사용 (`pip install` 금지 → 테스트도 `unittest`)
- 저장 포맷은 JSONL과 CSV 중 하나, 파일은 3개 이상(transactions / categories / budgets)
- 옵션은 `--` 로 통일, 모든 명령에 `--help`
- 오류는 스택트레이스 금지, "원인 + 해결 힌트" 출력, 종료 코드 0이 아님
- 모듈 3개 이상, 클래스 2개 이상, 데코레이터 1개 이상 실제 적용
- `list`, `search` 는 제너레이터 기반 스트리밍

> 과제 문서의 "7. 제약 사항"에는 옵션 표기를 `-` 로 통일하라고 적혀 있지만, "4. 기능 요구 사항"과 모든 예시는 `--` 입니다.
> 문서 변환 과정에서 하이픈 하나가 빠진 것으로 보고 `--` 로 구현했습니다.

### 2.2 스스로 정해야 하는 것

과제 문서가 "둘 중 하나를 골라 문서에 고정하라"고 한 항목들입니다. 코드를 쓰기 전에 정하고 README에 적습니다.

| 결정 항목 | 선택 | 이유 |
| --- | --- | --- |
| 저장 포맷 | JSONL | 태그처럼 목록인 값을 그대로 담을 수 있고, 한 줄이 한 레코드라 스트리밍과 덧붙이기(append)가 쉽다 |
| `update` 방식 | 옵션 기반(안 A) | 한 줄 명령으로 끝나 스크립트와 테스트에서 다루기 쉽다 |
| 빈 카테고리 파일 | 기본 카테고리 자동 생성(안 A) | 처음 실행한 사람이 바로 `add` 를 쓸 수 있다 |
| 사용 중 카테고리 삭제 | 기본은 차단, `--replace-with` 가 있으면 옮긴 뒤 삭제 | 과제가 허용한 두 방식을 모두 지원하되 기본값은 안전한 쪽 |
| 최신순의 뜻 | 날짜 내림차순 → 같은 날은 id 내림차순 | 과거 날짜를 나중에 입력해도 날짜 순서가 유지된다 |
| id 형식 | `TX-000001` 일련번호, 재사용 안 함 | 사람이 입력하기 쉽고, 삭제한 id가 다른 거래를 가리키는 사고를 막는다 |

## 3. 설계

### 3.1 계층과 의존 방향

```text
 사용자
   │  python -m budget_app <command>
   ▼
┌──────────────────────────────────────────────┐
│ CLI 계층   cli.py · commands.py · prompts.py · formatter.py │  입력 해석, 출력
└──────────────────────┬───────────────────────┘
                       ▼
┌──────────────────────────────────────────────┐
│ 서비스 계층  services.py · recurring.py · csv_io.py · backup.py │  업무 규칙
└──────────────────────┬───────────────────────┘
                       ▼
┌──────────────────────────────────────────────┐
│ 저장소 계층  repository.py · stores.py · storage.py          │  파일 입출력
└──────────────────────┬───────────────────────┘
                       ▼
┌──────────────────────────────────────────────┐
│ 모델 계층   models.py · validators.py                        │  데이터 구조, 검증
└──────────────────────────────────────────────┘
   공통: decorators.py (예외/로그/시간) · errors.py · config.py · app.py (조립)
```

화살표는 위에서 아래로만 갑니다. 서비스는 `print` 를 모르고, 저장소는 "예산 초과" 같은 규칙을 모릅니다.
이 규칙 덕분에 저장 포맷을 바꾸면 저장소 계층만, 출력 모양을 바꾸면 CLI 계층만 고치면 됩니다.

### 3.2 각 계층의 책임

| 계층 | 하는 일 | 하지 않는 일 |
| --- | --- | --- |
| 모델 | 필드 정의, 자기 검증(잘못된 값으로는 객체가 만들어지지 않음), dict 변환 | 파일 접근, 출력 |
| 저장소 | JSONL 한 줄씩 읽기, 덧붙이기, 원자적 재작성, id 발급 | 카테고리 존재 확인 같은 업무 규칙 |
| 서비스 | 카테고리 확인, 최신순 정렬, 월별 집계, 예산 비교, 삭제 정책 | `input()`, `print()`, 인자 해석 |
| CLI | 인자 해석, 대화형 입력, 문자열 검증, 표 출력, 종료 코드 | 파일 직접 접근 |

### 3.3 데이터가 안전하도록 미리 정한 규칙

1. **모델은 불변**(`@dataclass(frozen=True)`)입니다. 수정은 `dataclasses.replace` 로 새 객체를 만들고, 그때 검증이 다시 실행됩니다.
2. **수정/삭제는 원자적 교체**입니다. 임시 파일에 전체를 쓰고 `fsync` 한 뒤 `os.replace` 로 바꿉니다.
3. **검증이 먼저, 쓰기는 나중**입니다. 없는 id, 미등록 카테고리는 파일을 건드리기 전에 걸러집니다.
4. **일련번호를 먼저 저장하고 거래를 씁니다.** 중간에 멈추면 번호가 하나 건너뛸 뿐 같은 id가 두 번 나오지 않습니다.
5. **깨진 파일은 조용히 넘기지 않습니다.** 몇 번째 줄이 문제인지 알려 주고 멈춥니다.
6. **덧붙이기 전에 파일 끝을 확인합니다.** 마지막 줄바꿈이 빠진 파일에 그대로 덧붙이면 두 레코드가 한 줄로 붙습니다.

## 4. 단계별 구현 순서

아래 순서는 "아래 계층부터, 한 단계가 끝날 때마다 실행해서 확인" 원칙을 따릅니다. 각 단계의 테스트를 먼저 쓰고 구현하면 됩니다.

### 1단계 — 뼈대와 실행 경로

- `budget_app/__init__.py`, `__main__.py`, `cli.py` 를 만들고 `python -m budget_app --help` 가 나오게 합니다.
- `errors.py` 에 `BudgetAppError(message, hint)` 와 종료 코드 상수를 정의합니다.
- 확인: `python -m budget_app --help` 의 종료 코드가 0.

### 2단계 — 검증 함수와 모델

- `validators.py`: `parse_date`, `parse_month`, `parse_amount`, `parse_type`, `parse_tags`, `parse_category_name`.
  문자열을 받아 정규화된 값을 돌려주거나 `ValidationError` 를 던지는 순수 함수로 만듭니다.
- `models.py`: `Transaction`, `TransactionInput`, `Budget`, `SearchCriteria`, `MonthlySummary` 를 frozen dataclass로 정의합니다.
- 주의: `date.fromisoformat` 만으로는 부족합니다. Python 3.11부터 `20240115` 같은 형식도 받아들이므로 정규식으로 `YYYY-MM-DD` 모양을 먼저 확인합니다.
- 확인: `2024-13-40`, `2023-02-29`, 금액 `0`/`-5`/`1.5`, 타입 `gift` 가 모두 거부되는지 단위 테스트.

### 3단계 — 파일 입출력

- `storage.py`: `read_jsonl`(제너레이터), `append_jsonl`, `atomic_open`, `write_jsonl_atomic`.
- 확인: `read_jsonl(...)` 의 반환값이 제너레이터인지, 쓰는 도중 예외가 나도 원본이 그대로이고 임시 파일이 남지 않는지 테스트.

### 4단계 — 저장소

- `stores.py`: `CategoryStore`, `BudgetStore`, `SequenceStore`. 크기가 작은 파일이라 단순하게 다룹니다.
- `repository.py`: `TransactionRepository.iter_all`(제너레이터), `add_many`, `find_by_id`, `rewrite(transform)`.
  `rewrite` 하나로 수정·삭제·카테고리 일괄 변경을 모두 처리합니다.
- 확인: id가 순서대로 나오는지, 삭제 후 추가해도 id가 재사용되지 않는지.

### 5단계 — 서비스

- `services.py`: `BudgetService` 에 add / list_recent / search / update / delete / summarize / set_budget / 카테고리 관리.
- 최신순 상위 N건은 `heapq.nlargest(limit, 스트림, key=...)` 로 구합니다. 스트림을 한 번만 훑고 N건만 메모리에 둡니다.
- 확인: 임시 폴더에 거래를 넣고 정렬·집계·예외를 검증하는 통합 테스트.

### 6단계 — CLI 연결

- `cli.py`: `argparse` 하위 명령을 정의하고 `set_defaults(handler=...)` 로 처리기를 연결합니다.
  `--from` 은 Python 예약어라 `dest="date_from"` 을 줍니다. `allow_abbrev=False` 로 `--lim` 같은 줄임 옵션을 막습니다.
- `prompts.py`: 올바른 값이 올 때까지 다시 묻는 `ask(label, parse)`.
- `commands.py`: 명령마다 "문자열 검증 → 서비스 호출 → 출력 → 종료 코드" 순서의 함수 하나.
- `app.py`: 저장 폴더 초기화와 객체 조립.
- 확인: `main([...])` 을 직접 호출하는 E2E 테스트로 출력과 종료 코드를 검증.

### 7단계 — 데코레이터와 예외 처리

- `decorators.py`: `handle_errors`(예외 → 메시지 + 종료 코드), `log_call`(시작/완료/실패 로그), `timed`(소요 시간).
- `handle_errors` 는 `main` 에, `log_call`·`timed` 는 서비스와 저장소의 주요 메서드에 붙입니다.
- `argparse` 의 오류도 같은 형식으로 나오도록 `ArgumentParser.error` 를 재정의합니다.
- 확인: 저장 파일을 일부러 깨뜨린 뒤 실행해 `Traceback` 이 출력되지 않고 종료 코드가 1인지.

### 8단계 — import/export

- `csv_io.py`: 스키마 `date,type,category,amount,memo,tags` 고정. 가져올 때 2단계의 검증 함수를 그대로 재사용합니다.
- 확인: export → import 왕복, 잘못된 행 건너뛰기, 필수 컬럼 누락, 인코딩 오류.

### 9단계 — 보너스와 문서

- `backup.py`, `recurring.py`, `formatter.py` 의 표 정렬.
- README에 실행 방법, 저장 파일 위치/형식, 명령 예시, CSV 스키마, 고정한 선택 사항을 적습니다.

## 5. 핵심 개념 정리

### 5.1 제너레이터와 스트리밍

`yield` 가 있는 함수는 호출해도 바로 실행되지 않고, 값을 요청받을 때마다 다음 `yield` 까지만 진행합니다.

```python
def read_jsonl(path, decode):
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):   # 파일도 한 줄씩 읽힌다
            if not line.strip():
                continue
            yield _decode_line(path, line_number, line, decode)  # 한 건 내보내고 멈춘다
```

이 위에 조건 필터(제너레이터 식)와 `heapq.nlargest` 를 이어 붙이면, 파일 → 객체 → 필터 → 상위 N건이
한 건씩 흘러가는 파이프라인이 됩니다. 어느 단계도 전체 목록을 만들지 않습니다.

스트리밍과 "최신순 정렬"은 얼핏 충돌합니다. 정렬하려면 전부 봐야 하기 때문입니다.
`list --limit N` 은 "지금까지 본 것 중 최신 N건"만 유지하는 방식으로 해결했고,
`search` 는 조건에 맞는 것만 모아 정렬합니다(`--limit` 을 주면 마찬가지로 N건만 유지).

### 5.2 데코레이터

함수를 받아 기능을 덧붙인 새 함수를 돌려주는 함수입니다. 명령마다 `try/except` 를 반복하지 않고 한 곳에 모읍니다.

```python
@handle_errors          # main = handle_errors(main)
def main(argv=None) -> int:
    ...
```

- `functools.wraps` 를 써야 원래 함수의 이름과 문서 문자열이 유지됩니다.
- `ParamSpec` 을 쓰면 감싼 뒤에도 인자 타입 정보가 보존됩니다.
- 여러 개를 쌓으면 아래쪽부터 적용됩니다. `@log_call @timed def f` 는 `log_call(timed(f))` 입니다.

### 5.3 타입 힌트

- `-> Iterator[Transaction]` 은 "리스트가 아니라 한 번만 순회할 수 있는 흐름"이라는 계약을 시그니처로 알려 줍니다.
- `-> Transaction | None` 은 호출하는 쪽이 "없는 경우"를 처리해야 함을 드러냅니다.
- `tags: tuple[str, ...]` 는 불변 목록임을, `Callable[[Transaction], Transaction | None]` 은 `rewrite` 에 넘길 함수의 모양을 알려 줍니다.

### 5.4 원자적 파일 교체

파일을 그 자리에서 고쳐 쓰다가 프로그램이 죽으면 절반만 쓰인 파일이 남습니다.
같은 폴더에 임시 파일을 만들고 다 쓴 뒤 `os.replace` 로 이름을 바꾸면, 다른 프로그램이 보기에 파일은
"예전 내용" 아니면 "새 내용" 둘 중 하나입니다. 임시 파일을 같은 폴더에 두는 이유는 이름 바꾸기가
같은 파일 시스템 안에서만 원자적이기 때문입니다.

## 6. 자가 점검 체크리스트

제출 전에 직접 실행해 확인합니다.

- [ ] `python -m budget_app --help` 와 모든 하위 명령의 `--help` 가 동작한다
- [ ] `data` 폴더를 지우고 실행해도 파일과 기본 카테고리가 자동으로 생긴다
- [ ] `add` 에 잘못된 날짜/타입/카테고리/금액을 넣으면 이유를 알려 주고 다시 묻는다
- [ ] `add` 후 출력된 id로 `update`, `delete` 가 된다
- [ ] `list --limit 3` 이 최신순 3건을 보여 준다
- [ ] `search` 의 `--from --to --category --type --q --tag` 가 각각, 그리고 조합으로 동작한다
- [ ] `summary --month` 가 총수입/총지출/잔액/TOP N을 보여 주고, 거래 없는 달은 "데이터 없음"이다
- [ ] `budget set` 후 `summary` 에 사용률이 나오고, 초과하면 경고가 나온다
- [ ] 사용 중인 카테고리를 `category remove` 하면 막힌다
- [ ] 없는 id의 `update`/`delete` 가 "없는 데이터" 메시지와 종료 코드 1을 낸다 (`echo $?`)
- [ ] `export` 에 기간 조건이 없으면 오류가 난다
- [ ] `export` 한 파일을 `import` 할 수 있다
- [ ] 프로그램을 다시 실행해도 데이터가 남아 있다
- [ ] `transactions.jsonl` 의 한 줄을 일부러 망가뜨려도 스택트레이스가 나오지 않는다
- [ ] `python -m unittest discover -s tests -t .` 가 통과한다
- [ ] README에 실행 방법, 저장 파일 위치/형식, 명령 예시, CSV 스키마가 있다

## 7. 자주 하는 실수

| 실수 | 왜 문제인가 | 대신 할 것 |
| --- | --- | --- |
| `file.readlines()` 나 `list(...)` 로 전부 읽은 뒤 처리 | 스트리밍 요구사항 위반, 파일이 크면 메모리 부족 | `for line in file` + `yield` |
| 제너레이터를 두 번 순회 | 두 번째는 비어 있다 | 필요하면 새로 호출하거나 한 번에 처리 |
| 원본 파일을 `"w"` 로 열어 바로 다시 씀 | 도중에 죽으면 데이터 유실 | 임시 파일 + `os.replace` |
| `except Exception: pass` | 오류가 숨어 원인을 찾을 수 없다 | 원인과 힌트를 출력하고 0이 아닌 코드로 종료 |
| 오류가 나도 종료 코드 0 | 스크립트가 실패를 감지하지 못한다 | `sys.exit(main())` 으로 코드 전달 |
| 거래 수 + 1 로 id 생성 | 삭제 후 id가 겹친다 | 마지막 발급 번호를 따로 저장 |
| `-limit` 처럼 하이픈 하나 | 옵션 표기 규칙 위반 | `--limit` |
| 검증을 `add` 안에만 작성 | `update`, `import` 에서 규칙이 달라진다 | 검증 함수를 한 곳에 두고 재사용 |
| `--from` 을 `args.from` 으로 접근 | 예약어라 문법 오류 | `dest="date_from"` |
| CSV를 `line.split(",")` 로 파싱 | 메모나 태그 안의 쉼표에서 깨진다 | `csv` 모듈 사용 |
| `int(text)` 를 검증 없이 호출 | `ValueError` 가 그대로 올라와 "예기치 못한 오류"가 된다 | 정규식으로 형식과 자릿수를 먼저 확인 |
| 저장된 메모를 그대로 `print` | 줄바꿈이나 제어 문자가 표를 깨뜨린다 | 출력 직전에 제어 문자를 공백으로 치환 |
