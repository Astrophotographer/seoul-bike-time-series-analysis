# 서울시 따릉이 시계열 분석

2023~2024년 서울시 따릉이 일별 이용량의 추세, 계절성, 날씨와의 연관성, 이상 구간을 분석하는 프로젝트다.

## 실행 환경

- Python 3.10 이상
- pandas, NumPy, Matplotlib, Seaborn, statsmodels, pytest

## 설치

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 데이터 준비

데이터 다운로드 방법과 파일명은 [data/README.md](data/README.md)에 정리되어 있다.

```text
data/raw/
├── bike/
│   ├── 2023년 상반기 CSV
│   ├── 2023년 하반기 CSV
│   ├── 2024년 상반기 CSV
│   └── 2024년 하반기 CSV
└── weather_seoul_108.csv
```

## 분석 실행

```bash
python analysis.py \
  --bike-dir data/raw/bike \
  --weather data/raw/weather_seoul_108.csv \
  --output-dir . \
  --start 2023-01-01 \
  --end 2024-12-31
```

날씨 데이터 없이 따릉이 단일 시계열만 실행하려면 `--weather` 옵션을 생략한다.

실행 결과:

- `data/processed_daily_rentals.csv`: 날짜별 집계·특징·이상치 플래그
- `images/01_daily_trend.png`: 일별 이용량과 7일 이동평균
- `images/02_month_weekday_heatmap.png`: 월별·요일별 평균
- `images/03_weather_effect.png`: 강수·기온 구간별 비교
- `images/04_stl_decomposition.png`: `statsmodels`가 설치된 경우 생성되는 STL 분해

## 테스트

```bash
pytest -q
```

## 리포트

분석 질문, 전처리 기준, 시각화, 인사이트, 결론·한계점, AI 사용 로그는 [REPORT.md](REPORT.md)에 기록한다.
