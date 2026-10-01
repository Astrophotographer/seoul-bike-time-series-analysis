# 데이터 수집 안내

## 따릉이 원본

서울 열린데이터광장의 [서울시 공공자전거 따릉이 이용현황](https://data.seoul.go.kr/dataList/OA-14994/A/1/datasetView.do)에서 다음 일별 집계 파일을 내려받아 `data/raw/bike/`에 저장한다. 현재 실행에 사용한 로컬 파일명은 괄호 안에 적었다.

- `서울특별시 공공자전거 일별 대여건수_23.1-6.xlsx` (`2023_h1_status.csv`로 변환)
- `서울특별시 공공자전거 일별 대여건수_23.7-12.csv` (`2023_h2_status.csv`)
- `서울특별시 공공자전거 일별 대여건수_24.1-6.csv` (`2024_h1_status.csv`)
- `서울특별시 공공자전거 일별 대여건수_24.7-12.csv` (`2024_h2_status.csv`)
- `서울특별시 공공자전거 일별 대여건수_25.1-6.csv` (`2025_h1_status.csv`)
- `서울특별시 공공자전거 일별 대여건수_25.7-12.csv` (`2025_h2_status.csv`)
- `서울특별시 공공자전거 일별 대여건수_26.1-6.csv` (`2026_h1_status.csv`)

분석에 사용하는 원본 컬럼은 `대여일자`와 `대여건수`이다. 이 자료는 이미 서울시 전체 일별 대여건수로 집계되어 있으므로 추가 대여소 합산을 하지 않는다. 서울시 파일은 CP949 계열 인코딩일 수 있어 분석 코드가 UTF-8·CP949·EUC-KR 순서로 읽는다. 원본 파일은 용량과 이용조건을 확인한 뒤 GitHub에 포함하거나, 포함하지 않는 경우에도 이 문서와 공식 URL을 함께 배포한다.

## 기상 원본

기상청 다운로드에 로그인 절차가 필요한 환경에서도 재현할 수 있도록 [Open-Meteo 과거 기상 API](https://open-meteo.com/en/docs/historical-weather-api)를 사용했다. 서울 중심 좌표 `37.5665, 126.9780`을 API에 전달하고, API가 반환한 서울 인근 격자의 2023-01-01~2026-06-30 일별 자료를 `data/raw/weather_seoul_open_meteo.csv`에 저장한다.

재수집 명령:

```bash
python scripts/download_weather.py \
  --start 2023-01-01 \
  --end 2026-06-30 \
  --output data/raw/weather_seoul_open_meteo.csv
```

수집 스크립트는 API 응답의 `time`, `temperature_2m_mean`, `precipitation_sum`을 분석용 컬럼으로 저장한다. 분석 코드는 다음 의미의 컬럼명 변형도 자동으로 표준화한다.

- 날짜 → `date`
- 평균기온 → `mean_temp_c`
- 일강수량 → `precip_mm`

## 출처·이용조건 기록

- 다운로드 시점: 2026-10-01
- 제공기관: 서울특별시, Open-Meteo
- 원본 URL과 사용 컬럼은 위 링크에서 확인한다.
- Open-Meteo는 데이터 출처로 ERA5 및 자사 모델 자료를 안내하므로, 제출 전 [Open-Meteo 이용조건·출처 안내](https://open-meteo.com/en/license)를 다시 확인하고 출처를 표기한다.
- 서울시 파일과 Open-Meteo 자료 모두 최신 이용허락·출처표기 조건을 제출 전에 다시 확인한다.
