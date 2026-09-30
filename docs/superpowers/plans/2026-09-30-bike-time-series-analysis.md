# 서울시 따릉이 시계열 분석 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 2023~2024년 서울시 따릉이 일별 이용량을 정제·분석하고, 날씨 보조 데이터와 함께 재현 가능한 Python 분석 코드와 Markdown 리포트를 만든다.

**Architecture:** `src/bike_analysis.py`가 데이터 정제, 일별 집계, 특징 생성, 통계 요약, 시각화를 담당하고 `analysis.py`가 CLI 파이프라인을 조립한다. 원본 데이터는 `data/raw/`에서 읽고, 정제된 일별 데이터는 `data/processed_daily_rentals.csv`에 저장하며, 차트는 `images/`에 생성한다. 실제 수치는 파이프라인 실행 결과를 확인한 뒤 `REPORT.md`에 반영한다.

**Tech Stack:** Python 3.10+, pandas, NumPy, Matplotlib, Seaborn, statsmodels, pytest

**Spec:** [docs/superpowers/specs/2026-09-30-bike-time-series-analysis-design.md](../specs/2026-09-30-bike-time-series-analysis-design.md)

## Global Constraints

- 분석 기간은 `2023-01-01 ~ 2024-12-31`이다.
- 핵심 분석 단위는 날짜 1개당 1개 행인 서울시 전체 따릉이 이용량이다.
- 기상 보조 데이터는 서울 중심 좌표 인근 격자의 일평균기온과 일강수량을 사용한다.
- 원본에 기록이 없는 날짜를 자동으로 이용량 0으로 채우지 않고 누락 여부를 표시한다.
- 통계적 이상치는 기본적으로 삭제하지 않고 표시·검토한다.
- 이동평균, 계절성 집계, 변화율·변동성 중 2가지 이상을 적용한다.
- PNG 시각화 3개 이상과 수치 근거가 있는 인사이트 3개 이상을 만든다.
- 날씨와 이용량의 관계는 인과관계가 아닌 관찰된 연관성과 가설로 표현한다.
- README에 Python 버전, 설치·실행 방법, 데이터 출처·수집 방법·이용조건을 기록한다.
- REPORT.md에 관찰과 해석을 구분하고 AI 사용 로그를 포함한다.

## Review Focus

- 원본 CSV의 한글 컬럼명·인코딩·컬럼명 변형을 만나도 `대여일자`와 `이용건수`를 정확히 찾고 실패를 설명해야 한다. → Task 2의 컬럼 정규화 테스트.
- 원본에 기록이 없는 날짜와 실제 이용량 0인 날짜를 혼동하지 않아야 한다. → Task 2의 캘린더 누락 플래그 테스트.
- 동일한 원본 행이 중복되어도 이용건수를 이중 집계하지 않아야 한다. → Task 2의 exact duplicate 제거 테스트.
- 극단적인 이용량이 정상적인 행사·날씨 영향일 수 있으므로 이상치를 자동 삭제하지 않아야 한다. → Task 3의 이상치 flag 보존 테스트.
- 날씨 날짜가 일부 빠지거나 분석 기간과 다를 때 이용량 행을 잃지 않고 결측을 표시해야 한다. → Task 3의 left join·결측 테스트.

### Task 1: 프로젝트 실행 기반과 테스트 골격 만들기

**Files:**
- Create: `.gitignore`
- Create: `requirements.txt`
- Create: `src/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_bike_analysis.py`
- Create: `data/raw/.gitkeep`
- Create: `images/.gitkeep`

**Interfaces:**
- Produces: 테스트가 `src.bike_analysis`를 import할 수 있는 패키지 구조와 재현 가능한 의존성 목록.

- [ ] **Step 1: 분석 패키지 import를 검증하는 failing test 작성**

  `tests/test_bike_analysis.py`에 `test_analysis_module_exports_public_api`를 만들고, 이후 Task 2에서 정의할 `aggregate_bike_files`, `complete_calendar`, `add_features` 심볼을 import하도록 작성한다. 현재는 모듈이 없으므로 실패해야 한다.

- [ ] **Step 2: 테스트가 예상대로 실패하는지 확인**

  Run: `pytest tests/test_bike_analysis.py::test_analysis_module_exports_public_api -q`

  Expected: `ModuleNotFoundError` 또는 export 심볼 누락으로 FAIL.

- [ ] **Step 3: 기본 프로젝트 파일과 패키지 초기화 파일 작성**

  `requirements.txt`에 Python 3.10 이상에서 사용할 `pandas`, `numpy`, `matplotlib`, `seaborn`, `statsmodels`, `pytest`를 기록한다. `.gitignore`에는 가상환경, 캐시, 임시 파일을 제외하고 `data/raw/`의 대용량 원본은 기본 제외한다. `src/__init__.py`, 테스트·출력 폴더의 `.gitkeep`을 추가한다.

- [ ] **Step 4: 최소 import를 구현해 테스트 통과시키기**

  `src/bike_analysis.py`를 만들고 Task 2~3에서 구현할 공개 함수의 placeholder signature를 정의한다. 함수 본문은 `NotImplementedError`로 두지 말고, 테스트가 import만 확인할 수 있도록 빈 DataFrame을 반환하는 임시 구현을 사용한다. 다음 Task에서 실제 동작으로 교체한다.

- [ ] **Step 5: 테스트 재실행**

  Run: `pytest tests/test_bike_analysis.py::test_analysis_module_exports_public_api -q`

  Expected: PASS.

- [ ] **Step 6: 커밋**

  ```bash
  git add .gitignore requirements.txt src tests data/raw/.gitkeep images/.gitkeep
  git commit -m "chore: scaffold bike time-series analysis project"
  ```

### Task 2: 따릉이 원본 정규화·일별 집계·누락 캘린더 구현

**Files:**
- Modify: `src/bike_analysis.py`
- Modify: `tests/test_bike_analysis.py`

**Interfaces:**
- `normalize_bike_columns(frame: pandas.DataFrame) -> pandas.DataFrame`: 한글 원본 컬럼을 내부 이름 `date`, `rental_count`로 정규화한다.
- `aggregate_bike_files(paths: Sequence[pathlib.Path], start: str, end: str) -> tuple[pandas.DataFrame, dict[str, int]]`: 원본 파일을 읽어 `date`, `rental_count` 일별 집계와 정제 감사정보를 반환한다.
- `complete_calendar(daily: pandas.DataFrame, start: str, end: str) -> pandas.DataFrame`: 전체 날짜를 생성하고 `record_missing` 플래그를 추가한다.

- [ ] **Step 1: 컬럼 정규화와 집계 실패 케이스의 failing tests 작성**

  다음 테스트를 `tests/test_bike_analysis.py`에 추가한다.

  - `test_normalize_bike_columns_maps_korean_names`: `대여일자`, `이용건수`가 각각 `date`, `rental_count`로 바뀌는지 확인.
  - `test_normalize_bike_columns_rejects_missing_required_column`: 필수 컬럼이 없을 때 `ValueError`가 발생하고 컬럼명이 오류에 포함되는지 확인.
  - `test_aggregate_bike_files_sums_by_date_and_removes_exact_duplicates`: 동일 원본 행을 한 번만 반영하고 같은 날짜의 여러 대여소 이용건수를 합산하는지 확인.
  - `test_complete_calendar_marks_missing_dates_without_zero_fill`: 중간 날짜가 결과에 존재하되 `rental_count`는 결측이고 `record_missing`은 `True`인지 확인.

- [ ] **Step 2: 새 테스트가 실패하는지 확인**

  Run: `pytest tests/test_bike_analysis.py -k "normalize or aggregate or calendar" -q`

  Expected: 구현 전이므로 FAIL.

- [ ] **Step 3: 원본 컬럼 정규화 구현**

  `normalize_bike_columns`에서 컬럼명을 strip하고 `대여일자`·`대여일시` 후보를 `date`, `이용건수` 후보를 `rental_count`로 매핑한다. 필수 컬럼이 없으면 원본 컬럼 목록을 포함한 `ValueError`를 발생시킨다.

- [ ] **Step 4: 파일별 정제·일별 집계 구현**

  `aggregate_bike_files`는 파일을 하나씩 읽어 메모리 사용량을 제한한다. 날짜를 datetime으로 변환하고 분석 기간으로 필터링하며, 숫자 변환 실패·음수·정확히 동일한 중복 행을 감사정보에 기록한다. 유효한 행을 날짜별로 합산하고 여러 파일에서 나온 부분 집계를 다시 날짜별로 합친다. 결과는 오름차순 `date`, `rental_count`로 반환한다.

- [ ] **Step 5: 전체 날짜 캘린더 구현**

  `complete_calendar`는 `pd.date_range(start, end, freq="D")`를 기준으로 left join한다. 원본 기록이 없는 날짜는 `record_missing=True`로 표시하고 임의의 0 대체는 하지 않는다.

- [ ] **Step 6: 테스트 통과 확인**

  Run: `pytest tests/test_bike_analysis.py -k "normalize or aggregate or calendar" -q`

  Expected: PASS.

- [ ] **Step 7: 커밋**

  ```bash
  git add src/bike_analysis.py tests/test_bike_analysis.py
  git commit -m "feat: aggregate bike rentals into daily series"
  ```

### Task 3: 날씨 결합과 시계열 특징·이상치 플래그 구현

**Files:**
- Modify: `src/bike_analysis.py`
- Modify: `tests/test_bike_analysis.py`

**Interfaces:**
- `normalize_weather_columns(frame: pandas.DataFrame) -> pandas.DataFrame`: 기상청 다운로드 파일을 `date`, `mean_temp_c`, `precip_mm`로 정규화한다.
- `merge_weather(daily: pandas.DataFrame, weather: pandas.DataFrame) -> pandas.DataFrame`: 날짜 기준 left join을 수행한다.
- `add_features(frame: pandas.DataFrame) -> pandas.DataFrame`: 이동평균, 변화율, 이동 표준편차, 요일·월·강수 플래그·기온 구간을 추가한다.
- `flag_outliers(frame: pandas.DataFrame, threshold: float = 3.5) -> pandas.DataFrame`: robust z-score 기준으로 `outlier_flag`를 추가하되 행을 제거하지 않는다.

- [ ] **Step 1: 날씨 결합·특징·이상치의 failing tests 작성**

  다음 테스트를 추가한다.

  - `test_merge_weather_keeps_bike_dates_when_weather_is_missing`: 날씨에 없는 날짜도 결과에 남고 날씨 컬럼만 결측인지 확인.
  - `test_add_features_computes_weekly_metrics`: 7일 이동평균, 전일 대비 변화율, 7일 이동 표준편차가 생성되는지 확인.
  - `test_add_features_labels_weekday_month_and_rain`: 요일, 월, `rain_flag`, `temperature_bin` 컬럼이 생성되는지 확인.
  - `test_flag_outliers_marks_but_does_not_drop_extreme_row`: 극단값 행이 결과에 남고 `outlier_flag=True`인지 확인.

- [ ] **Step 2: 테스트 실패 확인**

  Run: `pytest tests/test_bike_analysis.py -k "weather or features or outlier" -q`

  Expected: 구현 전 FAIL.

- [ ] **Step 3: 기상청 컬럼 정규화·left join 구현**

  기상청 export에서 날짜, 평균기온, 강수량의 표기 변형을 허용하고 표준 컬럼으로 변환한다. `merge_weather`는 `how="left"`로 이용량 날짜를 보존하며, 결합 전후 행 수와 날씨 결측 수를 검증 가능한 형태로 유지한다.

- [ ] **Step 4: 시계열 특징 구현**

  `add_features`에서 `rolling_7d`, `pct_change`, `rolling_std_7d`, `weekday`, `weekday_name`, `month`, `rain_flag`, `temperature_bin`을 생성한다. 첫 날짜처럼 계산 불가능한 값은 결측으로 유지한다. 기온 구간 기준은 `<=0`, `0~10`, `10~20`, `20~30`, `>30`도 단위가 명확하게 기록되도록 한다.

- [ ] **Step 5: robust 이상치 flag 구현**

  이용량의 중앙값과 MAD를 이용해 robust z-score를 계산하고 절댓값이 3.5보다 큰 행에 `outlier_flag=True`를 부여한다. MAD가 0인 합성·실제 구간에서는 fallback으로 IQR 기준을 사용하며, 이상치 행을 drop하지 않는다.

- [ ] **Step 6: 테스트 통과 확인**

  Run: `pytest tests/test_bike_analysis.py -k "weather or features or outlier" -q`

  Expected: PASS.

- [ ] **Step 7: 커밋**

  ```bash
  git add src/bike_analysis.py tests/test_bike_analysis.py
  git commit -m "feat: add weather join and time-series features"
  ```

### Task 4: 분석 요약과 시각화 생성기 구현

**Files:**
- Modify: `src/bike_analysis.py`
- Modify: `tests/test_bike_analysis.py`

**Interfaces:**
- `summarize_analysis(frame: pandas.DataFrame) -> dict[str, object]`: 기간, 행 수, 결측·중복·이상치, 월별·요일별·날씨 비교 요약을 반환한다.
- `make_plots(frame: pandas.DataFrame, output_dir: pathlib.Path, include_stl: bool = True) -> list[pathlib.Path]`: PNG 3개 이상을 생성하고 생성 경로를 반환한다.

- [ ] **Step 1: 요약·시각화의 failing tests 작성**

  - `test_summarize_analysis_reports_period_and_point_count`: 시작일·종료일·유효 데이터 수가 요약에 포함되는지 확인.
  - `test_make_plots_creates_required_pngs`: 충분한 합성 데이터로 실행해 `01_daily_trend.png`, `02_month_weekday_heatmap.png`, `03_weather_effect.png`가 생성되는지 확인.
  - `test_make_plots_handles_missing_weather_values`: 날씨 결측이 있어도 주 시계열 차트는 생성되는지 확인.

- [ ] **Step 2: 테스트 실패 확인**

  Run: `pytest tests/test_bike_analysis.py -k "summarize or plots" -q`

  Expected: 구현 전 FAIL.

- [ ] **Step 3: 분석 요약 구현**

  `summarize_analysis`에서 기간, 전체 행 수, `record_missing` 수, 날씨 결측 수, 이상치 수, 월별·요일별 통계, 강수일/비강수일 비교, Spearman 상관계수를 JSON 직렬화 가능한 숫자·문자열로 반환한다.

- [ ] **Step 4: 필수 시각화 구현**

  `matplotlib`의 non-interactive backend에서 다음 PNG를 생성한다.

  - `01_daily_trend.png`: 일별 이용량과 7일 이동평균.
  - `02_month_weekday_heatmap.png`: 월 × 요일 평균 이용량.
  - `03_weather_effect.png`: 강수 여부별 boxplot과 기온 구간별 비교 또는 산점도.

  각 그래프에는 제목, 축 이름, 단위, 데이터 기간, 출처를 포함한다.

- [ ] **Step 5: STL 심화 그래프 구현**

  `statsmodels.tsa.seasonal.STL(period=7)`을 이용해 유효한 일별 이용량이 충분할 때 `04_stl_decomposition.png`를 생성한다. 데이터가 부족하거나 전부 결측이면 명확한 로그를 남기고 선택 그래프만 건너뛴다.

- [ ] **Step 6: 테스트 통과 확인**

  Run: `pytest tests/test_bike_analysis.py -k "summarize or plots" -q`

  Expected: PASS.

- [ ] **Step 7: 커밋**

  ```bash
  git add src/bike_analysis.py tests/test_bike_analysis.py
  git commit -m "feat: generate time-series summaries and charts"
  ```

### Task 5: CLI 파이프라인과 데이터 사용 문서 작성

**Files:**
- Create: `analysis.py`
- Create: `data/README.md`
- Create: `README.md`
- Modify: `tests/test_bike_analysis.py`

**Interfaces:**
- `run_pipeline(bike_dir: pathlib.Path, weather_path: pathlib.Path | None, output_dir: pathlib.Path, start: str, end: str) -> dict[str, object]`: 파일 탐색부터 CSV·PNG 생성까지 수행한다.
- CLI command: `python analysis.py --bike-dir data/raw/bike --weather data/raw/weather_seoul_108.csv --output-dir . --start 2023-01-01 --end 2024-12-31`

- [ ] **Step 1: CLI와 재현성 문서의 failing test 작성**

  `test_run_pipeline_writes_processed_csv_and_three_images`를 작성해 임시 raw CSV와 날씨 CSV를 넣고, `data/processed_daily_rentals.csv`와 PNG 3개 이상이 생성되는지 확인한다. 입력 파일이 없을 때 `FileNotFoundError`가 명확한 경로와 함께 발생하는 테스트도 추가한다.

- [ ] **Step 2: 테스트 실패 확인**

  Run: `pytest tests/test_bike_analysis.py -k "pipeline" -q`

  Expected: `analysis.py` 또는 `run_pipeline` 미구현으로 FAIL.

- [ ] **Step 3: 파이프라인 함수와 CLI 구현**

  `run_pipeline`에서 지정한 기간과 경로를 검증하고, `aggregate_bike_files` → `complete_calendar` → 선택적 `merge_weather` → `add_features` → `flag_outliers` → CSV 저장 → 요약·시각화 순서로 호출한다. `--weather`를 생략하면 따릉이 단일 시계열 fallback으로 실행한다. 완료 시 요약 딕셔너리를 출력한다.

- [ ] **Step 4: 데이터 사용 문서 작성**

  `data/README.md`에 서울시 2023·2024년 상·하반기 파일명, 공식 다운로드 페이지, 기상청 지점 108 자료를 내려받아 저장하는 위치와 날짜, 원본 컬럼, 이용조건 확인 방법을 기록한다. `README.md`에는 Python 3.10+, 가상환경 설치, `pip install -r requirements.txt`, CLI 실행 명령, 생성 파일 위치를 기록한다.

- [ ] **Step 5: 테스트 통과 확인**

  Run: `pytest tests/test_bike_analysis.py -k "pipeline" -q`

  Expected: PASS.

- [ ] **Step 6: 커밋**

  ```bash
  git add analysis.py data/README.md README.md tests/test_bike_analysis.py
  git commit -m "feat: add reproducible analysis pipeline"
  ```

### Task 6: 실제 데이터 수집·실행 결과로 REPORT.md 작성

**Files:**
- Create: `REPORT.md`
- Create or add locally: `data/raw/bike/*.csv`, `data/raw/weather_seoul_open_meteo.csv` when license·용량상 허용되는 경우
- Create: `data/processed_daily_rentals.csv`
- Create: `images/01_daily_trend.png`
- Create: `images/02_month_weekday_heatmap.png`
- Create: `images/03_weather_effect.png`
- Create: `images/04_stl_decomposition.png` when STL succeeds

**Interfaces:**
- Consumes: Task 5 CLI and generated summary/data files.
- Produces: 제출 가능한 Markdown 리포트와 이미지 링크.

- [ ] **Step 1: 공식 원본 파일을 `data/raw/`에 저장하거나 수집 방법을 확인**

  서울시 공식 페이지에서 2023·2024년 파일을 내려받고, Open-Meteo Historical Weather API에서 서울 중심 좌표의 일별 평균기온·강수량을 내려받는다. 파일명과 다운로드 날짜를 `data/README.md`에 기록한다. 원본을 저장하지 못하면 정제 결과와 재수집 절차를 반드시 남긴다.

- [ ] **Step 2: 실제 파이프라인 실행**

  Run: `python analysis.py --bike-dir data/raw/bike --weather data/raw/weather_seoul_108.csv --output-dir . --start 2023-01-01 --end 2024-12-31`

  Expected: 정제 CSV 1개, 필수 PNG 3개 이상, 기간·행 수·결측·이상치 요약이 출력된다.

- [ ] **Step 3: 실행 결과를 독립적으로 확인**

  `python -c` 또는 pytest fixture를 사용해 정제 CSV의 날짜 정렬, 행 수 100 이상, 음수 이용량 없음, 차트 파일 존재를 확인한다. 리포트에 쓸 모든 숫자는 생성된 CSV와 요약 출력에서 다시 확인한다.

- [ ] **Step 4: 사실과 해석을 분리한 REPORT.md 작성**

  설계 문서의 4개 질문을 기준으로 작성한다. 각 인사이트는 `관찰(Fact)`, `해석(Hypothesis)`, `행동/추가 분석(Action)` 순서로 구성하고, 실제 수치와 날짜 구간을 포함한다. 날씨와 이용량은 상관관계로만 표현하며 외부 요인을 통제하지 않은 한계를 기록한다.

- [ ] **Step 5: AI 사용 로그와 재현성 정보 추가**

  REPORT.md 마지막에 전처리·시각화·해석 문장 다듬기에 AI를 사용한 내용, 사용 이유, 샘플링 재계산·코드 재실행·대안 비교를 통한 검증 방법을 기록한다.

- [ ] **Step 6: 리포트 링크와 렌더링 확인**

  `rg`로 이미지 링크가 실제 파일명과 일치하는지 확인하고, Markdown 상대경로가 정상인지 점검한다. `git diff --check`로 공백 오류를 확인한다.

- [ ] **Step 7: 커밋**

  ```bash
  git add REPORT.md README.md data images data/processed_daily_rentals.csv
  git commit -m "docs: add bike time-series analysis report"
  ```

### Task 7: 전체 검증과 제출 상태 점검

**Files:**
- Modify: 필요한 경우 `README.md`, `REPORT.md`, `data/README.md`

- [ ] **Step 1: 전체 테스트 실행**

  Run: `pytest -q`

  Expected: 모든 테스트 PASS.

- [ ] **Step 2: 새 환경 재현 명령 확인**

  `python -m venv .venv`, `pip install -r requirements.txt`, `python analysis.py ...` 순서를 README와 대조한다. 시스템 Python에 이미 설치된 라이브러리에 의존하지 않도록 requirements를 확인한다.

- [ ] **Step 3: 제출 조건 점검**

  다음을 체크한다: 100개 이상 데이터 포인트, 질문 3개 이상, 시각화 3개 이상, 분석 기법 2개 이상, 인사이트 3개 이상, 결론·한계점, AI 사용 로그, 출처·기간·실행방법.

- [ ] **Step 4: 최종 diff 확인과 커밋**

  Run: `git status --short`, `git diff --check`, `git log --oneline --max-count=8`

  Expected: 의도하지 않은 파일이 없고 공백 오류가 없으며 필요한 커밋이 존재한다.
