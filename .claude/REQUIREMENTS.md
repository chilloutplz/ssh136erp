# ssh136erp 요구사항 명세

## 목적 & 범위

- 단일 매장(숙성회136) 운영을 위한 ERP
- 1차 목표: matepos(~2026년 중반) → tosspos(2026년 중반~) 매출 데이터를 하나의 정규화된 모델로 통합
- 확장 예정: 구매 관리, 원가/레시피(BOM) 관리

## 데이터 모델

### Sale — 매출(주문) 단위

- 식별: `source`(MATEPOS/TOSSPOS), `store_code`, `order_seq`, `business_date`, `sold_at`
- 채널/유형: `channel`, `channel_detail`, `order_type`(배달/포장/내점), `order_category`(온라인/오프라인)
- 결제: `payment_status`(결제완료/결제취소), `payment_method`, `delivery_company`
- 금액: `sale_amount`, `discount_amount`, `net_sale_amount`, `actual_sale_amount`, `taxable_amount`, `vat`, `non_taxable_amount`, `channel_delivery_fee`, `channel_discount`, `cup_deposit`, `online_delivery_fee`
- 반품 원본 참조: `org_business_date`, `org_order_seq`
- `raw_data`(JSONField) — 원본 payload 그대로 보관

### SaleItem — 품목 단위 (Sale에 FK)

### SaleTender — 결제수단 단위 (Sale에 FK)

## Phase 1 — 매출 집계 (완료)

- [x] matepos 백필 커맨드 (`backfill_matepos`)
- [x] tosspos Open API 클라이언트 + 백필 커맨드 (`backfill_tosspos`)
- [x] tosspos 웹훅 수신 (HMAC-SHA256 서명 검증 + `WebhookEventLog`로 멱등 처리)
- [x] tosspos → Sale 매퍼
- [x] 프론트엔드 대시보드: JWT 로그인, 일별 요약 카드(실매출/매출액/순매출/건수), 채널별 집계, 주문 목록 + 상세 드로어, 날짜 네비게이션

## Phase 2 — 구매 관리 (예정, 세부 사항 미확정)

- [ ] PDF 매입 인보이스 파싱

## Phase 3 — BOM 구축 (예정, 세부 사항 미확정)

- [ ] `goods_cd` 기준으로 매입 원재료 ↔ 판매 메뉴 연결

## 명시적으로 보류된 것

- 배달앱/카드사 정산·수수료·입금예정일 계산 — 훨씬 이후 단계로 연기
- 현재는 각 소스의 `raw_data`만 보관해두고, 정산 재계산 로직은 나중에 설계

## 확인/검증 필요 항목

- tosspos 웹훅 등록(Payload URL, 수신 이벤트, Secret Key) — cloudtype 배포 후 진행 가능
- tosspos 금액 필드(`actual_sale_amount` 등)가 matepos의 "POS 실매출액" 개념과 정확히 대응하는지 실데이터로 검증 필요

## 알아둘 것 — tosspos `source` 필드

- `source`는 고정 enum이 아니라 자유 문자열. 공식 문서에 언급된 값: `POS`(토스 POS), `KIOSK`(토스 키오스크), `PLUGIN_{appId}`(주문 생성 API로 만든 주문, 예: 배민 연동은 `PLUGIN_BAEMIN`)
- 위 목록에 없지만 실데이터로 확인된 값: `TABLE_ORDER`(토스 QR 테이블오더) — 손님이 직접 폰으로 주문하지만 매장 내 식사이므로 오프라인으로 분류
- `order_category`(오프라인/온라인) 판정은 `OFFLINE_SOURCES = {"POS", "TABLE_ORDER", "KIOSK"}` 집합 기준. 키오스크는 미사용이지만 도입 대비 미리 포함해둠
- `order_type`(내점/포장/배달)은 `source`가 아니라 `lineItems[0].diningOption` 기준으로 별도 결정됨 (`HERE→내점`, `TOGO/PICKUP→포장`, `DELIVERY→배달`) — `order_category`와 독립적이라 키오스크·테이블오더가 추가돼도 이 로직은 그대로 재사용됨
