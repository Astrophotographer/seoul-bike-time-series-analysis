# 서울시 따릉이 시계열 분석

2023~2024년 서울시 따릉이 일별 이용량의 추세, 계절성, 날씨와의 연관성, 이상 구간을 분석하는 프로젝트다.

## 웹 대시보드

분석 결과를 차트와 인사이트 카드로 탐색할 수 있는 정적 페이지를 GitHub Pages로 배포했다.

- [라이브 대시보드](https://astrophotographer.github.io/seoul-bike-time-series-analysis/)
- [GitHub 저장소](https://github.com/Astrophotographer/seoul-bike-time-series-analysis)

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
│   ├── 2023_h1_status.csv
│   ├── 2023_h2_status.csv
│   ├── 2024_h1_status.csv
│   └── 2024_h2_status.csv
└── weather_seoul_open_meteo.csv
```

기상 원본은 현재 `weather_seoul_open_meteo.csv`를 사용한다. 자세한 출처와 재수집 명령은 [data/README.md](data/README.md)를 확인한다.

기상 파일을 다시 만들 때는 `python scripts/download_weather.py --output data/raw/weather_seoul_open_meteo.csv`를 실행한다.

## 분석 실행

```bash
python analysis.py \
  --bike-dir data/raw/bike \
  --weather data/raw/weather_seoul_open_meteo.csv \
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
- `images/05_correlation.png`: 평균기온·강수량과 이용량의 Spearman 상관 산점도
- `images/06_baseline_forecast.png`: 마지막 28일 holdout의 7일 계절성 naive baseline 예측

## 테스트

```bash
pytest -q
```

## 리포트

분석 질문, 전처리 기준, 시각화, 인사이트, 결론·한계점, AI 사용 로그는 [REPORT.md](REPORT.md)에 기록한다.
