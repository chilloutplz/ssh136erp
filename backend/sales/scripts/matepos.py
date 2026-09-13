"""
MATE POS 주문건별 매출 스크래퍼
- 자동 로그인 → 리스트 수집 → 건별 상세 수집 → Django 전송
- 세션 만료 시 자동 재로그인 → 장기 실행 안전
- run.py 에서 호출하거나 직접 실행 가능
"""
import httpx
import asyncio
from datetime import date, timedelta
import os, sys
from decouple import config

# ── 설정 ─────────────────────────────────────────────────────
MATEPOS_BASE = "https://www.matetech.co.kr"
LOGIN_URL    = f"{MATEPOS_BASE}/login"

MATEPOS_USER_ID  = config("MATEPOS_USER_ID", default=None)
MATEPOS_PASSWORD = config("MATEPOS_PASSWORD", default=None)

API_BASE = config("API_BASE", default="http://localhost:8000/api")
SALES_BULK_CREATE    = f"{API_BASE}/sales/bulk-create/"
INTERNAL_API_KEY     = config("INTERNAL_API_KEY", default="")

HQ_BRAND_ID        = config("HQ_BRAND_ID", default=None)
MS_STR_ID          = config("MS_STR_ID", default=None)
STORE_CODE         = config("STORE_CODE", default=MS_STR_ID)
STORE_NAME         = config("STORE_NAME", default=None)
LIST_URL           = f"{MATEPOS_BASE}/api/sal0011/brands/{HQ_BRAND_ID}/stores/{MS_STR_ID}/sales/orders"
DETAIL_URL         = f"{MATEPOS_BASE}/api/sal0011/brands/{HQ_BRAND_ID}/stores/{MS_STR_ID}/sales/orders"
DETAIL_CONCURRENCY = 5   # 동시 상세 호출 수
RELOGIN_INTERVAL   = 50  # N일마다 재로그인 (세션 만료 예방)

enpCd = config("ENPCD", default=None)
corpCd = config("CORPCD", default=None)
brandCd = config("BRANDCD", default=None)

LIST_PARAMS = {
    "hqBrandId":      HQ_BRAND_ID,
    "msStrId":        MS_STR_ID,
    "strType":        "ONLY",
    "salesTermType":  "DAILY",
    "searchDate":     "oper",
    "orderTodayFlag": "N",
    "enpCd":          enpCd,
    "corpCd":         corpCd,
    "brandCd":        brandCd,
    "onlineYn":       "",
    "orderType":      "",
    "returnYn":       "",
    "size":           20,
}

HEADERS = {
    "Accept":           "application/json, text/javascript, */*; q=0.01",
    "Accept-Language":  "ko-KR,ko;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
    "Referer":          f"{MATEPOS_BASE}/service/saa0010/sales/analysis/term-orders",
}


# ── 로그인 ────────────────────────────────────────────────────
async def login(client: httpx.AsyncClient) -> bool:
    resp = await client.post(
        LOGIN_URL,
        data={
            "autoSignOn": "",
            "userId":     MATEPOS_USER_ID,
            "pw":         MATEPOS_PASSWORD,
            "authToken":  "",
            "isAgree":    "false",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    
    if resp.status_code not in (200, 302):
        print(f"[MATEPOS] 로그인 실패: status={resp.status_code}")
        return False
    try:
        body = resp.json()
        if not body.get("status", True):
            print(f"[MATEPOS] 로그인 실패: {body.get('message')}")
            return False
    except Exception:
        pass
    print("[MATEPOS] 로그인 성공")
    return True


def _is_session_expired(resp: httpx.Response) -> bool:
    """응답이 HTML 이거나 인증 오류 코드면 세션 만료로 판단"""
    if "text/html" in resp.headers.get("content-type", ""):
        return True
    try:
        body = resp.json()
        if str(body.get("code", "")) in ("401", "403"):
            return True
        msg = body.get("message", "") or ""
        if not body.get("status") and any(k in msg.lower() for k in ("login", "session", "auth", "인증", "로그인")):
            return True
    except Exception:
        pass
    return False


async def ensure_login(client: httpx.AsyncClient) -> bool:
    """세션 만료 감지 시 재로그인"""
    print("[MATEPOS] 세션 만료 — 재로그인 시도...")
    return await login(client)


# ── 리스트 수집 ───────────────────────────────────────────────
async def fetch_list(client: httpx.AsyncClient, target_date: str) -> list[dict] | None:
    """
    하루치 주문 목록.
    세션 만료 감지 시 None 반환 → 호출부에서 재로그인 후 재시도.
    """
    all_items = []
    page = 1
    total_page = 1

    while True:
        params = {
            **LIST_PARAMS,
            "operDt":     target_date,
            "operDtFrom": target_date,
            "operDtTo":   target_date,
            "page":       page,
        }
        resp = await client.get(LIST_URL, params=params)
        resp.raise_for_status()

        if _is_session_expired(resp):
            return None

        body = resp.json()
        if not body.get("status"):
            print(f"[MATEPOS] [{target_date}] 리스트 오류: {body.get('message')}")
            break

        result     = body["data"]["result"]
        content    = result.get("content", [])
        total_page = result.get("totalPage", 1)
        all_items.extend(content)

        if page >= total_page:
            break
        page += 1
        await asyncio.sleep(0.2)

    print(f"[MATEPOS] [{target_date}] 리스트 {len(all_items)}건 ({total_page}페이지)")
    return all_items


# ── 단건 상세 수집 ────────────────────────────────────────────
async def fetch_detail(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    oper_dt: str,
    tr_seq: str,
) -> dict | None:
    async with sem:
        try:
            resp = await client.get(f"{DETAIL_URL}/{oper_dt}/{tr_seq}")
            resp.raise_for_status()

            if _is_session_expired(resp):
                print(f"[MATEPOS] 상세 세션만료: {oper_dt}/{tr_seq}")
                return None

            body = resp.json()
            if not body.get("status"):
                print(f"[MATEPOS] 상세 오류: {oper_dt}/{tr_seq}: {body.get('message')}")
                return None
            return body["data"]["result"]
        except Exception as e:
            print(f"[MATEPOS] 상세 오류: {oper_dt}/{tr_seq}: {e}")
            return None


# ── 필드 매핑 ─────────────────────────────────────────────────
def map_sale(detail: dict) -> dict:
    
    # print("===== detail keys =====")
    # for key, value in detail.items():
    #     print(f"{key}: {value}")
    # print("=======================")
    
    od = detail.get("operDt", "")
    ot = detail.get("orderTm", "")
    sold_at = (
        f"{od[0:4]}-{od[4:6]}-{od[6:8]}T{ot[0:2]}:{ot[2:4]}:{ot[4:6]}"
        if len(od) == 8 and len(ot) == 6 else None
    )
    business_date = f"{od[0:4]}-{od[4:6]}-{od[6:8]}" if len(od) == 8 else None

    return {
        "source":               "MATEPOS",
        "store_code":           STORE_CODE,
        "store_name":           STORE_NAME,
        "business_date":        business_date,
        "sold_at":              sold_at,
        "order_seq":            int(detail.get("trSeq", 0)),
        "channel_order_no":     _nullify(detail.get("displayChannelOrderNo")),
        "order_category":       "온라인" if detail.get("onlineOrderYn") == "Y" else "오프라인",
        "channel":              detail.get("channelCd", "HALL"),
        "channel_detail":       detail.get("webSalesGrpNm") or "",
        "order_type":           _map_order_type(detail.get("orderSp")),
        # cancelYn=Y 인 경우만 결제취소, 반품(returnYn=Y)은 결제완료로 처리
        "payment_status":       "결제취소" if detail.get("cancelYn") == "Y" else "결제완료",
        "payment_method":       _payment_method(detail.get("tenders", [])),
        "delivery_company":     _nullify(detail.get("dlvAgncCoCd")),
        "sale_amount":          int(detail.get("saleAmt")                 or 0),
        "discount_amount":      int(detail.get("discountAmt")             or 0),
        "net_sale_amount":      int(detail.get("totAmt")                  or 0),
        "channel_delivery_fee": int(detail.get("channelDeliveryAmt")      or 0),
        "channel_discount":     int(detail.get("calculatedSaleExceptAmt") or 0),
        # calculatedSaleAmt - calculatedSaleExceptAmt = POS 실매출액
        "actual_sale_amount":   int(detail.get("calculatedSaleAmt") or 0) - int(detail.get("calculatedSaleExceptAmt") or 0),
        "taxable_amount":       int(detail.get("taxAmt")                  or 0),
        "vat":                  int(detail.get("vatAmt")                  or 0),
        "non_taxable_amount":   int(detail.get("taxFreeAmt")              or 0),
        "cup_deposit":          0,
        "online_delivery_fee":  int(detail.get("dlvAgncFee")              or 0),
        "note":                 _nullify(detail.get("orderMemo")),
        # ── 반품 원본 주문 참조 (반품 건에만 값 존재) ─────────
        "org_business_date":    _parse_date(detail.get("orgOperDt")),
        "org_order_seq":        _nullify(detail.get("orgBillNo")),
        "raw_data":             detail,
        "items":                [map_item(i) for i in detail.get("items", [])],
        "tenders":              [map_tender(t) for t in detail.get("tenders", [])],
    }


def map_item(item: dict) -> dict:
    return {
        "item_seq":           int(item.get("itemSeq", 0)),
        "goods_cd":           item.get("goodsCd", ""),
        "goods_nm":           item.get("goodsNm", ""),
        "app_prc":            int(item.get("appPrc")        or 0),
        "sale_qty":           int(item.get("saleQty")       or 0),
        "sale_amt":           int(item.get("saleAmt")       or 0),
        "item_dc_amt":        int(item.get("itemDcAmt")     or 0),
        "taxable_amount":     int(item.get("taxAmt")        or 0),
        "vat":                int(item.get("vatAmt")        or 0),
        "non_taxable_amount": int(item.get("taxFreeAmt")    or 0),
        "sale_except_amt":    int(item.get("saleExceptAmt") or 0),
        "sale_except_yn":     item.get("saleExceptYn", "N"),
        "packing_yn":         item.get("packingYn", "N"),
        "item_details":       item.get("itemDetails", []),
        "item_opt_details":   item.get("itemOptdetails", []),
    }


def map_tender(tender: dict) -> dict:
    return {
        "tender_seq":    int(tender.get("tenderSeq", 0)),
        "tender_cd":     tender.get("tenderCd", ""),
        "tender_nm":     tender.get("msTenderNm", ""),
        "tender_amt":    int(tender.get("tenderAmt") or 0),
        "change_amt":    int(tender.get("changeAmt") or 0),
        "pre_tender_yn": tender.get("preTenderYn", "N"),
        "return_yn":     tender.get("returnYn", "N"),
        "approval_no":   _nullify(tender.get("approvalNo")),
        "approval_dt":   _nullify(tender.get("approvalDt")),
        "pur_nm":        _nullify(tender.get("purNm")),
    }


def _payment_method(tenders: list) -> str:
    """tenders 목록에서 결제수단 요약"""
    real = {t.get("tenderCd") for t in tenders if t.get("tenderCd") not in ("IMMEDDSC", "CHANNELDSC")}
    if len(real) > 1:
        return "복합"
    if real:
        cd = next(iter(real))
        return {"PREPAID": "선결제", "CARD": "카드", "CASH": "현금"}.get(cd, cd)
    return ""


def _map_order_type(code: str | None) -> str:
    return {"D": "배달", "I": "내점", "T": "포장"}.get(code or "", code or "")


def _parse_date(val: str | None) -> str | None:
    """'20240301' → '2024-03-01', 없거나 '0'이면 None"""
    if not val or val == "0" or len(val) != 8:
        return None
    return f"{val[0:4]}-{val[4:6]}-{val[6:8]}"


def _nullify(val):
    return None if not val else val


# ── 하루치 전체 수집 ──────────────────────────────────────────
async def fetch_day(client: httpx.AsyncClient, target_date: str) -> list[dict] | None:
    """
    None 반환 = 세션 만료 감지.
    [] 반환  = 영업 없는 날.
    """
    orders = await fetch_list(client, target_date)

    if orders is None:
        return None

    if not orders:
        return []

    sem = asyncio.Semaphore(DETAIL_CONCURRENCY)
    tasks = [
        fetch_detail(client, sem, o.get("operDt", target_date), o.get("trSeq"))
        for o in orders
    ]
    details = await asyncio.gather(*tasks)

    if any(d is None for d in details):
        failed = sum(1 for d in details if d is None)
        print(f"[MATEPOS] [{target_date}] 상세 {failed}건 실패 — 세션 만료 의심")
        return None

    records = [map_sale(d) for d in details]
    print(f"[MATEPOS] [{target_date}] 상세 {len(records)}/{len(orders)}건 수집 완료")
    return records


# ── Django API 전송 ───────────────────────────────────────────
async def push_to_django(client: httpx.AsyncClient, records: list[dict]) -> dict:
    headers = {"X-Internal-Api-Key": INTERNAL_API_KEY} if INTERNAL_API_KEY else {}
    resp = await client.post(SALES_BULK_CREATE, json=records, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.json()


# ── 날짜 범위 생성 ─────────────────────────────────────────────
def date_range(start: str, end: str) -> list[str]:
    s = date(int(start[:4]), int(start[4:6]), int(start[6:8]))
    e = date(int(end[:4]),   int(end[4:6]),   int(end[6:8]))
    days, cur = [], s
    while cur <= e:
        days.append(cur.strftime("%Y%m%d"))
        cur += timedelta(days=1)
    return days


# ── 실행 진입점 (run.py 에서 호출) ───────────────────────────
async def run(start: str, end: str, dry_run: bool = False) -> dict:
    """
    반환값: { "days": int, "records": int, "errors": int, "amount": int }
    """
    if not MATEPOS_USER_ID or not MATEPOS_PASSWORD:
        raise EnvironmentError(".env 에 MATEPOS_USER_ID, MATEPOS_PASSWORD 를 설정하세요.")

    days = date_range(start, end)
    print(f"[MATEPOS] 총 {len(days)}일 처리 시작: {start} ~ {end}")

    total_records = 0
    total_errors  = 0
    total_amount  = 0   # ← 금액 합계 추가

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=20) as client:

        if not await login(client):
            raise ConnectionError("MATEPOS 로그인 실패")

        for idx, day in enumerate(days):
            # 주기적 재로그인
            if idx > 0 and idx % RELOGIN_INTERVAL == 0:
                print(f"[MATEPOS] {idx}일째 주기적 재로그인...")
                if not await login(client):
                    raise ConnectionError("MATEPOS 재로그인 실패")

            try:
                records = await fetch_day(client, day)

                if records is None:
                    if not await ensure_login(client):
                        raise ConnectionError(f"[{day}] 재로그인 실패")
                    records = await fetch_day(client, day)
                    if records is None:
                        print(f"[MATEPOS] [{day}] 재시도 실패. 스킵.")
                        total_errors += 1
                        continue

                if not records:
                    continue

                if dry_run:
                    print(f"[MATEPOS] [{day}] dry_run: {len(records)}건 (전송 생략)")
                    continue

                result = await push_to_django(client, records)
                print(f"[MATEPOS] [{day}] Django: {result}")

                total_records += len(records)
                # 하루치 금액 합산
                day_amount = sum(r.get("sale_amount", 0) for r in records)
                total_amount += day_amount

                await asyncio.sleep(0.5)

            except httpx.HTTPStatusError as e:
                print(f"[MATEPOS] [{day}] HTTP 오류: {e.response.status_code}")
                total_errors += 1
            except Exception as e:
                print(f"[MATEPOS] [{day}] 오류: {e}")
                total_errors += 1

    return {
        "days": len(days),
        "records": total_records,
        "errors": total_errors,
        "amount": total_amount
    }