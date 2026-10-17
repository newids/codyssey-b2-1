# 나만의 용돈 기입장 (budget_app)

Python 표준 라이브러리만으로 만든 파일 기반 콘솔 가계부입니다.
거래 추가·조회·검색·수정·삭제, 월별 요약, 예산 초과 경고, 카테고리 관리, CSV 가져오기/내보내기를 지원하고,
데이터는 JSONL 파일로 영구 저장합니다.

| 문서 | 내용 |
| --- | --- |
| [docs/01-mission-guide.md](docs/01-mission-guide.md) | 미션 수행 가이드 (요구사항 분석, 단계별 구현 순서, 핵심 개념) |
| [docs/02-result-report.md](docs/02-result-report.md) | 수행 결과 보고서 (요구사항 충족표, 실행 화면, 테스트 결과) |
| [docs/03-evaluation-answers.md](docs/03-evaluation-answers.md) | 평가 답변서 (과제 목표 5문항 + 예상 질문) |
| [docs/04-evaluation-checklist.md](docs/04-evaluation-checklist.md) | 평가항목 체크리스트별 답변과 근거 위치 |

## 1. 실행 방법

- 요구 환경: Python 3.10 이상. 설치할 패키지는 없습니다.
- 프로젝트 루트(이 README가 있는 폴더)에서 실행합니다.

```bash
python -m budget_app <command> [options]
python -m budget_app --help            # 전체 명령 목록
python -m budget_app summary --help    # 명령별 사용법
```

처음 실행하면 `./data` 폴더와 저장 파일이 자동으로 만들어지고 기본 카테고리
(`food, transport, rent, salary, shopping, etc`)가 등록됩니다.

공통 옵션은 명령 앞뒤 어디에나 쓸 수 있습니다.

| 옵션 | 설명 |
| --- | --- |
| `--data-dir <폴더>` | 저장 폴더 변경 (기본값 `./data`) |
| `--verbose` | 실행 로그와 소요 시간 출력 |
| `--help` | 사용법 출력 |

## 2. 명령 요약

| 명령 | 입력 방식 | 설명 |
| --- | --- | --- |
| `add` | 대화형 | 거래 추가, 생성된 id 출력 |
| `list [--limit N]` | 옵션 | 최신순 목록 (기본 10건) |
| `search [--from] [--to] [--category] [--type] [--q] [--tag] [--min-amount] [--max-amount] [--limit]` | 옵션 | 조건 검색, 최신순. 금액 범위는 양 끝 포함 |
| `summary --month YYYY-MM [--top N]` | 옵션 | 총수입/총지출/잔액, 예산 사용률, 지출 TOP N (기본 3) |
| `budget set --month YYYY-MM --amount 금액` | 옵션 | 월 예산 저장 (`budget show --month`, `budget list` 로 조회) |
| `category add [--name]` / `list` / `remove [--name] [--replace-with]` | 대화형 또는 옵션 | 카테고리 관리 |
| `update --id ID [--date] [--type] [--category] [--amount] [--memo] [--tags]` | **옵션 방식으로 고정** | 지정한 항목만 수정 |
| `delete --id ID` | 옵션 | 거래 삭제 |
| `import --from CSV [--strict]` | 옵션 | CSV 일괄 등록 (`--strict`: 잘못된 행이 있으면 전부 취소) |
| `export --out CSV (--month YYYY-MM \| --from/--to)` | 옵션 | 조건에 맞는 거래를 CSV로 저장 |
| `backup` | - | 데이터 파일을 타임스탬프 폴더로 백업 (보너스) |
| `recurring add/list/remove/apply` | 옵션 | 반복 내역 등록과 월별 자동 생성 (보너스) |

### 이 프로젝트에서 고정한 선택 사항

| 항목 | 선택 |
| --- | --- |
| 저장 포맷 | JSONL |
| `update` 방식 | 옵션 기반(안 A). 준 옵션만 바뀌고, `--memo ""` / `--tags ""` 는 값을 비웁니다. |
| 카테고리 파일이 비어 있을 때 | 기본 카테고리 자동 생성(안 A) |
| 사용 중인 카테고리 삭제 | 기본은 삭제를 막고, `--replace-with` 로 대체 카테고리를 주면 거래와 반복 규칙을 옮긴 뒤 삭제 |
| 최신순 기준 | 날짜 내림차순, 같은 날짜면 나중에 등록한 id 먼저 |
| 금액 | 양의 정수(원 단위, 최대 15자리). `15,000` 처럼 천 단위 쉼표는 허용 |

## 3. 주요 명령 예시

```console
$ python -m budget_app add
날짜(YYYY-MM-DD): 2024-01-15
타입(income/expense): expense
카테고리: food
금액(양수): 15000
메모(선택): 점심
태그(쉼표로 구분, 없으면 엔터): meal
[저장 완료] id=TX-000012

$ python -m budget_app list --limit 3
ID        | 날짜       | 타입    | 카테고리  |    금액 | 메모 | 태그
----------+------------+---------+-----------+---------+------+-----
TX-000012 | 2024-01-15 | expense | food      |   15000 | 점심 | meal
TX-000011 | 2024-01-14 | income  | salary    | 3000000 |      |
TX-000010 | 2024-01-12 | expense | transport |   20000 |      |

$ python -m budget_app search --from 2024-01-01 --to 2024-01-31 --category food --tag meal
$ python -m budget_app search --type expense --q 점심 --limit 5
$ python -m budget_app search --type expense --min-amount 50000      # 5만원 이상 지출만

$ python -m budget_app budget set --month 2024-01 --amount 500000
[저장 완료] 2024-01 예산 500000원

$ python -m budget_app summary --month 2024-01 --top 3
[2024-01 요약] 거래 12건
총 수입: 3000000원
총 지출: 215000원
잔액: 2785000원
예산: 500000원 (사용률 43.0%)
지출 TOP 3
1) rent      150000원
2) food       45000원
3) transport  20000원

$ python -m budget_app category add
카테고리명: hobby
[저장 완료] category=hobby
$ python -m budget_app category list
$ python -m budget_app category remove --name hobby --replace-with etc

$ python -m budget_app update --id TX-000012 --amount 18000 --memo "점심(수정)"
$ python -m budget_app delete --id TX-000012

$ python -m budget_app export --out export.csv --month 2024-01
[완료] export.csv (12 records)
$ python -m budget_app export --out q1.csv --from 2024-01-01 --to 2024-03-31
$ python -m budget_app import --from samples/import_sample.csv
[완료] imported=7, skipped=0
$ python -m budget_app import --from bank.csv --strict   # 잘못된 행이 있으면 전부 취소

$ python -m budget_app backup
$ python -m budget_app recurring add --day 25 --type income --category salary --amount 3000000 --memo 월급
$ python -m budget_app recurring apply --month 2024-02
```

예산 사용률이 80% 이상이면 `[주의]`, 예산을 넘으면 `[경고] 예산을 N원 초과했습니다!` 가 함께 출력됩니다.
거래가 없는 달은 `[YYYY-MM] 데이터 없음` 을 출력합니다.

`[주의]` 기준(80%)은 `budget_app/config.py` 의 `BUDGET_WARNING_RATE` 상수로 바꿉니다. 한 사람이 쓰는 프로그램이라 별도 설정 파일이나 옵션으로는 두지 않았습니다.

## 4. 저장 파일 위치와 형식

기본 위치는 `./data` 이며 `--data-dir` 로 바꿀 수 있습니다. 모든 파일은 UTF-8 JSONL(한 줄에 JSON 객체 하나)입니다.

| 파일 | 내용 | 한 줄 예시 |
| --- | --- | --- |
| `transactions.jsonl` | 거래 내역 | `{"id": "TX-000001", "type": "expense", "date": "2024-01-15", "amount": 15000, "category": "food", "memo": "점심", "tags": ["meal"]}` |
| `categories.jsonl` | 카테고리 | `{"name": "food"}` |
| `budgets.jsonl` | 월 예산 | `{"month": "2024-01", "amount": 500000}` |
| `recurring.jsonl` | 반복 규칙 | `{"id": "RC-0001", "day": 25, "type": "income", "amount": 3000000, "category": "salary", "memo": "월급"}` |
| `meta.jsonl` | 마지막으로 발급한 일련번호 | `{"key": "transaction", "value": 12}` |
| `backups/<YYYYMMDD-HHMMSS>/` | `backup` 명령이 만든 복사본 | 위 파일들과 동일 |

- 거래 id는 `TX-000001` 형식의 일련번호입니다. 삭제한 id는 다시 쓰지 않습니다.
- 수정·삭제는 같은 폴더의 임시 파일에 전체를 다시 쓴 뒤 `os.replace` 로 교체합니다. 중간에 실패해도 원본은 그대로 남습니다.
- 거래 파일은 한 줄씩 읽는 제너레이터로만 다루므로, 파일이 커져도 메모리 사용량이 늘지 않습니다.
- 다시 쓴 파일은 원본의 권한(모드)을 그대로 이어받고, 임시 파일은 원본과 같은 폴더에 만듭니다. 데이터 폴더에 읽기·쓰기 권한만 있으면 되고, 다른 폴더나 시스템 임시 폴더는 쓰지 않습니다.

### 백업과 복구

`backup` 은 5개 파일을 `data/backups/<시각>/` 에 복사합니다. 복구는 그 폴더의 파일을 데이터 폴더로 다시 복사하면 됩니다.

```console
$ python -m budget_app backup
[백업 완료] data/backups/20261017-152144 (5 files)

$ cp data/backups/20261017-152144/*.jsonl data/      # 복구: 백업 시점으로 되돌리기
$ python -m budget_app list --limit 3                 # 되돌아왔는지 확인
```

- 5개 파일을 **함께** 되돌리세요. `transactions.jsonl` 만 되돌리면 `meta.jsonl` 의 일련번호와 어긋나지는 않지만(번호는 건너뛸 뿐), 예산·카테고리는 복구 전 상태로 남습니다.
- 복구는 프로그램이 실행 중이 아닐 때 합니다. 저장 파일이 깨져 `저장 파일을 읽을 수 없습니다: ... N번째 줄` 오류가 날 때도 같은 방법으로 되돌립니다.

## 5. import/export CSV 스키마

UTF-8, 첫 줄은 헤더입니다. 엑셀이 붙이는 BOM이 있어도 읽습니다.

| column | required | 설명 |
| --- | --- | --- |
| `date` | Y | `YYYY-MM-DD` |
| `type` | Y | `income` / `expense` |
| `category` | Y | 등록된 카테고리 |
| `amount` | Y | 양수 정수 |
| `memo` | N | 문자열 |
| `tags` | N | 쉼표(,) 구분 문자열. 여러 개면 `"meal,friends"` 처럼 따옴표로 감쌉니다. |

```csv
date,type,category,amount,memo,tags
2024-01-15,expense,food,15000,점심,meal
2024-01-20,expense,food,18000,"저녁, 친구와","meal,friends"
```

- `import` 는 기본적으로 **부분 성공** 방식입니다. 올바른 행만 등록하고, 잘못된 행은 행 번호와 사유를 출력하며 건너뜁니다(`skipped`).
- `import --strict` 는 **롤백** 방식입니다. 잘못된 행이 하나라도 있으면 아무것도 등록하지 않고 사유를 알려 줍니다. 어느 방식이든 모든 행을 검증한 뒤에 파일에 쓰므로 절반만 들어가는 일은 없습니다.
- 필수 컬럼이 헤더에 없으면 아무것도 등록하지 않고 오류로 끝납니다.
- `export` 는 `--month` 또는 `--from`/`--to` 중 한 가지 방식의 기간 조건이 반드시 필요합니다. 같은 경로의 파일이 있으면 덮어씁니다.
- `export` 결과를 그대로 `import` 할 수 있습니다(id는 새로 발급됩니다).

## 6. 오류 처리와 종료 코드

오류는 스택트레이스 없이 원인과 해결 힌트로 출력합니다(표준 오류).

```console
$ python -m budget_app delete --id TX-999999
[오류] 없는 데이터입니다: id=TX-999999
[힌트] list 또는 search 명령으로 id 를 확인하세요. (예: TX-000012)
```

| 코드 | 의미 |
| --- | --- |
| 0 | 정상 종료 |
| 1 | 입력값 오류, 없는 데이터, 파일 오류 |
| 2 | 명령/옵션 형식 오류 |
| 3 | 예기치 못한 내부 오류 |
| 130 | 사용자가 Ctrl+C 로 중단 |

셸에서 종료 코드는 `$?` 로 확인합니다. 스크립트에서는 `&&` / `||` 로 성공·실패를 분기할 수 있습니다.

```console
$ python -m budget_app delete --id TX-999999; echo "exit=$?"
[오류] 없는 데이터입니다: id=TX-999999
[힌트] list 또는 search 명령으로 id 를 확인하세요. (예: TX-000012)
exit=1
$ python -m budget_app import --from bank.csv --strict && echo "등록 완료" || echo "실패(코드 $?)"
```

대화형 입력(`add` 등)에서 잘못된 값을 넣으면 이유를 알려 주고 그 항목만 다시 묻습니다.

`-` 로 시작하는 값은 옵션으로 오해받으므로 `--memo=-10%할인` 처럼 `=` 로 붙여 씁니다.

### 자주 보는 오류와 해결

| 메시지 | 원인 | 해결 |
| --- | --- | --- |
| `등록되지 않은 카테고리입니다: cafe` | 카테고리를 만들기 전에 사용 | `category add --name cafe` 뒤에 다시 실행 |
| `없는 데이터입니다: id=TX-...` | 오타, 또는 이미 삭제한 id | `list` / `search` 로 id 확인 |
| `'food' 카테고리를 사용하는 거래가 N건 있어 삭제할 수 없습니다.` | 사용 중인 카테고리 삭제 | `--replace-with <다른 카테고리>` 를 붙여 옮긴 뒤 삭제 |
| `저장 파일을 읽을 수 없습니다: ... N번째 줄` | 손으로 고치다 JSON 한 줄이 깨짐 | 그 줄을 고치거나 `backups/` 의 복사본으로 복구 |
| `파일을 처리할 수 없습니다: Permission denied (...)` | 데이터 폴더에 쓰기 권한 없음 | 폴더 권한 수정, 또는 `--data-dir` 로 다른 폴더 지정 |
| `파일을 처리할 수 없습니다: No space left on device` | 디스크 가득 참 | 공간 확보 후 재실행. 덧붙이던 도중이었다면 그때까지의 행만 저장되고 id 는 겹치지 않음 |
| `가져올 파일을 찾을 수 없습니다` / `CSV 헤더에 필수 컬럼이 없습니다` | 경로 오타, 헤더 누락 | 경로 확인, 첫 줄을 `date,type,category,amount,memo,tags` 로 |
| `같은 시각의 백업이 이미 있습니다` | 1초 안에 `backup` 을 두 번 실행 | 1초 뒤 재실행 |
| `명령 형식이 올바르지 않습니다` (코드 2) | 옵션 이름 오타, 필수 옵션 누락 | `<command> --help` |
| `예기치 못한 오류가 발생했습니다: ...` (코드 3) | 위 어디에도 속하지 않는 내부 오류 | `backup` 으로 보존 → `--verbose` 로 다시 실행해 어느 단계에서 멈추는지 확인 → 저장 파일 점검 |

### 실행 로그 (`--verbose`)

`--verbose` 를 붙이면 서비스·저장소의 주요 메서드가 시작/완료/실패 로그와 소요 시간을 표준 오류에 출력합니다. 결과(표준 출력)와 섞이지 않습니다.

```console
$ python -m budget_app search --tag meal --verbose
[log] 시작: BudgetService.search
[log] 소요 시간: BudgetService.search 0.10ms
[log] 완료: BudgetService.search
ID        | 날짜       | 타입    | 카테고리 |  금액 | 메모 | 태그
...
```

`시작/완료/실패` 는 `log_call`, `소요 시간` 은 `timed` 데코레이터가 남깁니다. 로그 수준은 `--verbose` 가 없으면 WARNING, 있으면 DEBUG 입니다(`cli._configure_logging`).

## 6.1 알아 둘 제한

- 한 번에 한 프로세스만 쓰는 것을 전제로 합니다. 같은 데이터 폴더에 여러 프로세스가 동시에 쓰면 id가 겹칠 수 있습니다.
- 같은 CSV를 두 번 `import` 하면 중복 검사 없이 두 번 등록됩니다. 다음 단계로 `--skip-duplicates`(날짜·타입·카테고리·금액·메모가 같은 거래가 이미 있으면 건너뜀) 옵션을 계획하고 있습니다. 설계는 [docs/03-evaluation-answers.md Q16](docs/03-evaluation-answers.md) 참고.
- `search` 에 `--limit` 이 없으면 일치한 결과를 모두 모아 정렬합니다. 결과가 1,000건을 넘으면 `--limit` 사용을 권하는 안내를 표준 오류에 출력합니다.
- `recurring apply` 는 생성한 거래의 `recurring:<규칙 id>` 태그로 중복을 막습니다. 이 태그를 지우면 같은 달에 다시 생성됩니다.

## 7. 구조

```text
budget_app/
  __main__.py     진입점 (python -m budget_app)
  cli.py          인자 해석, 명령 분기                     ┐ CLI 계층
  commands.py     명령별 처리기 (검증 → 서비스 호출 → 출력) │
  prompts.py      대화형 입력(재입력 루프)                  │
  formatter.py    표 정렬, 요약 출력                        ┘
  services.py     BudgetService: 업무 규칙                  ┐ 서비스 계층
  recurring.py    RecurringService: 반복 내역               │
  csv_io.py       CSV 가져오기/내보내기                     │
  backup.py       백업                                      ┘
  repository.py   TransactionRepository (스트리밍)          ┐ 저장소 계층
  stores.py       Category/Budget/Recurring/Sequence 저장소 │
  storage.py      JSONL 스트리밍 읽기, 원자적 쓰기          ┘
  models.py       Transaction 등 불변 dataclass             ┐ 모델 계층
  validators.py   입력 검증 함수                            ┘
  decorators.py   handle_errors / log_call / timed (공통 관심사)
  errors.py       예외 계층, 종료 코드
  config.py       기본값, 파일 경로
  app.py          객체 조립, 저장 폴더 초기화
tests/            unittest 기반 단위·통합·E2E 테스트
samples/          import 용 예시 CSV
```

의존 방향은 CLI → 서비스 → 저장소 → 모델 한쪽으로만 흐릅니다.

```text
cli.py → commands.py → services.py / recurring.py / csv_io.py / backup.py → repository.py / stores.py → storage.py
          (prompts.py, formatter.py 는 commands.py 만 사용)          (models.py, validators.py 는 모든 계층이 사용)
```

## 8. 테스트

```bash
python -m unittest discover -s tests -t .
```

표준 라이브러리 제약에 맞춰 `unittest` 를 사용합니다. 테스트는 매번 임시 폴더를 쓰므로 `./data` 를 건드리지 않습니다.

타입 힌트는 `mypy --strict` 로 검사합니다. 실행에는 필요 없으므로 개발용으로만 설치합니다.

```bash
pip install mypy              # 개발 환경에만
mypy --strict budget_app      # Success: no issues found in 19 source files
```
