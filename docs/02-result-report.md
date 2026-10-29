# 수행 결과 보고서 — B2-1 나만의 용돈 기입장

과제 요구사항이 어디에 구현되어 있고 어떻게 확인했는지를 정리한 문서입니다.
아래 실행 화면은 모두 이 저장소의 코드를 빈 폴더에서 실제로 실행한 출력입니다(2026-10-02, macOS, Python 3.13.5).

## 1. 결과 요약

| 항목 | 결과 |
| --- | --- |
| 필수 기능 10종 | 모두 구현 |
| 보너스 4종 (백업, 반복 내역, 표 정렬, 저장 원자성) | 모두 구현 |
| 외부 라이브러리 | 사용하지 않음 (표준 라이브러리만) |
| 자동 테스트 | 110개 통과 (Python 3.13.5, 3.10.12 양쪽) |
| 줄 실행률 | 전체 약 99% (표준 라이브러리 `trace` 로 측정, 모듈별 최저 80%) |
| 코드 규모 | 앱 19개 파일 약 2,210줄, 테스트 약 1,380줄 |
| 타입 검사 | `mypy --strict budget_app` 오류 0건 (mypy 2.4.0) |
| 고정한 선택 | JSONL / `update` 옵션 방식 / 기본 카테고리 자동 생성 |

## 2. 요구사항 충족표

### 2.1 최종 결과물 10항목

| # | 요구사항 | 구현 위치 | 검증 테스트 |
| --- | --- | --- | --- |
| 1 | `add`: 대화형 입력, 저장 메시지 + id | `commands.cmd_add`, `prompts.ask` | `test_add_prints_generated_id_and_persists`, `test_add_reprompts_until_each_field_is_valid` |
| 2 | `list`: `--limit`, 최신순, 스트리밍 | `commands.cmd_list`, `services.list_recent` | `test_list_shows_newest_first_with_limit`, `test_read_is_a_lazy_generator` |
| 3 | `search`: `--from/--to/--category/--type/--q/--tag` | `commands.cmd_search`, `models.SearchCriteria` | `test_search_by_options`, `test_criteria_filters_every_condition` |
| 4 | `summary`: 총수입/총지출/잔액 + TOP N | `services.summarize`, `formatter.format_summary` | `test_summary_totals_and_top_categories`, `test_summary_without_data_says_so` |
| 5 | `budget set` + 사용률/초과 경고 | `commands.cmd_budget_set`, `stores.BudgetStore` | `test_budget_and_summary_with_warning`, `test_budget_is_persisted_and_reflected_in_summary` |
| 6 | `category add/list/remove` (사용 중 처리) | `services.add_category`, `recurring.remove_category` | `test_category_commands`, `test_category_in_use_cannot_be_removed_without_replacement` |
| 7 | `update --id` (옵션 방식 고정) | `commands.cmd_update`, `services.update_transaction` | `test_update_and_delete_by_id`, `test_update_failures_leave_data_untouched` |
| 8 | `delete --id`, 없는 id 처리 | `services.delete_transaction` | `test_delete_removes_one_and_unknown_id_is_not_found` |
| 9 | `import --from`, `export --out` + 건수 출력 | `csv_io.py` | `test_export_then_import_round_trips`, `test_import_skips_invalid_rows_with_reasons`, `test_strict_import_registers_nothing_when_any_row_is_invalid`, `test_skip_duplicates_ignores_rows_already_stored_and_repeated_in_file` |
| 10 | 3개 이상 파일로 영구 저장, README | `config.DataPaths`, `README.md` | `test_first_run_creates_files_and_default_categories` |

### 2.2 기능 요구사항 세부

| 요구사항 | 충족 방법 |
| --- | --- |
| `python -m budget_app <command>` 실행 | `budget_app/__main__.py` |
| 모든 명령에 `--help` | `argparse` 하위 명령. 16개 명령 조합을 `test_every_command_supports_help` 로 확인 |
| 옵션은 `--` 로 통일 | 모든 옵션이 `--이름` 형식. `allow_abbrev=False` 로 줄임 옵션 차단 |
| 데이터 모델 필드 (id, type, date, amount, category, memo, tags) | `models.Transaction` (frozen dataclass) |
| 클래스 2개 이상 | `Transaction`, `TransactionRepository`, `CategoryStore`, `BudgetStore`, `BudgetService` 등 |
| 입력 검증 (날짜, 금액, type, category) | `validators.py`. 대화형은 재입력, 옵션은 오류 메시지 |
| 저장 포맷 1개 선택, 3개 이상 파일 | JSONL 5개 파일 |
| `--data-dir` 로 저장 폴더 변경 | `cli.build_parser`. 명령 앞뒤 모두 가능 |
| 파일이 없을 때 자동 생성, 기본 카테고리(안 A) | `app._initialize_storage` |
| `list` 기본 limit | 10 (`config.DEFAULT_LIST_LIMIT`) |
| update/delete 안정성 | 임시 파일 + `fsync` + `os.replace` (`storage.atomic_open`) |
| 데이터 없는 달 | `[YYYY-MM] 데이터 없음` |
| 예산 영구 저장 | `budgets.jsonl` |
| 사용 중 카테고리 삭제 | 기본 차단, `--replace-with` 로 대체 후 삭제. 반복 규칙이 쓰는 경우도 같은 규칙 |
| export 는 기간 조건 필수 | `commands._export_criteria` |
| CSV 스키마 고정 | `csv_io.CSV_COLUMNS` |
| 데코레이터 1개 이상 실제 적용 | `handle_errors`, `log_call`, `timed` |
| 스택트레이스 대신 원인 + 힌트, 종료 코드 | `decorators.handle_errors`, `errors.py` |
| 모듈 3개 이상, 계층 분리 | 19개 파일, CLI/서비스/저장소/모델 |

## 3. 실행 화면

### 3.1 첫 실행과 가져오기

```console
$ python -m budget_app category list
[안내] 저장 파일 5개를 새로 만들었습니다: data
[안내] 기본 카테고리를 등록했습니다: food, transport, rent, salary, shopping, etc
- food
- transport
- rent
- salary
- shopping
- etc

$ python -m budget_app import --from import.csv
[완료] imported=7, skipped=0
```

### 3.2 거래 추가 (잘못된 값은 재입력)

날짜에 `2024-13-40`, 카테고리에 `cafe`, 금액에 `-500` 을 먼저 넣어 본 화면입니다.
입력을 파이프로 넣어 실행한 출력에, 터미널에서 보이는 것처럼 입력값을 함께 적었습니다.

```console
$ python -m budget_app add
날짜(YYYY-MM-DD): 2024-13-40
[오류] 날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).
[힌트] 예: 2024-01-15
날짜(YYYY-MM-DD): 2024-01-28
타입(income/expense): expense
카테고리: cafe
[오류] 등록되지 않은 카테고리입니다: cafe
[힌트] 사용 가능: food, transport, rent, salary, shopping, etc / 새로 만들려면 category add 를 실행하세요.
카테고리: food
금액(양수): -500
[오류] 금액은 0보다 큰 정수여야 합니다 (최대 15자리).
[힌트] 예: 15000 (기호나 소수점 없이 입력)
금액(양수): 6500
메모(선택): 카페
태그(쉼표로 구분, 없으면 엔터): meal,coffee
[저장 완료] id=TX-000008
```

### 3.3 목록과 검색

```console
$ python -m budget_app list --limit 3
ID        | 날짜       | 타입    | 카테고리 |  금액 | 메모         | 태그
----------+------------+---------+----------+-------+--------------+-------------
TX-000008 | 2024-01-28 | expense | food     |  6500 | 카페         | meal,coffee
TX-000007 | 2024-01-25 | expense | shopping | 45000 | 겨울 장갑    |
TX-000006 | 2024-01-20 | expense | food     | 18000 | 저녁, 친구와 | meal,friends

$ python -m budget_app search --from 2024-01-01 --to 2024-01-31 --category food --tag meal
ID        | 날짜       | 타입    | 카테고리 |  금액 | 메모         | 태그
----------+------------+---------+----------+-------+--------------+-------------
TX-000008 | 2024-01-28 | expense | food     |  6500 | 카페         | meal,coffee
TX-000006 | 2024-01-20 | expense | food     | 18000 | 저녁, 친구와 | meal,friends
TX-000005 | 2024-01-15 | expense | food     | 15000 | 점심         | meal
TX-000003 | 2024-01-08 | expense | food     | 12000 | 점심         | meal
(총 4건)

$ python -m budget_app search --type expense --q 점심 --limit 1
ID        | 날짜       | 타입    | 카테고리 |  금액 | 메모 | 태그
----------+------------+---------+----------+-------+------+-----
TX-000005 | 2024-01-15 | expense | food     | 15000 | 점심 | meal
(총 1건)

$ python -m budget_app list --id 5                      # TX-000005 와 같음
ID        | 날짜       | 타입    | 카테고리 |  금액 | 메모 | 태그
----------+------------+---------+----------+-------+------+-----
TX-000005 | 2024-01-15 | expense | food     | 15000 | 점심 | meal
$ python -m budget_app search --id 5 --type income      # id 에 다른 조건을 겹침
조건에 맞는 거래가 없습니다.
$ python -m budget_app list --id TX-000404
[오류] 없는 데이터입니다: id=TX-000404
[힌트] list 또는 search 명령으로 id 를 확인하세요. (예: TX-000012)
```

### 3.4 예산과 월별 요약

```console
$ python -m budget_app budget set --month 2024-01 --amount 250000
[저장 완료] 2024-01 예산 250000원

$ python -m budget_app summary --month 2024-01 --top 3
[2024-01 요약] 거래 8건
총 수입: 3000000원
총 지출: 266500원
잔액: 2733500원
예산: 250000원 (사용률 106.6%)
[경고] 예산을 16500원 초과했습니다!
지출 TOP 3
1) rent     150000원
2) food      51500원
3) shopping  45000원

$ python -m budget_app summary --month 2023-07
[2023-07] 데이터 없음
```

### 3.5 수정, 삭제, 없는 id

```console
$ python -m budget_app update --id TX-000008 --amount 7000 --memo "카페(수정)"
[수정 완료] id=TX-000008
ID        | 날짜       | 타입    | 카테고리 | 금액 | 메모       | 태그
----------+------------+---------+----------+------+------------+------------
TX-000008 | 2024-01-28 | expense | food     | 7000 | 카페(수정) | meal,coffee

$ python -m budget_app delete --id TX-000004
[삭제 완료] id=TX-000004 (2024-01-12 transport 20000원)

$ python -m budget_app delete --id TX-000004
[오류] 없는 데이터입니다: id=TX-000004
[힌트] list 또는 search 명령으로 id 를 확인하세요. (예: TX-000012)
$ echo $?
1
```

### 3.6 카테고리 관리

```console
$ python -m budget_app category add --name hobby
[저장 완료] category=hobby

$ python -m budget_app category remove --name food
[오류] 'food' 카테고리를 사용하는 거래가 4건 있어 삭제할 수 없습니다.
[힌트] category remove --name food --replace-with <대체 카테고리> 로 거래를 옮긴 뒤 삭제할 수 있습니다.

$ python -m budget_app category remove --name shopping --replace-with etc
[안내] 거래 1건을 'etc' 카테고리로 옮겼습니다.
[삭제 완료] category=shopping
```

### 3.7 내보내기

```console
$ python -m budget_app export --out export.csv --month 2024-01
[완료] export.csv (7 records)

$ cat export.csv
date,type,category,amount,memo,tags
2024-01-02,income,salary,3000000,1월 월급,fixed
2024-01-05,expense,rent,150000,월세,"home,fixed"
2024-01-08,expense,food,12000,점심,meal
2024-01-15,expense,food,15000,점심,meal
2024-01-20,expense,food,18000,"저녁, 친구와","meal,friends"
2024-01-25,expense,etc,45000,겨울 장갑,
2024-01-28,expense,food,7000,카페(수정),"meal,coffee"

$ python -m budget_app export --out export.csv
[오류] 내보낼 기간을 지정해야 합니다.
[힌트] --month YYYY-MM 또는 --from YYYY-MM-DD --to YYYY-MM-DD 를 지정하세요.
```

### 3.8 명령 형식 오류와 실행 로그

```console
$ python -m budget_app list --limti 3
[오류] 명령 형식이 올바르지 않습니다: unrecognized arguments: --limti 3
[힌트] 사용법은 'python -m budget_app --help' 로 확인하세요.
$ echo $?
2

$ python -m budget_app search --tag meal --verbose
[log] 시작: BudgetService.search
[log] 소요 시간: BudgetService.search 0.10ms
[log] 완료: BudgetService.search
ID        | 날짜       | 타입    | 카테고리 |  금액 | 메모         | 태그
...
```

### 3.9 저장 파일

```console
$ ls data
backups  budgets.jsonl  categories.jsonl  meta.jsonl  recurring.jsonl  transactions.jsonl

$ head -3 data/transactions.jsonl
{"id": "TX-000001", "type": "income", "date": "2024-01-02", "amount": 3000000, "category": "salary", "memo": "1월 월급", "tags": ["fixed"]}
{"id": "TX-000002", "type": "expense", "date": "2024-01-05", "amount": 150000, "category": "rent", "memo": "월세", "tags": ["home", "fixed"]}
{"id": "TX-000003", "type": "expense", "date": "2024-01-08", "amount": 12000, "category": "food", "memo": "점심", "tags": ["meal"]}
```

### 3.10 경계·실패 사례

핵심 명령마다 "잘못된 경우에 어떻게 끝나는가"를 한 줄씩 정리했습니다. 모두 자동 테스트로 확인한 동작입니다.

| 명령 | 입력 | 결과 | 종료 코드 | 테스트 |
| --- | --- | --- | --- | --- |
| `add` | 날짜 `2024-13-40`, 금액 `-500` | 이유를 알려 주고 그 항목만 다시 물음 | 0 | `test_add_reprompts_until_each_field_is_valid` |
| `add` | 입력 도중 Ctrl+D (EOF) | 아무것도 저장하지 않고 취소 안내 | 1 | `test_add_cancelled_by_end_of_input_saves_nothing` |
| `add` | 금액 5,000자리 숫자, 비 ASCII 숫자 | 입력 오류로 거부(최대 15자리) | 1 | `test_hostile_values_are_rejected_as_validation_errors` |
| `list` | `--limit 0`, `--limit abc` | `[오류] --limit 값은 1 이상의 정수여야 합니다.` | 1 | `test_list_on_empty_data_and_invalid_limit` |
| `list` | 거래 0건 | `거래 내역이 없습니다. add 명령으로 ...` | 0 | `test_empty_states_are_explained` |
| `search` | `--from` 이 `--to` 보다 늦음, `--min-amount` > `--max-amount` | 순서가 바뀌었다고 안내 | 1 | `test_search_by_options`, `test_search_by_amount_range` |
| `search` | `--limit` 없이 1,000건 초과 일치 | 결과 전체 출력 + `--limit` 권장 안내(표준 오류) | 0 | `test_search_without_limit_suggests_limit_when_result_is_large` |
| `summary` | 거래가 없는 달 | `[2024-03] 데이터 없음` | 0 | `test_summary_without_data_says_so` |
| `summary` | 예산 80% 이상 / 초과 | `[주의]` / `[경고] 예산을 N원 초과했습니다!` | 0 | `test_budget_near_limit_shows_caution_and_income_only_month_has_no_ranking` |
| `update` | 바꿀 옵션 없음, 없는 id, `--amount -1` | 파일을 건드리지 않고 오류 | 1 | `test_update_failures_leave_data_untouched` |
| `delete` | 없는 id | `[오류] 없는 데이터입니다: id=...` + id 확인 힌트 | 1 | `test_delete_removes_one_and_unknown_id_is_not_found` |
| `category remove` | 사용 중인 카테고리, 대체 없음 | 사용 건수를 알려 주며 차단 | 1 | `test_category_in_use_cannot_be_removed_without_replacement` |
| `category remove --replace-with` | 거래 옮기는 단계에서 I/O 실패 | 규칙만 옮겨진 상태로 멈추고 카테고리는 남음. 재실행하면 완료 | 1 | `test_interrupted_category_replacement_leaves_no_dangling_reference` |
| `export` | 기간 조건 없음, `--month` 와 `--from` 동시 지정 | 어떤 조합이 필요한지 힌트 | 1 | `test_export_and_import_report_counts` |
| `import` | 없는 파일, 필수 컬럼 없는 헤더, cp949 파일 | 아무것도 등록하지 않고 원인 안내 | 1 | `test_import_rejects_bad_files` |
| `import` | 12행 전부 잘못됨 | `imported=0, skipped=12`, 사유 10건 + `외 2건` | 0 | `test_category_add_by_option_and_import_skip_reasons` |
| `import --strict` | 한 행이라도 잘못됨 | 아무것도 등록하지 않음 | 1 | `test_strict_import_exits_with_error_and_writes_nothing` |
| `import` | 1만 행 CSV | 전부 등록, 약 1초 | 0 | `test_large_csv_import_registers_every_row_in_one_append` |
| `import` | 3행 중 2행 쓴 뒤 디스크 가득 참 | 쓴 2행은 읽을 수 있고, 재실행 시 새 id(겹치지 않음) | 1 | `test_interrupted_import_leaves_readable_file_and_never_reuses_ids` |
| `import --skip-duplicates` | 저장된 거래와 같은 행, 같은 파일 두 번 import | 저장된 개수만큼 `이미 있는 거래` 로 건너뜀(파일 안의 실제 반복은 등록). `--strict` 와 함께 써도 중복은 실패 사유 아님 | 0 | `test_skip_duplicates_ignores_rows_already_stored_and_repeated_in_file`, `test_strict_import_with_skip_duplicates_only_fails_on_invalid_rows` |
| `budget remove` | 설정되지 않은 달 | `예산이 설정되어 있지 않습니다` | 1 | `test_budget_remove_command` |
| `category remove --replace-with` | 마지막 단계(카테고리 삭제)에서 I/O 실패 | `완료: 거래 1건 ... / 남음: 카테고리 'gym' 삭제` 힌트 | 1 | `test_failure_at_last_step_reports_moved_counts_and_remaining_step` |
| `category remove` | 첫 단계에서 I/O 실패 | `완료: 없음 / 남음: 카테고리 'gym' 삭제` 힌트 | 1 | `test_failure_before_any_step_reports_nothing_done` |
| `search` | `config.SEARCH_DEFAULT_LIMIT=2` 설정, `--limit` 없음 | 2건만 표시하고 `기본 상한 2건` 안내 | 0 | `test_search_default_cap_from_config_applies_when_limit_is_omitted` |
| 29가지 조합 | 핵심 명령의 실패 입력 29개 | 기대 종료 코드(0/1/2)를 한 표로 고정 | 표 참조 | `test_exit_codes_per_failure_case` |
| `recurring apply` | 규칙의 카테고리가 지워진 뒤 | 그 규칙만 `실패` 로 보고 | 1 | `test_export_by_date_range_and_recurring_failure_report` |
| `backup` | 같은 초에 두 번 실행 | `같은 시각의 백업이 이미 있습니다` | 1 | `test_backup_copies_data_files_into_timestamped_folder` |
| 모든 명령 | 깨진 `transactions.jsonl` | 몇 번째 줄인지 알려 주고 종료(스택트레이스 없음) | 1 | `test_corrupted_data_file_is_reported_without_traceback` |
| 모든 명령 | 옵션 오타 | `명령 형식이 올바르지 않습니다` + `--help` 안내 | 2 | `test_usage_errors_exit_with_2_and_hint` |

## 4. 보너스 과제

```console
$ python -m budget_app recurring add --day 31 --type expense --category rent --amount 150000 --memo 월세
[저장 완료] id=RC-0001 (매월 31일 rent 150000원)

$ python -m budget_app recurring apply --month 2024-02
[완료] 2024-02 반복 내역: created=1, already_applied=0, failed=0
  - 생성 TX-000009 2024-02-29 rent 150000원

$ python -m budget_app recurring apply --month 2024-02
[완료] 2024-02 반복 내역: created=0, already_applied=1, failed=0

$ python -m budget_app backup
[백업 완료] data/backups/20261002-151801 (5 files)
- transactions.jsonl
- categories.jsonl
- budgets.jsonl
- recurring.jsonl
- meta.jsonl
```

| 보너스 | 구현 | 확인 |
| --- | --- | --- |
| 백업 | `backup.py`. `data/backups/<YYYYMMDD-HHMMSS>/` 에 복사 | `test_backup_copies_data_files_into_timestamped_folder` |
| 반복 내역 | `recurring.py`. 31일 규칙이 2월 29일로 조정되고, 두 번째 실행은 중복 생성하지 않음 | `test_apply_creates_once_and_clamps_day_to_month_end` |
| 표 정렬 | `formatter.py`. 한글을 2칸으로 계산해 열 맞춤 | `test_table_alignment_counts_korean_as_double_width` |
| 저장 원자성 | `storage.atomic_open`. 실패 시 원본 유지, 임시 파일 정리 | `test_failed_atomic_write_keeps_original_and_leaves_no_temp_file` |

## 5. 테스트 결과

```console
$ python -m unittest discover -s tests -t .
...................................................................................................................
----------------------------------------------------------------------
Ran 115 tests in 2.119s

OK
```

| 파일 | 대상 | 테스트 수 |
| --- | --- | --- |
| `tests/test_validators_models.py` | 검증 함수, 모델 | 20 |
| `tests/test_storage.py` | JSONL 입출력, 원자적 쓰기, 저장소 | 18 |
| `tests/test_services.py` | 서비스, CSV(1만 행·중단·중복 포함), 반복 내역, 백업 | 39 |
| `tests/test_cli.py` | 명령 실행(E2E, 종료 코드 29가지 표 포함), 데코레이터, 표 정렬 | 38 |

- Python 3.13.5와 3.10.12에서 모두 통과했습니다.
- 줄 실행률은 `python -m trace --count --missing` 으로 측정했습니다. 측정된 18개 모듈 중 15개가 100%이고,
  `commands.py` 98%, `decorators.py` 91%, `prompts.py` 80% 입니다.
  실행되지 않은 줄은 끊긴 파이프 처리와 잘못된 인코딩의 키보드 입력처럼 자동 테스트로 재현하기 어려운 분기이며, 이 둘은 터미널에서 직접 실행해 확인했습니다.

## 6. 스트리밍 처리 실측

거래 30만 건(40.4MB)의 `transactions.jsonl` 을 만들어 `tracemalloc` 으로 최대 메모리를 측정했습니다.

| 작업 | 최대 메모리 |
| --- | --- |
| 스트리밍 `list_recent(10)` | 약 147KB |
| 스트리밍 `summarize("2024-01", 3)` | 약 147KB |
| (비교) 전부 리스트로 읽은 뒤 정렬 | 약 182MB |

스트리밍 방식의 메모리 사용량은 파일 크기와 무관하게 일정했고, 전부 읽는 방식의 약 1/1200 이었습니다.
처리 시간은 두 방식 모두 5~6초로 비슷했습니다. 스트리밍은 메모리를 줄이는 것이지 시간을 줄이는 것은 아닙니다.

## 7. 코드 리뷰와 보완 내역

구현 후 독립적인 코드 리뷰를 한 차례 받아, 실제로 재현된 문제를 고치고 회귀 테스트를 추가했습니다.

| 발견된 문제 | 조치 |
| --- | --- |
| 마지막 줄바꿈이 빠진 파일에 덧붙이면 두 레코드가 한 줄로 붙어 파일이 깨짐 | 덧붙이기 전에 줄바꿈 여부를 확인해 보정 |
| 4300자리가 넘는 숫자, UTF-8이 아닌 저장 파일, 타입이 틀린 레코드가 "예기치 못한 오류"(코드 3)로 처리됨 | 각각 입력 오류, 데이터 파일 오류(코드 1)로 분류하고 힌트 제공. 금액은 최대 15자리 |
| 대체 카테고리로 삭제해도 반복 규칙은 지워진 카테고리를 계속 가리킴 | 반복 규칙도 함께 옮기고, 대체 카테고리가 없으면 삭제 차단 |
| `recurring apply` 가 실패한 규칙이 있어도 종료 코드 0 | 실패가 있으면 종료 코드 1 |
| 메모의 줄바꿈·제어 문자가 표를 깨뜨리고 터미널 제어 코드로 실행됨 | 출력할 때 제어 문자를 공백으로 치환(저장값은 그대로) |
| 다시 쓴 파일의 권한이 0600으로 바뀜 | 기존 파일의 권한을 유지 |
| `... \| head -1` 에서 "Broken pipe" 오류 메시지 출력 | 메시지 없이 종료 |
| 아랍 숫자 등 비 ASCII 숫자와 `1,5,0` 같은 쉼표를 금액으로 인정 | ASCII 숫자와 올바른 천 단위 쉼표만 허용 |
| CSV 헤더의 대소문자·공백, 자모가 분리된 한글 카테고리명 불일치 | 헤더와 이름을 정규화해 비교 |

## 7.1 평가항목 점검 후 보완 (2026-10-16)

| 보완 | 내용 |
| --- | --- |
| `import --strict` 추가 | 부분 성공(기본)에 더해 롤백 방식을 제공. 잘못된 행이 하나라도 있으면 아무것도 등록하지 않고 종료 코드 1 |
| `search --min-amount/--max-amount` | 금액 범위 검색 (PR #1) |
| 평가 답변 보강 | 10만 건 병목/개선(Q15), 깨진 CSV 행 처리(Q16), 평가항목별 답변서([04-evaluation-checklist.md](04-evaluation-checklist.md)) |

## 7.2 AI 사전평가 보완 제안 반영 (2026-10-17)

16개 항목이 모두 통과한 사전평가에서 항목마다 나온 "보완" 제안을 반영했습니다. 항목별 조치는 [04-evaluation-checklist.md](04-evaluation-checklist.md) 끝의 표에 있습니다. 코드가 바뀐 것은 아래 네 가지입니다.

| 보완 | 내용 |
| --- | --- |
| 카테고리 대체 순서 수정 | 기존에는 거래를 옮기고 카테고리를 지운 **뒤에** 반복 규칙을 옮겼기 때문에, 규칙을 쓰는 단계에서 실패하면 지워진 카테고리를 가리키는 규칙이 남았습니다. 규칙 → 거래 → 카테고리 순서로 바꾸고 중단 테스트를 추가했습니다 |
| `search` 안내 | `--limit` 없이 결과가 1,000건을 넘으면 `--limit` 사용을 권하는 안내를 표준 오류에 출력. 도움말에도 권장 문구 추가 |
| 대용량·중단 테스트 | 1만 행 CSV import(약 1초), 덧붙이는 도중 디스크 오류 시 파일 상태와 id 재사용 금지 검증 |
| 타입 검사 | `mypy --strict` 가 지적한 6곳(핸들러·파서 타입, 제네릭 인자)을 고쳐 오류 0건 |

## 7.3 2차 AI 사전평가 보완 제안 반영 (2026-10-17)

1차 반영 뒤 다시 받은 사전평가(16/16 통과)의 제안을 반영했습니다. 항목별 조치는 [04-evaluation-checklist.md](04-evaluation-checklist.md) 의 두 번째 반영표에 있습니다. 코드가 바뀐 것은 아래입니다.

| 보완 | 내용 |
| --- | --- |
| `import --skip-duplicates` | 계획으로만 있던 중복 감지를 구현. 날짜·타입·카테고리·금액·메모가 같은 거래를 저장된 개수만큼 건너뛰고(같은 파일 재입력은 멱등, 실제 반복 거래는 보존) 사유를 보고. 테스트 3개 |
| `budget remove --month` | 예산 삭제 명령 추가. 요약에서 예산 줄과 경고가 사라지는 것을 테스트로 확인 |
| 카테고리 대체 실패 시 진행 상황 출력 | `StepFailedError` 로 `완료: ... / 남음: ...` 힌트를 출력. 규칙 이동 뒤 실패, 마지막 단계 실패, 아무것도 못 한 경우 세 가지 테스트 |
| `config.SEARCH_DEFAULT_LIMIT` | `--limit` 없는 `search` 의 기본 상한(기본값 None=전체). 설정하면 그 건수만 보여 주고 안내 |
| 종료 코드 표 테스트 | 핵심 명령의 실패 입력 29가지에 기대 종료 코드를 명시한 `test_exit_codes_per_failure_case` |
| 예기치 못한 오류 힌트 | 재현 보고에 필요한 최소 정보(명령 전체, `--verbose` 마지막 `[log]` 줄)를 힌트에 명시. `handle_errors` docstring 에 예외→종료 코드 표 |

## 7.4 `--id` 직접 조회 추가 (2026-10-28)

시연 중 "방금 만든 거래 하나만 보고 싶다"는 요구에 `search` 조건 조합이나 `list --limit` 로 우회해야 했던 점을 고쳤습니다.

| 보완 | 내용 |
| --- | --- |
| `list --id ID` | id 로 거래 한 건만 출력. 없는 id 는 update/delete 와 같은 `없는 데이터` 오류(코드 1) |
| `search --id ID [...]` | id 를 검색 조건(`SearchCriteria.tx_id`)에 추가. 다른 조건과 겹치면 그 한 건에 적용하고, 안 맞으면 빈 결과(코드 0). id 는 유일하므로 첫 일치에서 파일 읽기를 멈춤 |
| `parse_transaction_id` | `TX-000012`, `tx-000012`, `12` 를 같은 id 로 정규화하는 검증 함수. `list/search/update/delete` 네 명령이 공유 |
| 테스트 5개 | 검증 함수 2, 서비스 2, CLI 1 (테스트 110 → 115개, `mypy --strict` 0건) |

## 8. 알려진 한계

고치지 않고 남겨 둔 항목입니다.

- **동시 실행 시 id 중복 가능.** 여러 프로세스가 같은 데이터 폴더에 동시에 `add` 하면 같은 id가 발급될 수 있습니다(12개 프로세스 병렬 실행으로 재현됨).
  한 사람이 한 터미널에서 쓰는 프로그램이라는 전제로 파일 잠금은 넣지 않았습니다.
- **반복 내역의 중복 방지는 태그에 의존합니다.** 생성된 거래의 `recurring:RC-0001` 태그를 `update --tags` 로 지우거나 날짜를 다른 달로 옮기면 같은 달에 다시 생성됩니다.
- **수정·삭제·조회 시간은 파일 크기에 비례합니다.** 인덱스가 없어 30만 건에서 수 초가 걸립니다.
- **`search` 에 `--limit` 이 없으면** 조건에 맞는 결과를 모두 모아 정렬합니다. 1,000건을 넘으면 `--limit` 을 권하는 안내만 띄우고 막지는 않습니다. 상한을 강제하려면 `config.SEARCH_DEFAULT_LIMIT` 에 숫자를 넣습니다(옵션이 아닌 상수인 이유: 한 사람이 쓰는 프로그램이고, 스크립트에서 전체 결과를 기대하는 쪽이 기본이라고 보았기 때문).
- **`-` 로 시작하는 값**은 `--memo=-abc` 처럼 `=` 로 붙여 써야 합니다(`argparse` 의 동작).
- **같은 CSV를 두 번 `import` 하면** 기본으로는 두 번 등록됩니다. `--skip-duplicates` 를 붙여야 건너뛰며, 기준은 날짜·타입·카테고리·금액·메모입니다(태그 제외).
- **`import` 가 덧붙이는 도중 중단되면** 그때까지 쓰인 행만 남고 자동으로 되돌리지 않습니다. 파일은 읽을 수 있고 id 는 겹치지 않습니다.
