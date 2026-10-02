# tosspos(토스플레이스) Open API 참조 노트

> 공식 문서(docs.tossplace.com)를 확인하면서 알게 된 필드 의미, enum 값, 헷갈리기 쉬운 부분을 기록합니다.
> 매번 문서를 다시 찾지 않도록, 코드에서 특정 필드값을 다룰 때 이 파일부터 확인하세요.
> 확인 안 된 필드는 "미확인"으로 남겨두고, 실데이터/문서로 확인되면 채워 넣습니다.

## Order.source — 주문 채널

고정 enum이 아니라 자유 문자열. 확인된 값:

| 값 | 의미 | 분류(오프라인/온라인) |
| --- | --- | --- |
| `POS` | 토스 POS에서 인입 | 오프라인 |
| `KIOSK` | 토스 키오스크에서 인입 (공식문서 언급, 실사용 안 함) | 오프라인 |
| `TABLE_ORDER` | 토스 QR 테이블오더 — 손님이 폰으로 직접 주문하지만 매장 내 식사 | 오프라인 |
| `PLUGIN_{appId}` | 주문 생성 API로 생성된 주문. 예: 배민 연동은 `PLUGIN_BAEMIN` | 온라인 |

- `mapper.py`의 `OFFLINE_SOURCES = {"POS", "TABLE_ORDER", "KIOSK"}`로 판정.
- 새로운 배달앱/플러그인 연동 시 `PLUGIN_{앱이름}` 형태로 새 값이 생길 수 있음 — `OFFLINE_SOURCES`에 넣을 필요 없음(기본이 온라인).

## Order.orderState — 주문 상태

| 값 | 의미 |
| --- | --- |
| `REQUESTED` | 주문 수락 전 (픽업 주문 등) |
| `OPENED` | 시작됨 |
| `COMPLETED` | 완료됨 (결제까지 완료) |
| `CANCELLED` | 취소됨 |
| `UNDEFINED` | — |

- `mapper.py`는 `CANCELLED`만 "결제취소"로, 나머지는 전부 "결제완료"로 매핑. `REQUESTED`/`OPENED` 상태 주문이 웹훅으로 들어올 경우 이 매핑이 맞는지는 **미확인** — 아직 실제로 이 상태의 웹훅을 받아본 적 없음.

## OrderLineItem.diningOption — 식사 옵션

| 값 | 의미 | `order_type` 매핑 |
| --- | --- | --- |
| `HERE` | 매장 식사 | 내점 |
| `TOGO` | 포장 (즉석) | 포장 |
| `PICKUP` | 포장 (사전 예약 픽업) | 포장 |
| `DELIVERY` | 배달 | 배달 |
| `UNDEFINED` | — | — |

- `TOGO`와 `PICKUP`은 서로 다른 값이지만 매장 입장에선 둘 다 "포장"으로 처리해도 무방해서 `DINING_OPTION_MAP`에서 합침.
- `PICKUP`은 `OrderRequestedInfo`(예상 준비 완료 시각 등)와 연결되는 사전 예약 흐름. 현재 스키마엔 이 타이밍 정보를 저장하는 필드가 없음 — 필요해지면 `raw_data`에서 꺼내 써야 함.

## Payment 필드 — paymentMethod vs sourceType

두 필드가 서로 다른 레벨.

| 필드 | 성격 | 비고 |
| --- | --- | --- |
| `paymentMethod` | 세부 분류 (자유 문자열) | 예: `"CARD_NFC"` |
| `sourceType` (PaymentSourceType) | 대분류 (고정 enum) | `CASH`, `CARD`, `PREPAID_VALUE`, `ACCOUNT_TRANSFER`, `BARCODE`, `EXTERNAL`, `UNDEFINED` |

- `mapper.py`의 `_normalized_payment_code()`는 `paymentMethod`와 `sourceType` 양쪽에 `TRANSFER`/`ACCOUNT_TRANSFER`가 섞여 나올 수 있어서 둘 다 체크함.
- `BARCODE`(간편결제) 관련 `paymentMethod` 세부값은 **미확인** — 간편결제 결제 건이 실제로 들어오면 `paymentMethod` 예시값(`"CARD_NFC"`류)을 확인해서 이 표에 추가할 것.

## Order.discounts — 할인 내역 (channel_discount 매핑)

- `discounts[].title`이 실데이터에서 `"즉시 할인(업주 부담)"`으로 확인됨 (matepos의 `calculatedSaleExceptAmt`와 같은 개념 — 배달앱 즉시할인 중 매장이 부담하는 금액).
- 다만 **toss API 응답 자체엔 "업주 부담"과 "플랫폼 부담"을 구분하는 구조적 필드가 없음** (`type`은 `VARIABLE_AMOUNT` 등 계산방식 표시일 뿐, 부담 주체 표시가 아님). `title` 텍스트로만 구분 가능한데, 배달플랫폼별 정산 데이터를 따로 붙여서 대조하지 않으면 정확한 구분이 불가능하다고 판단.
- **결정 (2026-09-30): 당장은 `discounts` 배열 전체를 구분 없이 합산해서 `channel_discount`에 넣는다.** (`sum(d.get("amount") for d in order.get("discounts", []))`)
- 나중에 배달플랫폼 정산 데이터 연동(Phase 3 이후 가능성)이 생기면, 그때 실제 정산 금액과 대조해서 title 기반 필터링이 필요한지 재검토.
- 품목 단위 할인(`lineItems[].appliedDiscounts`)은 아직 `channel_discount`에 포함 안 함 — 품목 할인이 실제로 존재하는지, 존재한다면 합산해야 하는지는 **미확인**.

## 아직 확인 안 된 것

- `PaymentEasyPayDetails`(간편결제 세부: provider, acquirer 등)를 `mapper.py`에서 활용할지 여부
- `OrderRequestedInfo`(픽업/배달 주문 요청 정보) 활용 여부 — 현재는 `raw_data`에만 보관됨
- `Discount`, `OrderAccrual`(적립), `OrderRedemption`(혜택 사용) — 현재 스키마에 반영 안 됨, ALPHA 단계 필드라 우선순위 낮음

## 웹훅 이벤트별 payload 구조 — order.* / payment.*

같은 주문 하나에 대해 토스가 여러 이벤트를 거의 동시에 보낸다. 이벤트별로 담긴 정보량이 다르다.

| event_type | 구조 | 비고 |
| --- | --- | --- |
| `order.order.created.v1` | `data.order`에 **전체 Order 객체** (`chargePrice`, `lineItems`, `discounts`, `payments` 등) | 주문 생성 시점에 이미 금액까지 확정돼서 들어옴 (실데이터로 확인: TABLE_ORDER 주문도 created 시점에 `chargePrice` 완전히 채워져 있었음) |
| `order.order.opened.v1` | `data = {source, orderId, orderKey, openedAt, orderNumber}` — **얇음, `order` 키 없음** | 상태 변경 알림만 |
| `order.order.completed.v1` | `data = {source, orderId, orderKey, completedAt, orderNumber}` — **얇음, `order` 키 없음** | 상태 변경 알림만 |
| `payment.payment.approved.v1` | `data.payment`에 결제 상세 (`amount`, `cardDetails` 등) — **`order` 키 없음** | 결제 상세이지 주문 상세가 아님 |

- `created`만 Sale을 만들기에 충분한 전체 데이터를 담고 있고, 나머지(`opened`/`completed`/`payment.approved`)는 상태 변경 알림일 뿐이라 무시해도 매출 데이터 유실이 없음.
- `order.order.updated.v1` 같은 다른 `order.*` 이벤트가 올 경우 구조가 `created`와 같은지 `opened`/`completed`처럼 얇은지는 **미확인** — 실제로 받아보면 이 표에 추가할 것.

## 알려진 버그 — 얇은 이벤트를 주문 전체로 오인해 가짜 Sale 생성 (수정됨)

- `views.py`의 `_dispatch()`가 `order.*`/`payment.*` 양쪽에서 `... or data` 형태의 과도한 fallback을 쓰고 있었음.
- `opened`/`completed`/`payment.approved`처럼 `order` 키가 없는 얇은 이벤트가 오면, `data`(또는 `payment`) 자체가 `order`로 오인되어 `order_seq="None"`(문자열), `channel=""`(또는 `TABLE_ORDER`), 금액 0인 가짜 Sale 레코드가 생성됨. (사례: 2026-09-16 21:49 KST 수신 건 → id=19343, 이후 삭제)
- 실제 주문 데이터 자체는 `created` 이벤트에서 이미 정상 처리돼 있었어서(id=19341, 64,500원 정확히 일치), **데이터 유실은 없었고 중복 쓰레기 행만 생긴 것으로 확인됨**.
- **수정 (2026-09-30)**: `order.*`는 `data.get("order")`만, `payment.*`는 `data.get("order") or data.get("payment", {}).get("order")`만 사용하도록 fallback 제거. `order`가 없으면 `if not order: return`으로 조용히 스킵.
- 같은 패턴으로 생긴 가짜 레코드가 더 있는지 의심되면 `Sale.objects.filter(order_seq="None")`으로 확인할 것.

