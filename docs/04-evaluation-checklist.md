# 평가항목 체크리스트 답변 — B2-1 나만의 용돈 기입장

평가항목 문서(`B2-1 평가항목.md`)의 체크리스트 16개 항목에 대해 **충족 여부 → 답변(1~2줄) → 근거 위치(URL)** 순서로 정리했습니다.
근거 링크는 GitHub `main` 브랜치 기준이며, 문서 링크는 `?plain=1#L줄번호` 로 해당 줄을 가리킵니다.

저장소: https://github.com/newids/codyssey-b2-1

## 점검 결과 요약

| 구분 | 항목 수 | 충족 | 이번에 보완한 것 |
| --- | --- | --- | --- |
| 항목 1 (기능 동작) | 7 | 7 | - |
| 항목 2 (구조 설명) | 3 | 3 | - |
| 항목 3 (개념 설명) | 3 | 3 | - |
| 항목 4 (설계 판단) | 3 | 3 | `import --strict`(롤백 방식) 추가, 10만 건 병목/개선 답변(Q15), 깨진 행 처리 답변(Q16) 추가 |

이 문서를 바탕으로 받은 AI 사전평가(2026-10-17, 16/16 통과)의 항목별 "보완" 제안도 반영했습니다. 제안별 조치는 문서 끝의 [보완 제안 반영표](#ai-사전평가-보완-제안-반영-2026-10-17)에 있습니다.

점검 중 모자란다고 본 것은 항목 4의 마지막 두 개였습니다. "병목과 개선"은 한계 목록(Q14)에만 짧게 있었고, "깨진 행 처리"는 부분 성공 한 가지만 구현되어 있어 롤백 전략을 비교해 설명하기 어려웠습니다. 두 가지 모두 코드와 답변을 보강했고, 테스트는 97개로 늘어 모두 통과합니다.

---

## 항목 1 — 기능 동작

### 1-1. add/list/search/summary/export/import/update/delete가 요구사항대로 동작하는가?

**충족.** 8개 명령 모두 `python -m budget_app <command>` 로 동작하며, 명령마다 E2E 테스트가 실제 진입점(`main`)을 호출해 출력과 종료 코드를 검증합니다.
`add` 는 대화형, 나머지는 `--옵션` 방식이고 `update` 는 옵션 방식으로 고정했습니다.

- 명령 정의: [budget_app/cli.py#L44-L147](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/cli.py#L48-L154)
- 명령 처리기: [budget_app/commands.py#L32-L169](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/commands.py#L34-L178)
- E2E 테스트: [tests/test_cli.py#L22-L175](https://github.com/newids/codyssey-b2-1/blob/main/tests/test_cli.py#L23-L178)
- 실행 화면: [docs/02-result-report.md §3](https://github.com/newids/codyssey-b2-1/blob/main/docs/02-result-report.md?plain=1#L59), 명령 요약표: [README.md §2](https://github.com/newids/codyssey-b2-1/blob/main/README.md?plain=1#L36)

### 1-2. 프로그램 재실행 후에도 거래/카테고리/예산 데이터가 유지되는가? (저장 파일 3개 이상)

**충족.** `./data` 에 `transactions / categories / budgets / recurring / meta` 5개 JSONL 파일로 저장하며, 첫 실행 때 없는 파일을 자동 생성합니다.
테스트는 `create_app` 을 다시 호출해 새 프로세스처럼 읽어도 예산이 남아 있는지 확인합니다.

- 파일 경로 정의: [budget_app/config.py#L23-L54](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/config.py#L24-L55)
- 초기화(자동 생성): [budget_app/app.py#L36-L49](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/app.py#L38-L51)
- 테스트: [test_first_run_creates_files_and_default_categories](https://github.com/newids/codyssey-b2-1/blob/main/tests/test_services.py#L43), [test_budget_is_persisted_and_reflected_in_summary](https://github.com/newids/codyssey-b2-1/blob/main/tests/test_services.py#L159)
- 파일 형식 설명: [README.md §4](https://github.com/newids/codyssey-b2-1/blob/main/README.md?plain=1#L125)

### 1-3. category add/list/remove가 정상 동작하는가? (삭제 시 사용 중인 카테고리 처리 포함)

**충족.** 사용 중인 카테고리는 사용 건수를 알려 주며 삭제를 막고, `--replace-with` 를 주면 거래와 반복 규칙을 대체 카테고리로 옮긴 뒤 삭제합니다.
대체 카테고리도 등록된 것이어야 하고, 삭제 대상과 같으면 거부합니다.
세 파일은 **반복 규칙 → 거래 → 카테고리** 순서로 처리해, 도중에 실패해도 지워진 카테고리를 가리키는 데이터가 남지 않고 재실행하면 이어서 끝납니다(한 트랜잭션은 아님).

- 삭제 정책: [budget_app/services.py#L143-L168](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/services.py#L148-L180), 반복 규칙 처리: [budget_app/recurring.py#L60-L78](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/recurring.py#L62-L87)
- 중단 테스트: [test_interrupted_category_replacement_leaves_no_dangling_reference](https://github.com/newids/codyssey-b2-1/blob/main/tests/test_services.py#L381)
- 테스트: [test_category_in_use_cannot_be_removed_without_replacement](https://github.com/newids/codyssey-b2-1/blob/main/tests/test_services.py#L176), [test_category_removal_with_replacement_moves_transactions](https://github.com/newids/codyssey-b2-1/blob/main/tests/test_services.py#L185), [test_category_commands](https://github.com/newids/codyssey-b2-1/blob/main/tests/test_cli.py#L117)
- 실행 화면: [docs/02-result-report.md §3.6](https://github.com/newids/codyssey-b2-1/blob/main/docs/02-result-report.md?plain=1#L170)

### 1-4. budget set이 저장되며, summary에서 예산 사용률/초과 여부가 출력되는가?

**충족.** `budget set` 은 `budgets.jsonl` 에 월별로 저장(같은 달은 덮어쓰기)되고, `summary` 는 예산이 있으면 `사용률 N%` 를, 80% 이상이면 `[주의]`, 초과하면 `[경고] 예산을 N원 초과했습니다!` 를 출력합니다.

- 저장: [budget_app/stores.py#L58-L71](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/stores.py#L60-L77), 사용률 계산: [budget_app/models.py#L258-L267](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/models.py#L258-L267), 출력: [budget_app/formatter.py#L93-L102](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/formatter.py#L93-L102)
- 테스트: [test_budget_and_summary_with_warning](https://github.com/newids/codyssey-b2-1/blob/main/tests/test_cli.py#L95), [test_budget_near_limit_shows_caution_and_income_only_month_has_no_ranking](https://github.com/newids/codyssey-b2-1/blob/main/tests/test_cli.py#L180)
- 실행 화면: [docs/02-result-report.md §3.4](https://github.com/newids/codyssey-b2-1/blob/main/docs/02-result-report.md?plain=1#L129)

### 1-5. import/export가 명시된 CSV 스키마(UTF-8, 헤더, 컬럼)로 동작하는가?

**충족.** 스키마 `date,type,category,amount,memo,tags` 를 상수로 고정해 export 헤더와 import 검증에 같이 쓰며, UTF-8(BOM 포함)로 읽고 씁니다.
export 한 파일을 그대로 import 해도 메모의 쉼표·따옴표·여러 태그가 보존됩니다.

- 스키마 상수와 입출력: [budget_app/csv_io.py#L17-L97](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/csv_io.py#L17-L97)
- 테스트: [test_export_then_import_round_trips](https://github.com/newids/codyssey-b2-1/blob/main/tests/test_services.py#L210), [test_import_accepts_excel_bom_and_optional_columns_missing](https://github.com/newids/codyssey-b2-1/blob/main/tests/test_services.py#L270)
- 스키마 문서: [README.md §5](https://github.com/newids/codyssey-b2-1/blob/main/README.md?plain=1#L142), 예시 파일: [samples/import_sample.csv](https://github.com/newids/codyssey-b2-1/blob/main/samples/import_sample.csv)

### 1-6. 잘못된 입력/파일 오류에서 스택트레이스 없이 오류 메시지와 해결 힌트를 출력하는가?

**충족.** 모든 의도된 오류는 `BudgetAppError(message, hint)` 로 던지고, `handle_errors` 데코레이터가 `[오류] 원인` / `[힌트] 해결 방법` 두 줄로 바꿔 표준 오류에 출력합니다.
깨진 저장 파일은 몇 번째 줄인지, 잘못된 CSV 는 몇 행인지 알려 주며, 예기치 못한 예외도 스택트레이스 없이 처리됩니다.

- 예외 계층: [budget_app/errors.py#L12-L36](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/errors.py#L12-L36), 변환: [budget_app/decorators.py#L32-L69](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/decorators.py#L32-L69), 인자 오류: [budget_app/cli.py#L20-L31](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/cli.py#L23-L34)
- 테스트: [test_corrupted_data_file_is_reported_without_traceback](https://github.com/newids/codyssey-b2-1/blob/main/tests/test_cli.py#L309), [test_unreadable_data_files_are_data_errors_not_unexpected_errors](https://github.com/newids/codyssey-b2-1/blob/main/tests/test_cli.py#L272)
- 실행 화면: [docs/02-result-report.md §3.2, §3.5](https://github.com/newids/codyssey-b2-1/blob/main/docs/02-result-report.md?plain=1#L78)

### 1-7. 오류 상황에서 종료 코드가 0이 아님을 확인할 수 있는가?

**충족.** 정상 0, 입력·데이터 오류 1, 명령 형식 오류 2, 예기치 못한 오류 3, Ctrl+C 130 으로 구분하고 `sys.exit(main())` 으로 전달합니다.
실제 `python -m budget_app` 프로세스를 띄워 반환 코드를 확인하는 테스트가 있습니다.

- 종료 코드 상수: [budget_app/errors.py#L5-L9](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/errors.py#L5-L9), 진입점: [budget_app/__main__.py](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/__main__.py)
- 테스트: [test_module_entry_point_returns_exit_codes](https://github.com/newids/codyssey-b2-1/blob/main/tests/test_cli.py#L349), [test_usage_errors_exit_with_2_and_hint](https://github.com/newids/codyssey-b2-1/blob/main/tests/test_cli.py#L301), [test_handle_errors_converts_exceptions_to_exit_codes](https://github.com/newids/codyssey-b2-1/blob/main/tests/test_cli.py#L366)
- 종료 코드 표: [README.md §6](https://github.com/newids/codyssey-b2-1/blob/main/README.md?plain=1#L167)

---

## 항목 2 — 구조 설명

### 2-1. 코드가 3개 이상 모듈로 분리되어 있고, 각 모듈의 책임을 "어떻게" 나눴는지 설명할 수 있는가?

**충족.** 18개 모듈을 CLI(입력 해석·출력) → 서비스(업무 규칙) → 저장소(파일 입출력) → 모델(데이터 구조·검증) 네 계층으로 나누고, 의존은 위에서 아래로만 흐르게 했습니다.
나누는 기준은 "무엇이 바뀔 때 어디만 고치면 되는가"입니다. 저장 포맷이 바뀌면 저장소만, 출력 모양이 바뀌면 CLI 만 고칩니다.

- 구조도와 의존 방향: [README.md §7](https://github.com/newids/codyssey-b2-1/blob/main/README.md?plain=1#L195), [docs/01-mission-guide.md §3.1~3.2](https://github.com/newids/codyssey-b2-1/blob/main/docs/01-mission-guide.md?plain=1#L51)
- 답변: [docs/03-evaluation-answers.md Q2](https://github.com/newids/codyssey-b2-1/blob/main/docs/03-evaluation-answers.md?plain=1#L37)
- 조립 지점(계층 연결): [budget_app/app.py#L23-L33](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/app.py#L25-L35)

### 2-2. 최소 2개 이상의 클래스에 부여한 책임 경계를 "어떻게" 정했는지 설명할 수 있는가?

**충족.** `TransactionRepository` 는 "파일을 어떻게 읽고 쓰는가"만, `BudgetService` 는 "어떤 거래가 유효하고 어떻게 집계하는가"만 맡습니다. 경계 기준은 **파일 형식을 아는가 / 업무 규칙을 아는가**입니다.
`Transaction` 모델은 자기 검증만, `CategoryStore`·`BudgetStore` 는 각자 파일 하나만 담당하며, 서비스는 저장소를 생성자로 받아 테스트에서 바꿔 끼울 수 있습니다.

- 저장소: [budget_app/repository.py#L18-L73](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/repository.py#L18-L78), 서비스: [budget_app/services.py#L26-L38](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/services.py#L26-L43), 모델: [budget_app/models.py#L66-L125](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/models.py#L66-L125)
- 책임표: [docs/01-mission-guide.md §3.2](https://github.com/newids/codyssey-b2-1/blob/main/docs/01-mission-guide.md?plain=1#L78), 답변: [docs/03-evaluation-answers.md Q2](https://github.com/newids/codyssey-b2-1/blob/main/docs/03-evaluation-answers.md?plain=1#L37)

### 2-3. 파일 기반 update/delete를 "어떻게" 안전하게 처리했는지 설명할 수 있는가?

**충족.** 원본을 직접 고치지 않고, 같은 폴더의 임시 파일에 전체를 다시 쓴 뒤 `fsync` → `os.replace` 로 한 번에 교체합니다. 도중에 죽어도 원본은 그대로이고 임시 파일만 남습니다.
수정 전에 id 존재와 값 유효성을 먼저 검사하고, 삭제한 id 는 `meta.jsonl` 의 일련번호 덕분에 재사용되지 않습니다.

- 원자적 교체: [budget_app/storage.py#L77-L94](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/storage.py#L77-L94), 스트리밍 재작성: [budget_app/repository.py#L41-L61](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/repository.py#L46-L66), 검증 후 쓰기: [budget_app/services.py#L65-L86](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/services.py#L70-L88)
- 테스트: [test_failed_atomic_write_keeps_original_and_leaves_no_temp_file](https://github.com/newids/codyssey-b2-1/blob/main/tests/test_storage.py#L62), [test_update_failures_leave_data_untouched](https://github.com/newids/codyssey-b2-1/blob/main/tests/test_services.py#L116), [test_deleted_id_is_never_reused](https://github.com/newids/codyssey-b2-1/blob/main/tests/test_storage.py#L142)
- 답변: [docs/03-evaluation-answers.md Q7, Q8](https://github.com/newids/codyssey-b2-1/blob/main/docs/03-evaluation-answers.md?plain=1#L195), 개념: [docs/01-mission-guide.md §5.4](https://github.com/newids/codyssey-b2-1/blob/main/docs/01-mission-guide.md?plain=1#L200)

---

## 항목 3 — 개념 설명

### 3-1. list/search를 제너레이터로 스트리밍 처리한 방식을 "어떻게" 구현했고, "왜" 유리한지 설명할 수 있는가?

**충족.** `read_jsonl` 이 파일을 한 줄씩 `yield` 하고, 그 위에 필터(제너레이터 식)와 `heapq.nlargest(limit, …)` 를 이어 붙여 "파일 → 객체 → 조건 → 최신 N건"이 한 건씩 흐르게 했습니다.
30만 건(40MB) 실측에서 최대 메모리가 147KB 로, 전부 읽어 정렬한 182MB 의 약 1/1200 이었습니다. 메모리가 파일 크기와 무관해지는 것이 이점입니다.

- 제너레이터: [budget_app/storage.py#L20-L38](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/storage.py#L20-L38), [budget_app/repository.py#L23-L25](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/repository.py#L28-L30), 최신 N건: [budget_app/services.py#L47-L63](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/services.py#L52-L68)
- 테스트: [test_read_is_a_lazy_generator](https://github.com/newids/codyssey-b2-1/blob/main/tests/test_storage.py#L20), [test_list_recent_is_newest_first_and_limited](https://github.com/newids/codyssey-b2-1/blob/main/tests/test_services.py#L63)
- 실측: [docs/02-result-report.md §6](https://github.com/newids/codyssey-b2-1/blob/main/docs/02-result-report.md?plain=1#L287), 답변: [docs/03-evaluation-answers.md Q3](https://github.com/newids/codyssey-b2-1/blob/main/docs/03-evaluation-answers.md?plain=1#L54), 개념: [docs/01-mission-guide.md §5.1](https://github.com/newids/codyssey-b2-1/blob/main/docs/01-mission-guide.md?plain=1#L160)

### 3-2. 데코레이터로 분리한 공통 기능이 무엇이며, "왜" 분리가 필요했는지 설명할 수 있는가?

**충족.** `handle_errors`(예외 → 메시지·종료 코드), `log_call`(시작/완료/실패 로그), `timed`(소요 시간) 세 개를 만들어 `main` 과 서비스·저장소의 주요 메서드에 붙였습니다.
이 셋은 모든 명령에 똑같이 필요하지만 가계부 로직과 무관합니다. 명령마다 `try/except` 를 반복하면 한 곳만 빠져도 스택트레이스가 노출되므로 한 곳에 모았습니다.

- 구현: [budget_app/decorators.py#L32-L109](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/decorators.py#L32-L109), 적용: [budget_app/cli.py#L34-L35](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/cli.py#L37-L38), [budget_app/services.py#L47-L49](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/services.py#L52-L54)
- 테스트: [test_decorators_preserve_function_identity_and_result](https://github.com/newids/codyssey-b2-1/blob/main/tests/test_cli.py#L379), [test_verbose_prints_log_and_elapsed_time](https://github.com/newids/codyssey-b2-1/blob/main/tests/test_cli.py#L341)
- 답변: [docs/03-evaluation-answers.md Q4](https://github.com/newids/codyssey-b2-1/blob/main/docs/03-evaluation-answers.md?plain=1#L90), 개념: [docs/01-mission-guide.md §5.2](https://github.com/newids/codyssey-b2-1/blob/main/docs/01-mission-guide.md?plain=1#L180)

### 3-3. 타입 힌트를 적용해 얻는 이점을 실제 코드 예로 "어떻게" 확인했고 "왜" 도움이 되는지 설명할 수 있는가?

**충족.** `iter_all() -> Iterator[Transaction]` 과 `list_recent() -> list[Transaction]` 의 차이가 "한 번만 순회 가능 / 여러 번 사용 가능"을, `find_by_id() -> Transaction | None` 이 "없는 경우를 처리하라"를 시그니처만으로 알려 줍니다.
`rewrite(transform: Callable[[Transaction], Transaction | None])` 처럼 넘길 함수의 모양도 계약으로 고정되어, 함수 본문을 열지 않고 계층 간 경계를 지킬 수 있습니다.
검증은 `mypy --strict budget_app` 으로 하며 19개 모듈 오류 0건입니다(실행에는 불필요, 개발용 설치).

- 예시 코드: [budget_app/repository.py#L16-L45](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/repository.py#L15-L45), [budget_app/models.py#L66-L80](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/models.py#L66-L80), 제네릭 `ask`: [budget_app/prompts.py#L14](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/prompts.py#L14)
- 타입 검사 실행법: [README.md §8](https://github.com/newids/codyssey-b2-1/blob/main/README.md?plain=1#L287)
- 답변: [docs/03-evaluation-answers.md Q5](https://github.com/newids/codyssey-b2-1/blob/main/docs/03-evaluation-answers.md?plain=1#L133), 개념: [docs/01-mission-guide.md §5.3](https://github.com/newids/codyssey-b2-1/blob/main/docs/01-mission-guide.md?plain=1#L194)

---

## 항목 4 — 설계 판단

### 4-1. JSONL과 CSV 중 선택한 저장 포맷의 장단점을 비교하고, "왜" 그 포맷을 택했는지 근거를 말할 수 있는가?

**충족.** JSONL 은 태그 같은 목록 값과 숫자/문자열 타입을 그대로 담고 한 줄이 한 레코드라 스트리밍·덧붙이기가 쉽지만 엑셀로 열기 불편합니다. CSV 는 그 반대입니다.
그래서 내부 저장은 JSONL, 사람과 주고받는 용도는 import/export 의 CSV 로 역할을 나눴습니다.

- 비교표와 근거: [docs/03-evaluation-answers.md Q6](https://github.com/newids/codyssey-b2-1/blob/main/docs/03-evaluation-answers.md?plain=1#L183), 결정 기록: [docs/01-mission-guide.md §2.2](https://github.com/newids/codyssey-b2-1/blob/main/docs/01-mission-guide.md?plain=1#L36)
- 저장 형식 예시: [README.md §4](https://github.com/newids/codyssey-b2-1/blob/main/README.md?plain=1#L125)

### 4-2. 거래가 10만 건으로 늘어난다면, 현재 구조에서 병목이 어디이며 "어떻게" 개선할지 설명할 수 있는가?

**충족(이번에 보강).** 메모리는 스트리밍으로 일정하지만 시간이 문제입니다. 조회마다 전체 파일을 읽고 JSON 을 해석하며, `update`/`delete` 는 파일 전체를 다시 쓰므로 10만 건이면 명령당 1~2초입니다.
개선은 월별 파일 분할 → 역순 읽기로 `list` 조기 종료 → id 오프셋 인덱스 → `sqlite3` 저장소 교체 순서이며, 서비스가 저장소 인터페이스만 쓰므로 저장소 계층만 바꾸면 됩니다.
예상 효과(추정)는 월별 분할만으로 월 단위 명령이 약 1/24(0.07초), 역순 읽기로 `list` 가 수 ms, SQLite 로 조회·수정 모두 수 ms 입니다.

- 답변: [docs/03-evaluation-answers.md Q15](https://github.com/newids/codyssey-b2-1/blob/main/docs/03-evaluation-answers.md?plain=1#L265)
- 실측 근거(30만 건): [docs/02-result-report.md §6](https://github.com/newids/codyssey-b2-1/blob/main/docs/02-result-report.md?plain=1#L287)
- 병목 지점 코드: 전체 스캔 [budget_app/repository.py#L23-L28](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/repository.py#L28-L33), 전체 재작성 [budget_app/repository.py#L41-L61](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/repository.py#L46-L66)

### 4-3. import CSV에 일부 깨진 행이 섞이면, "어떻게" 처리해 사용자 신뢰를 지킬지 (부분 성공/롤백/리포트) 설명할 수 있는가?

**충족(이번에 보강).** 기본은 **부분 성공**: 올바른 행만 등록하고 `imported=N, skipped=M` 과 건너뛴 행의 번호·사유를 리포트합니다. `--strict` 를 주면 **롤백**: 잘못된 행이 하나라도 있으면 아무것도 등록하지 않고 종료 코드 1 로 끝납니다.
어느 방식이든 모든 행을 검증한 뒤에 한 번만 쓰므로 절반만 들어가는 일이 없고, 헤더가 틀리면 읽기 전에 중단합니다.
같은 CSV 재입력의 중복은 아직 막지 않으며, `--skip-duplicates`(날짜·타입·카테고리·금액·메모 일치 시 건너뜀) 옵션을 다음 단계로 설계해 두었습니다.

- 구현: [budget_app/csv_io.py#L31-L62](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/csv_io.py#L31-L62), 리포트 출력: [budget_app/commands.py#L154-L162](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/commands.py#L162-L170)
- 테스트: [test_import_skips_invalid_rows_with_reasons](https://github.com/newids/codyssey-b2-1/blob/main/tests/test_services.py#L231), [test_strict_import_registers_nothing_when_any_row_is_invalid](https://github.com/newids/codyssey-b2-1/blob/main/tests/test_services.py#L247), [test_strict_import_exits_with_error_and_writes_nothing](https://github.com/newids/codyssey-b2-1/blob/main/tests/test_cli.py#L205)
- 답변: [docs/03-evaluation-answers.md Q16](https://github.com/newids/codyssey-b2-1/blob/main/docs/03-evaluation-answers.md?plain=1#L284), 사용법: [README.md §5](https://github.com/newids/codyssey-b2-1/blob/main/README.md?plain=1#L161)

---

## AI 사전평가 보완 제안 반영 (2026-10-17)

사전평가는 16개 항목 모두 PASS 였고, 항목마다 "보완" 제안이 하나씩 있었습니다. 전부 반영했으며 코드가 바뀐 것은 #3, #5, #11, #13 네 개입니다(테스트 97 → 101개, `mypy --strict` 0건).

| # | 제안 | 조치 | 위치 |
| --- | --- | --- | --- |
| 1 | 핵심 명령의 실패/경계 E2E 사례를 docs 에 추가 | 22개 경계·실패 사례를 명령·입력·결과·종료 코드·테스트 이름으로 표로 정리 | [02-result-report.md §3.10](https://github.com/newids/codyssey-b2-1/blob/main/docs/02-result-report.md?plain=1#L236) |
| 2 | 백업 → 복원 절차 추가 | `backup` 뒤 `cp data/backups/<시각>/*.jsonl data/` 로 되돌리는 예시와 주의점(5개 파일 함께, 실행 중 아님) | [README.md §4 백업과 복구](https://github.com/newids/codyssey-b2-1/blob/main/README.md?plain=1#L145) |
| 3 | 카테고리 대체 중 실패 시 롤백 보증 설명 | 점검 중 실제 문제 발견: 카테고리를 지운 **뒤에** 규칙을 옮겨 중간 실패 시 규칙이 지워진 카테고리를 가리켰음. 규칙 → 거래 → 카테고리 순서로 고치고 중단 테스트 추가, 보증 범위를 문서화 | [recurring.py#L62-L86](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/recurring.py#L62-L87), [테스트](https://github.com/newids/codyssey-b2-1/blob/main/tests/test_services.py#L381), [03 Q12](https://github.com/newids/codyssey-b2-1/blob/main/docs/03-evaluation-answers.md?plain=1#L254) |
| 4 | 예산 경고 임계값 변경 방법 안내 | `config.BUDGET_WARNING_RATE` 위치와 "옵션으로 두지 않은 이유"를 README 에 명시, 상수에 주석 | [README.md §3](https://github.com/newids/codyssey-b2-1/blob/main/README.md?plain=1#L125), [config.py#L11](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/config.py#L11) |
| 5 | 대용량 CSV 성능·중단 테스트 추가 | 1만 행 import(약 1초, 상한 10초 검증)와 "2행 쓴 뒤 디스크 가득 참" 시나리오(파일 읽기 가능, id 재사용 없음, 재실행 정상) 테스트 | [대용량](https://github.com/newids/codyssey-b2-1/blob/main/tests/test_services.py#L302), [중단](https://github.com/newids/codyssey-b2-1/blob/main/tests/test_services.py#L317) |
| 6 | 내부 오류의 구체적 힌트 보강 | 자주 보는 오류 10가지의 메시지·원인·해결 표(권한, 디스크 공간, 깨진 줄, 코드 2/3 포함) | [README.md §6 자주 보는 오류와 해결](https://github.com/newids/codyssey-b2-1/blob/main/README.md?plain=1#L217) |
| 7 | 종료 코드 확인 셸 예시 | `; echo "exit=$?"` 와 `&& ... \|\| ...` 예시 | [README.md §6](https://github.com/newids/codyssey-b2-1/blob/main/README.md?plain=1#L203) |
| 8 | 모듈 의존 다이어그램 | 두 줄 텍스트 다이어그램(`cli → commands → services → repository → storage`) 추가 | [README.md §7](https://github.com/newids/codyssey-b2-1/blob/main/README.md?plain=1#L280) |
| 9 | 주요 클래스의 책임 한 문장 | 9개 클래스에 docstring 추가, 답변서에 클래스별 책임표와 일련번호 책임 분리(보관/예약/무관) 설명 | [03 Q2 클래스별 책임](https://github.com/newids/codyssey-b2-1/blob/main/docs/03-evaluation-answers.md?plain=1#L54), [services.py#L26](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/services.py#L26), [repository.py#L18](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/repository.py#L18) |
| 10 | 권한 유지 정책 한 줄 | 원본 권한 상속, 임시 파일은 같은 폴더, 폴더 쓰기 권한만 필요함을 README 에 명시 | [README.md §4](https://github.com/newids/codyssey-b2-1/blob/main/README.md?plain=1#L143) |
| 11 | `search --limit` 미지정 시 경고/권장 | 결과가 1,000건을 넘으면 표준 오류에 `--limit` 권장 안내, 도움말 문구 보강, 테스트 추가 | [commands.py#L58-L82](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/commands.py#L58-L83), [테스트](https://github.com/newids/codyssey-b2-1/blob/main/tests/test_cli.py#L327) |
| 12 | `--verbose` 로그 예시 | 실제 출력 예시와 어느 데코레이터가 어떤 줄을 남기는지, 로그 수준 설명 | [README.md §6 실행 로그](https://github.com/newids/codyssey-b2-1/blob/main/README.md?plain=1#L232) |
| 13 | 타입 검사 실행법 | `mypy --strict budget_app` 안내. 실행해 보니 6곳 지적 → 모두 수정해 0건 | [README.md §8](https://github.com/newids/codyssey-b2-1/blob/main/README.md?plain=1#L287), [cli.py#L17-L20](https://github.com/newids/codyssey-b2-1/blob/main/budget_app/cli.py#L17-L20) |
| 14 | JSONL 단점(엑셀 친화성) 명시 | 비교표 아래에 JSONL 단점 3가지와 보완 수단(export CSV, 줄 번호 오류, backup) 추가 | [03 Q6](https://github.com/newids/codyssey-b2-1/blob/main/docs/03-evaluation-answers.md?plain=1#L209) |
| 15 | 개선안별 예상 효과 수치 | 실측(6만 건/초) 기반 추정표: 월별 분할 1/24, 역순 읽기 수 ms, SQLite 수 ms, 구현 비용 | [03 Q15 예상 효과](https://github.com/newids/codyssey-b2-1/blob/main/docs/03-evaluation-answers.md?plain=1#L307) |
| 16 | import 중복 감지 옵션 향후 방안 | `--skip-duplicates` 설계(기준 키, 동작, 메모리, 기본값을 끄는 이유) 문서화 | [03 Q16 향후 보완](https://github.com/newids/codyssey-b2-1/blob/main/docs/03-evaluation-answers.md?plain=1#L338), [README.md §6.1](https://github.com/newids/codyssey-b2-1/blob/main/README.md?plain=1#L250) |

설계 규칙으로도 남겼습니다: [01-mission-guide.md §3.3 규칙 7](https://github.com/newids/codyssey-b2-1/blob/main/docs/01-mission-guide.md?plain=1#L95).
