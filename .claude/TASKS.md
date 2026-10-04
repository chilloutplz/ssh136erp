# TASKS

> 지금 해야 할 일만 유지합니다. 완료하면 체크하고 "완료됨"으로 옮기고, 새로 생기면 위에 추가합니다.

## 지금 할 일 (In Progress / To Do)

- [ ] **주문 취소 SaleCancel 테이블 (grok/feat/sale-cancel-table)**
  - 모델: `SaleCancel` (원 Sale FK, channel_order_no, cancel_amount, process_note, is_read)
  - 유니크: `(source, store_code, channel_order_no, cancelled_at)` — 충돌 시 process_note
  - 원주문 미매칭: `sale=null` + process_note, 원 Sale 있으면 `payment_status=결제취소`
  - API: `GET /api/sales/summary/cancel/`, `GET /api/sales/cancels/notes/`, `PATCH /api/sales/cancels/<id>/read/`
  - tosspos cancelled.v1 / matepos cancelYn(bulk 시 serializer) → SaleCancel
  - 프론트: AppShell 알림 벨, 일일매출 취소 카드, 주문상세 취소 이력
  - 배포: cloudtype 브랜치 `grok/feat/sale-cancel-table` + `python manage.py migrate` (0004)
  - 확인: 실웹훅 취소 1건, summary/cancel, 벨 process_note

- [ ] **matepos 할인값 매칭 추가**
  - 현상: tosspos는 discounts 합산해서 channel_discount에 넣는데, matepos는 0으로 비어있음
  - 할 일: matepos raw_data에서 할인 필드 찾아서 discount_amount / channel_discount에 매핑

## 검증/확인 대기중

- [ ] **일일매출, 기간매출 데이터 로딩 표시 추가**
  - 구현: DashboardView / PeriodSalesView — 조회 중 스피너 패널, 새로고침 버튼 disabled
  - 확인: 날짜 변경·새로고침 시 "불러오는 중" 스피너가 보이고, 완료 후 카드/목록 표시
  - 브랜치/PR: `feat/sales-loading-ui`

## 완료됨

- [x] 2026-10-02 — 제품메뉴얼 그룹 (DB + API): `manuals.ProductManual`, `GET/POST /api/product-manuals/`, `DELETE /api/product-manuals/<id>/`, https 검증·이름 중복 불가, 시드 3건, migrate 적용 확인
- [x] 2026-10-02 — 제품메뉴얼 그룹 (Frontend - 사이드 메뉴): 매출/매입 아래 제품메뉴얼 목록, 클릭 시 새 창, 빈 목록 안내, 그룹 라벨 색 구분
- [x] 2026-10-02 — 제품메뉴얼 그룹 (Frontend - 등록 팝업): `+` 추가 팝업, 목록 즉시 갱신, 항목별 삭제(confirm)
- [x] 2026-09 — Phase 1 매출 집계 기능 전체 완료 (matepos/tosspos 백필, 웹훅, 대시보드)
- [x] 2026-09-30 — tosspos API 인증 스킴 실제 발급 키로 검증 완료 (`test_toss_auth.py` 실행, `resultType=SUCCESS` 확인)
- [x] 2026-09-30 — `order_category` 분류 버그 수정: `source`가 `POS` 단독 비교였던 것을 `POS`/`TABLE_ORDER`/`KIOSK`(오프라인 소스 집합) 기준으로 변경 (`backend/integrations/tosspos/mapper.py`)
- [x] 2026-09-30 — matepos/tosspos 금액 필드 실데이터 검증: `channel_discount`는 tosspos `discounts` 배열 전체 합산(방식 A)으로 확정 (상세 이유는 API_NOTES.md 참고)
- [x] 2026-09-30 — 채널명 통일: matepos(`BAEMIN`/`CPEATS`/`YOGIYO`/`DKY`/`POS`) + tosspos(`PLUGIN_*`/`TABLE_ORDER`/`POS`) → "배민/쿠팡/요기요/땡겨요/내점(POS)/내점(테이블)"로 통일. `backend/common/channel_names.py` 신설, `mapper.py`/`matepos.py` 적용, 기존 데이터는 `normalize_channel_names` 커맨드로 일괄 변환 완료
- [x] 2026-09-30 — 웹훅 버그 수정: `order.*`/`payment.*` 양쪽에서 얇은 상태변경 알림(`opened`/`completed`/`payment.approved`)을 주문 전체로 오인하던 `or data` fallback 제거 (`backend/integrations/tosspos/views.py`). 실데이터 추적 결과 실제 매출 유실은 없고 가짜 레코드(id=19343) 하나만 생성됐던 것으로 확인, 삭제 완료
- [x] 2026-09-30 — tosspos 웹훅 등록 (cloudtype 배포 후 진행)
- [x] 2026-09-30 — `Sale.objects.filter(order_seq="None")`으로 동일 패턴 가짜 레코드 더 있는지 확인완료 0건
