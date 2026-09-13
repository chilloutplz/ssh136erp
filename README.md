# ssh136erp

매장 ERP 프로젝트. 1차 목표는 **매출 데이터 통합 수집**.
향후 BOM, 배달플랫폼/카드사 정산·입금일자 등으로 확장 예정.

## 구조 (monorepo)

```
ssh136erp/
├── backend/      # Django + DRF + (SQLite→PostgreSQL) — 이번 단계 구현 완료
├── frontend/     # Vue3 실시간 매출 정산 화면 — 다음 단계
└── scraper/      # 배달플랫폼 정산 스크래핑 — 추후 필요 시 구조 확정
```

## backend 개요

- **통합 매출 모델**: `Sale` – `SaleItem` – `SaleTender`
  matepos 스크립트(`map_sale`/`map_item`/`map_tender`)의 필드 체계를 기준으로,
  tosspos 데이터도 동일 스키마로 매핑해서 저장합니다.
- **matepos**: 2024.3.1~2026.5.20 **1회성 백필** (`python manage.py backfill_matepos`)
- **tosspos**: 2026.5.21~어제 구간은 Open API로 백필(추후 배치 작성 필요), 이후는 **웹훅 실시간 수신**
- **정산/카드수수료/입금예정**: 이번 단계에서는 제외. `raw_data` JSON 필드에 원본을 보관해 두어
  나중에 재계산·확장 가능하도록 설계했습니다.

### 실행 방법

```bash
cd backend
./venv/bin/python manage.py runserver   # 개발 서버 (matepos 백필 스크립트가 이 서버로 데이터를 쏩니다)

# 다른 터미널에서 matepos 백필 (dry-run 먼저 권장)
./venv/bin/python manage.py backfill_matepos --start 20240301 --end 20260520 --dry-run
./venv/bin/python manage.py backfill_matepos --start 20240301 --end 20260520
```

`.env.example`을 `.env`로 복사한 뒤 matepos / tosspos 인증 정보를 채워주세요.

### 주요 API

| Method | Path | 설명 |
|---|---|---|
| POST | `/api/sales/bulk-create/` | 매출 레코드 리스트 upsert (내부 API Key 필요) |
| GET | `/api/sales/` | 매출 목록 조회 (필터: store_code, source, business_date_from/to) |
| GET | `/api/sales/summary/daily/` | 일자별 매출 합계 |
| POST | `/api/integrations/tosspos/webhook/` | tosspos 웹훅 수신 (서명 검증 + 멱등 처리) |

### ⚠️ 다음 단계에서 반드시 확인/보정이 필요한 부분

1. **tosspos 실제 API 인증 스킴** — `client.py`의 `Authorization: Bearer` 형식이 실제 발급받은
   API Key와 맞는지 개발자센터 문서/발급 화면에서 확인 필요.
2. **tosspos 웹훅 등록** — 개발자센터에서 Payload URL, 수신 이벤트, Secret Key 설정 (cloudtype 배포 후 가능).
3. **tosspos 금액 필드 매핑 검증** — `mapper.py`의 `actual_sale_amount` 등은 matepos의 "POS 실매출액"
   개념과 정확히 대응하는지 실제 tosspos 응답으로 검증 필요.
4. **tosspos 2026.5.21~어제 백필 스크립트** — `client.py`의 `TossPlaceClient`를 이용한
   management command는 아직 미작성 (구조만 준비됨).
