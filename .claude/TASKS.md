# TASKS

> 지금 해야 할 일만 유지합니다. 완료하면 체크하고 "완료됨"으로 옮기고, 새로 생기면 위에 추가합니다.

## 지금 할 일 (In Progress / To Do)

- [ ] **신규 기능 - 제품메뉴얼 그룹 (DB + API)**
  - 테이블: `product_manuals` (id, product_name, manual_url, sort_order, created_at, created_by)
  - API:
    - `GET /api/product-manuals` 목록 조회
    - `POST /api/product-manuals` 생성
    - `DELETE /api/product-manuals/{id}` 삭제
  - 유효성 검사:
    - manual_url은 https:// 로 시작
    - product_name 중복 불가
    - URL 형식 유효성 검사
  - 확인: 마이그레이션 후 DB 테이블 생성 여부

- [ ] **신규 기능 - 제품메뉴얼 그룹 (Frontend - 사이드 메뉴)**
  - 사이드 메뉴에 `제품메뉴얼` 그룹 추가 (아이콘: book)
  - DB에서 불러온 제품이름 리스트 렌더링 (sort_order 순)
  - 클릭 시 `window.open(manual_url, '_blank')` 외부 새창 열림
  - 데이터 없을 때 `등록된 메뉴얼이 없습니다` 표시
  - 초기 데이터 예시:
    - 전어 미나리 가이드: `https://seasonal-jeoneo-minari-guide.challoo.chatgpt.site/#order`
    - 새우 가이드: `https://seasonal-shrimp-guide.challoo.chatgpt.site/`
    - 치킨난반 가이드: `https://chicken-nanban-guide.challoo.chatgpt.site/`

- [ ] **신규 기능 - 제품메뉴얼 그룹 (Frontend - 등록 팝업)**
  - 사이드 메뉴 그룹 옆 `+` 버튼 또는 설정 페이지에 `추가` 버튼
  - 팝업 구성: 제품 이름 input, 링크 input
  - 저장 시 API 호출, 성공하면 사이드 메뉴 즉시 갱신 (invalidate query)
  - 권한: 관리자만 추가/삭제 가능
  - 삭제: 각 아이템 옆 휴지통 아이콘, confirm 후 삭제

- [ ] **일일매출, 기간매출 데이터 로딩 표시 추가**
  - 현상: 일일매출/기간매출 조회 시 데이터 로딩 중인지 구분이 안 돼서 빈 화면으로 보임
  - 할 일: frontend 대시보드 - 일일 요약 카드, 기간매출 차트/테이블에 loading spinner 또는 skeleton UI 추가, API 호출 중 isLoading 상태 관리
  - 확인 위치: `backend/sales` 집계 API 호출 구간, `frontend/src/views/Dashboard.vue` 또는 해당 컴포넌트

- [ ] **matepos 할인값 매칭 추가**
  - 현상: tosspos는 discounts 합산해서 channel_discount에 넣는데, matepos는 0으로 비어있음
  - 할 일: matepos raw_data에서 할인 필드 찾아서 discount_amount / channel_discount에 매핑

## 검증/확인 대기중
- (없음)

## 완료됨

- [x] 2026-09 — Phase 1 매출 집계 기능 전체 완료 (matepos/tosspos 백필, 웹훅, 대시보드)
- [x] 2026-09-30 — tosspos API 인증 스킴 실제 발급 키로 검증 완료 (`test_toss_auth.py` 실행, `resultType=SUCCESS` 확인)
- [x] 2026-09-30 — `order_category` 분류 버그 수정: `source`가 `POS` 단독 비교였던 것을 `POS`/`TABLE_ORDER`/`KIOSK`(오프라인 소스 집합) 기준으로 변경 (`backend/integrations/tosspos/mapper.py`)
- [x] 2026-09-30 — matepos/tosspos 금액 필드 실데이터 검증: `channel_discount`는 tosspos `discounts` 배열 전체 합산(방식 A)으로 확정 (상세 이유는 API_NOTES.md 참고)
- [x] 2026-09-30 — 채널명 통일: matepos(`BAEMIN`/`CPEATS`/`YOGIYO`/`DKY`/`POS`) + tosspos(`PLUGIN_*`/`TABLE_ORDER`/`POS`) → "배민/쿠팡/요기요/땡겨요/내점(POS)/내점(테이블)"로 통일. `backend/common/channel_names.py` 신설, `mapper.py`/`matepos.py` 적용, 기존 데이터는 `normalize_channel_names` 커맨드로 일괄 변환 완료
- [x] 2026-09-30 — 웹훅 버그 수정: `order.*`/`payment.*` 양쪽에서 얇은 상태변경 알림(`opened`/`completed`/`payment.approved`)을 주문 전체로 오인하던 `or data` fallback 제거 (`backend/integrations/tosspos/views.py`). 실데이터 추적 결과 실제 매출 유실은 없고 가짜 레코드(id=19343) 하나만 생성됐던 것으로 확인, 삭제 완료
- [x] 2026-09-30 — tosspos 웹훅 등록 (cloudtype 배포 후 진행)
- [x] 2026-09-30 — `Sale.objects.filter(order_seq="None")`으로 동일 패턴 가짜 레코드 더 있는지 확인완료 0건
