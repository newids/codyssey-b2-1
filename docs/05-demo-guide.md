# 시연 가이드 — B2-1 나만의 용돈 기입장

평가자 앞에서 프로그램을 10분 안에 보여 주기 위한 대본입니다.
단계마다 **실행할 명령**, **기대 출력**, **말할 포인트**를 적었습니다. 출력은 이 저장소의 코드를 빈 폴더에서 실제로 실행한 결과입니다(2026-10-28, Python 3.13.5).

| 단계 | 보여 주는 것 | 평가항목 |
| --- | --- | --- |
| 0 | 준비: 빈 데이터 폴더, 테스트 1회 | 1-2, 테스트 |
| 1 | 첫 실행 → 파일 5개 자동 생성, 기본 카테고리 | 1-2 |
| 2 | `add` 대화형 입력, 잘못된 값 재입력 | 1-1, 1-6 |
| 3 | `list`, `list --id`, `search` 조건 조합, `search --id` | 1-1, 3-1 |
| 4 | `budget set` → `summary` 예산 초과 경고 | 1-4 |
| 5 | `update`, `delete`, 없는 id 오류와 종료 코드 | 1-1, 1-7, 2-3 |
| 6 | `category add/remove`, 사용 중인 카테고리 대체 | 1-3 |
| 7 | `export` → CSV 확인 → `import --skip-duplicates` | 1-5, 4-3 |
| 8 | 보너스: `recurring`, `backup` | 보너스 |
| 9 | 재실행 후 데이터 유지, 저장 파일, `--verbose` 로그 | 1-2, 3-2 |

시간이 부족하면 8단계를 빼고, 질문이 들어오면 [04-evaluation-checklist.md](04-evaluation-checklist.md) 의 해당 항목으로 넘어갑니다.

---

## 0. 준비 (시연 전)

프로젝트 루트에서 실행합니다. 기존 `./data` 를 건드리지 않도록 시연용 폴더를 따로 씁니다.

```bash
cd codyssey-b2-1
rm -rf ./demo-data                       # 이전 리허설 데이터 삭제
alias b='python -m budget_app --data-dir ./demo-data'
python -m unittest discover -s tests -t . # 115 tests OK 를 확인하고 시작
```

- 터미널 폰트는 한글 표가 깨지지 않게 고정폭으로, 창 너비는 100칸 이상으로 맞춥니다.
- 아래 명령은 모두 `b <command>` 로 적었습니다. alias 없이 하려면 `python -m budget_app --data-dir ./demo-data <command>` 입니다.

> 리허설은 맨 아래 **부록 A** 의 스크립트 한 번으로 끝까지 돌려볼 수 있습니다.

## 1. 첫 실행 — 파일이 스스로 만들어진다 (30초)

```console
$ b category list
[안내] 저장 파일 5개를 새로 만들었습니다: ./demo-data
[안내] 기본 카테고리를 등록했습니다: food, transport, rent, salary, shopping, etc
- food
- transport
- rent
- salary
- shopping
- etc
```

말할 포인트

- 설치할 패키지가 없고 표준 라이브러리만 씁니다.
- 거래·카테고리·예산·반복 규칙·메타(일련번호) 파일 5개를 JSONL 로 저장합니다. 파일 3개 이상이라는 요구를 넘깁니다.
- `[안내]` 는 표준 오류로 나가므로 표준 출력만 파이프로 넘겨도 섞이지 않습니다.

## 2. 거래 추가 — 잘못된 값은 그 자리에서 다시 묻는다 (1분 30초)

정상 입력 다섯 건을 넣습니다. 이 다섯 건이 이후 단계의 재료입니다.

```console
$ b add
날짜(YYYY-MM-DD): 2024-01-05
타입(income/expense): expense
카테고리: rent
금액(양수): 150000
메모(선택): 월세
태그(쉼표로 구분, 없으면 엔터):
[저장 완료] id=TX-000001
```

같은 방식으로 네 건 더:

| 날짜 | 타입 | 카테고리 | 금액 | 메모 | 태그 | id |
| --- | --- | --- | --- | --- | --- | --- |
| 2024-01-12 | expense | transport | 20000 | | | TX-000002 |
| 2024-01-14 | income | salary | 3000000 | | | TX-000003 |
| 2024-01-15 | expense | food | 15000 | 점심 | meal | TX-000004 |
| 2024-01-20 | expense | food | 30000 | 저녁 | meal,friends | TX-000005 |

여섯 번째는 일부러 틀리게 넣어 재입력을 보여 줍니다.

```console
$ b add
날짜(YYYY-MM-DD): 2024-13-40
[오류] 날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).
[힌트] 예: 2024-01-15
날짜(YYYY-MM-DD): 2024-01-22
타입(income/expense): expense
카테고리: hobby
[오류] 등록되지 않은 카테고리입니다: hobby
[힌트] 사용 가능: food, transport, rent, salary, shopping, etc / 새로 만들려면 category add 를 실행하세요.
카테고리: shopping
금액(양수): 0
[오류] 금액은 0보다 큰 정수여야 합니다 (최대 15자리).
[힌트] 예: 15000 (기호나 소수점 없이 입력)
금액(양수): 42000
메모(선택): 운동화
태그(쉼표로 구분, 없으면 엔터):
[저장 완료] id=TX-000006
```

말할 포인트

- 모든 오류는 `[오류] 원인` + `[힌트] 해결` 두 줄이고 스택트레이스가 없습니다.
- 검증 함수(`validators.py`)는 대화형 입력, 옵션, CSV, 저장 파일 읽기가 모두 같은 것을 씁니다.
- id 는 "거래 수 + 1" 이 아니라 `meta.jsonl` 의 일련번호를 먼저 예약하고 씁니다. 삭제돼도 번호를 재사용하지 않습니다.

## 3. 목록과 검색 — 스트리밍으로 읽는다 (1분 30초)

```console
$ b list --limit 3
ID        | 날짜       | 타입    | 카테고리 |  금액 | 메모   | 태그
----------+------------+---------+----------+-------+--------+-------------
TX-000006 | 2024-01-22 | expense | shopping | 42000 | 운동화 |
TX-000005 | 2024-01-20 | expense | food     | 30000 | 저녁   | meal,friends
TX-000004 | 2024-01-15 | expense | food     | 15000 | 점심   | meal

$ b list --id 4
ID        | 날짜       | 타입    | 카테고리 |  금액 | 메모 | 태그
----------+------------+---------+----------+-------+------+-----
TX-000004 | 2024-01-15 | expense | food     | 15000 | 점심 | meal

$ b search --from 2024-01-01 --to 2024-01-31 --category food --tag meal
ID        | 날짜       | 타입    | 카테고리 |  금액 | 메모 | 태그
----------+------------+---------+----------+-------+------+-------------
TX-000005 | 2024-01-20 | expense | food     | 30000 | 저녁 | meal,friends
TX-000004 | 2024-01-15 | expense | food     | 15000 | 점심 | meal
(총 2건)

$ b search --type expense --min-amount 50000
ID        | 날짜       | 타입    | 카테고리 |   금액 | 메모 | 태그
----------+------------+---------+----------+--------+------+-----
TX-000001 | 2024-01-05 | expense | rent     | 150000 | 월세 |
(총 1건)

$ b search --id 4 --type income
조건에 맞는 거래가 없습니다.
```

말할 포인트

- 목록과 검색은 파일을 한 줄씩 읽는 제너레이터(`iter_all`) 위에서 동작합니다. `list --limit N` 은 `heapq.nlargest` 로 N 건만 메모리에 둡니다.
- `--id` 는 `TX-000004` 와 `4` 를 같은 id 로 받습니다. `list --id` 는 한 건만 보여 주고, `search --id` 는 다른 조건과 겹쳐서 쓸 수 있습니다. id 는 유일하므로 첫 일치에서 읽기를 멈춥니다.
- 한글은 2칸으로 세어 표가 어긋나지 않습니다(`formatter.display_width`).

## 4. 예산과 월별 요약 — 초과 경고 (1분)

```console
$ b budget set --month 2024-01 --amount 250000
[저장 완료] 2024-01 예산 250000원

$ b summary --month 2024-01 --top 3
[2024-01 요약] 거래 6건
총 수입: 3000000원
총 지출: 257000원
잔액: 2743000원
예산: 250000원 (사용률 102.8%)
[경고] 예산을 7000원 초과했습니다!
지출 TOP 3
1) rent     150000원
2) food      45000원
3) shopping  42000원
```

말할 포인트

- 요약은 파일을 한 번만 훑으며 합계와 카테고리별 지출을 동시에 모읍니다.
- 사용률 80% 이상이면 `[주의]`, 초과하면 `[경고]` 입니다. 예산을 지우면(`budget remove`) 줄 자체가 사라집니다.

## 5. 수정·삭제 — 없는 id 와 종료 코드 (1분)

```console
$ b update --id 4 --amount 18000 --memo "점심(수정)"
[수정 완료] id=TX-000004
ID        | 날짜       | 타입    | 카테고리 |  금액 | 메모       | 태그
----------+------------+---------+----------+-------+------------+-----
TX-000004 | 2024-01-15 | expense | food     | 18000 | 점심(수정) | meal

$ b delete --id TX-000006
[삭제 완료] id=TX-000006 (2024-01-22 shopping 42000원)

$ b delete --id TX-000006; echo "exit=$?"
[오류] 없는 데이터입니다: id=TX-000006
[힌트] list 또는 search 명령으로 id 를 확인하세요. (예: TX-000012)
exit=1
```

말할 포인트

- `update` 는 옵션 방식으로 고정했습니다. 지정한 항목만 바뀝니다.
- 수정·삭제는 임시 파일에 전부 쓴 뒤 `os.replace` 로 한 번에 바꿉니다. 도중에 죽어도 원본은 그대로입니다(2-3).
- 종료 코드: 성공 0, 데이터·입력 오류 1, 명령 형식 오류 2, 예기치 못한 오류 3. 셸 스크립트에서 분기할 수 있습니다.

## 6. 카테고리 — 사용 중이면 옮기고 지운다 (1분)

```console
$ b category add --name hobby
[저장 완료] category=hobby
$ b category remove --name hobby
[삭제 완료] category=hobby

$ b category remove --name transport
[오류] 'transport' 카테고리를 사용하는 거래가 1건 있어 삭제할 수 없습니다.
[힌트] category remove --name transport --replace-with <대체 카테고리> 로 거래를 옮긴 뒤 삭제할 수 있습니다.

$ b category remove --name transport --replace-with etc
[안내] 거래 1건을 'etc' 카테고리로 옮겼습니다.
[삭제 완료] category=transport
```

말할 포인트

- 거래를 먼저 옮기고 카테고리를 마지막에 지우므로, 중간에 멈춰도 지워진 카테고리를 가리키는 거래는 생기지 않습니다.
- 실패하면 `완료: ... / 남음: ...` 힌트로 어디까지 됐는지 알려 주고, 같은 명령을 다시 실행하면 남은 단계만 수행합니다.

## 7. 내보내기와 가져오기 (1분 30초)

```console
$ b export --out ./demo-data/2024-01.csv --month 2024-01
[완료] ./demo-data/2024-01.csv (5 records)

$ cat ./demo-data/2024-01.csv
date,type,category,amount,memo,tags
2024-01-05,expense,rent,150000,월세,
2024-01-12,expense,etc,20000,,
2024-01-14,income,salary,3000000,,
2024-01-15,expense,food,18000,점심(수정),meal
2024-01-20,expense,food,30000,저녁,"meal,friends"

$ b import --from samples/import_sample.csv --skip-duplicates
[완료] imported=5, skipped=2
  - 건너뜀 3행: 이미 있는 거래 (2024-01-05 rent 150000원)
  - 건너뜀 5행: 등록되지 않은 카테고리입니다: transport

$ b import --from samples/import_sample.csv --skip-duplicates
[완료] imported=0, skipped=7
  - 건너뜀 2행: 이미 있는 거래 (2024-01-02 salary 3000000원)
  ...
```

말할 포인트

- CSV 스키마는 `date,type,category,amount,memo,tags` 고정, UTF-8 입니다. 엑셀의 BOM 도 받습니다.
- 깨진 행은 기본으로 건너뛰고 행 번호와 사유를 보고합니다(부분 성공). `--strict` 를 주면 한 행이라도 틀리면 아무것도 등록하지 않습니다(롤백). `--skip-duplicates` 로 같은 파일을 두 번 넣어도 안전합니다.
- 1만 행 CSV 도 한 번의 덧붙이기로 등록하며 테스트에 시간 상한이 있습니다.

## 8. 보너스 — 반복 내역과 백업 (1분, 생략 가능)

```console
$ b recurring add --day 25 --type income --category salary --amount 3000000 --memo 월급
[저장 완료] id=RC-0001 (매월 25일 salary 3000000원)
$ b recurring apply --month 2024-02
[완료] 2024-02 반복 내역: created=1, already_applied=0, failed=0
  - 생성 TX-000012 2024-02-25 salary 3000000원
$ b recurring apply --month 2024-02
[완료] 2024-02 반복 내역: created=0, already_applied=1, failed=0

$ b backup
[백업 완료] ./demo-data/backups/20261028-161808 (5 files)
- transactions.jsonl
- categories.jsonl
- budgets.jsonl
- recurring.jsonl
- meta.jsonl
```

말할 포인트

- 생성된 거래에 `recurring:RC-0001` 태그를 붙여 같은 달에 두 번 만들지 않습니다. 31일 규칙은 짧은 달에서 말일로 조정됩니다.
- 백업은 타임스탬프 폴더로 복사합니다. 복구는 파일을 되돌려 놓고 `list --limit 3` 로 확인하면 됩니다.

## 9. 마무리 — 데이터가 남아 있고, 로그가 보인다 (30초)

새 터미널(또는 다시 실행)에서:

```console
$ b list --limit 2
ID        | 날짜       | 타입    | 카테고리 |    금액 | 메모      | 태그
----------+------------+---------+----------+---------+-----------+------------------
TX-000012 | 2024-02-25 | income  | salary   | 3000000 | 월급      | recurring:RC-0001
TX-000011 | 2024-01-25 | expense | shopping |   45000 | 겨울 장갑 |

$ head -2 ./demo-data/transactions.jsonl
{"id": "TX-000001", "type": "expense", "date": "2024-01-05", "amount": 150000, "category": "rent", "memo": "월세", "tags": []}
{"id": "TX-000002", "type": "expense", "date": "2024-01-12", "amount": 20000, "category": "etc", "memo": "", "tags": []}

$ b search --tag meal --verbose
[log] 시작: BudgetService.search
[log] 소요 시간: BudgetService.search 0.18ms
[log] 완료: BudgetService.search
...
(총 5건)

$ b list --lim 3; echo "exit=$?"
[오류] 명령 형식이 올바르지 않습니다: unrecognized arguments: --lim 3
[힌트] 사용법은 'python -m budget_app --help' 로 확인하세요.
exit=2
```

말할 포인트

- JSONL 은 한 줄이 거래 하나라서 덧붙이기(`add`)가 O(1) 이고, 손으로 고쳐도 다른 줄이 깨지지 않습니다.
- `--verbose` 의 `[log]` 줄은 `@log_call`, `@timed` 데코레이터가 찍습니다. 서비스 코드에는 로그·시간 측정 코드가 없습니다(3-2).
- `[로그]` 와 `[안내]` 는 표준 오류, 표는 표준 출력입니다.

---

## 예상 질문 대응

| 질문 | 한 줄 답 | 자세히 |
| --- | --- | --- |
| 왜 CSV 가 아니라 JSONL 인가 | 한 줄 하나의 레코드라 덧붙이기와 부분 손상 복구가 쉽고, 메모의 쉼표·따옴표 문제가 없음 | [03 Q6](03-evaluation-answers.md#q6-jsonl과-csv-중-왜-jsonl인가) |
| 수정 중 죽으면 | 임시 파일에 쓰고 `os.replace` 로 교체하므로 원본 또는 완성본 둘 중 하나만 남음 | [03 Q7](03-evaluation-answers.md#q7-updatedelete-도중-프로그램이-죽으면-데이터는-어떻게-되는가) |
| 10만 건이면 | 수정·삭제·조회가 파일 크기에 비례. 인덱스 파일 또는 SQLite 로 전환 | [03 Q15](03-evaluation-answers.md#q15-거래가-10만-건으로-늘어나면-병목은-어디이고-어떻게-개선하는가) |
| 제너레이터가 왜 유리한가 | `list --limit 10` 이 10만 건 파일에서도 10건 메모리만 씀 | [03 Q3](03-evaluation-answers.md#q3-yield-기반-제너레이터로-스트리밍-처리하는-이유와-동작-방식은) |
| 테스트는 | 115개, 임시 폴더에서 실제 진입점을 호출하는 E2E 포함, `mypy --strict` 0건 | [02 §5](02-result-report.md#5-테스트-결과) |

## 시연 전 체크리스트

- [ ] `python --version` 이 3.10 이상
- [ ] `rm -rf ./demo-data` 로 깨끗한 상태
- [ ] `python -m unittest discover -s tests -t .` 통과
- [ ] 터미널 너비 100칸 이상, 고정폭 폰트
- [ ] `samples/import_sample.csv` 존재
- [ ] 이 문서와 [04-evaluation-checklist.md](04-evaluation-checklist.md) 를 다른 창에 열어 둠

## 부록 A. 리허설 스크립트

대화형 입력까지 파이프로 넣어 1~9단계를 한 번에 돌립니다. 프로젝트 루트에서 실행합니다.

```bash
#!/usr/bin/env bash
set -u
D=./demo-data
rm -rf "$D"
b() { echo; echo "\$ budget_app $*"; python -m budget_app --data-dir "$D" "$@"; echo "exit=$?"; }

b category list
printf '2024-01-05\nexpense\nrent\n150000\n월세\n\n'            | b add
printf '2024-01-12\nexpense\ntransport\n20000\n\n\n'           | b add
printf '2024-01-14\nincome\nsalary\n3000000\n\n\n'             | b add
printf '2024-01-15\nexpense\nfood\n15000\n점심\nmeal\n'         | b add
printf '2024-01-20\nexpense\nfood\n30000\n저녁\nmeal,friends\n' | b add
printf '2024-13-40\n2024-01-22\nexpense\nhobby\nshopping\n0\n42000\n운동화\n\n' | b add

b list --limit 3
b list --id 4
b search --from 2024-01-01 --to 2024-01-31 --category food --tag meal
b search --type expense --min-amount 50000
b search --id 4 --type income

b budget set --month 2024-01 --amount 250000
b summary --month 2024-01 --top 3

b update --id 4 --amount 18000 --memo "점심(수정)"
b delete --id TX-000006
b delete --id TX-000006

b category add --name hobby
b category remove --name hobby
b category remove --name transport
b category remove --name transport --replace-with etc

b export --out "$D/2024-01.csv" --month 2024-01
cat "$D/2024-01.csv"
b import --from samples/import_sample.csv --skip-duplicates
b import --from samples/import_sample.csv --skip-duplicates

b recurring add --day 25 --type income --category salary --amount 3000000 --memo 월급
b recurring apply --month 2024-02
b recurring apply --month 2024-02
b backup

b list --limit 2
head -2 "$D/transactions.jsonl"
b search --tag meal --verbose
b list --lim 3
```
