"""
단계별 테스트
1단계: 로그인 성공 여부
2단계: 주문 건별 리스트 수신 확인 (전체 페이지, trSeq 목록 출력)
- 사용: python test_scraper.py
- 날짜 변경: TEST_DATE 값 수정
"""
import httpx
import asyncio
from dotenv import load_dotenv
from pathlib import Path
import os
import json

load_dotenv(Path(__file__).parent.parent / ".env")

MATEPOS_BASE = "https://www.matetech.co.kr"
LOGIN_URL    = f"{MATEPOS_BASE}/login"

HQ_BRAND_ID = "100201"
MS_STR_ID   = "1020869"
SALES_URL   = f"{MATEPOS_BASE}/api/sal0011/brands/{HQ_BRAND_ID}/stores/{MS_STR_ID}/sales/orders"

MATEPOS_USER_ID  = os.getenv("MATEPOS_USER_ID")
MATEPOS_PASSWORD = os.getenv("MATEPOS_PASSWORD")

# ── 확인할 날짜 ───────────────────────────────────────────────
TEST_DATE = "20240622"

HEADERS = {
    "Accept":           "application/json, text/javascript, */*; q=0.01",
    "Accept-Language":  "ko-KR,ko;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
    "Referer":          f"{MATEPOS_BASE}/service/saa0010/sales/analysis/term-orders",
}

BASE_PARAMS = {
    "hqBrandId":      HQ_BRAND_ID,
    "msStrId":        MS_STR_ID,
    "strType":        "ONLY",
    "salesTermType":  "DAILY",
    "searchDate":     "oper",
    "orderTodayFlag": "N",
    "enpCd":          "mp_bnature",
    "corpCd":         "1001",
    "brandCd":        "20001",
    "onlineYn":       "",
    "orderType":      "",
    "returnYn":       "",
    "size":           20,
}


async def test():
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=20) as client:

        # ── 1단계: 로그인 ─────────────────────────────────────
        print("=" * 50)
        print("[1단계] 로그인 테스트")
        print("=" * 50)

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

        print(f"status code : {resp.status_code}")
        if resp.status_code not in (200, 302):
            print("→ 로그인 실패. 여기서 중단.")
            return
        print("→ 로그인 성공\n")

        # ── 2단계: 리스트 전체 수신 ───────────────────────────
        print("=" * 50)
        print(f"[2단계] 리스트 수신 테스트 — {TEST_DATE}")
        print("=" * 50)

        all_content = []
        page = 1
        total_page = 1

        while True:
            params = {
                **BASE_PARAMS,
                "operDt":     TEST_DATE,
                "operDtFrom": TEST_DATE,
                "operDtTo":   TEST_DATE,
                "page":       page,
            }
            resp2 = await client.get(SALES_URL, params=params)

            try:
                body   = resp2.json()
                result = body.get("data", {}).get("result", {})
                content    = result.get("content", [])
                total_page = result.get("totalPage", 1)
                total_count = result.get("totalCount", 0)
                all_content.extend(content)
            except Exception as e:
                print(f"파싱 오류: {e}")
                print(resp2.text[:300])
                return

            if page >= total_page:
                break
            page += 1
            await asyncio.sleep(0.2)

        print(f"totalCount  : {total_count}")
        print(f"totalPage   : {total_page}")
        print(f"수신 건수   : {len(all_content)}")
        print()

        # trSeq 목록 출력
        tr_seqs = [int(o.get("trSeq", 0)) for o in all_content]
        tr_seqs.sort()
        print(f"trSeq 목록  : {tr_seqs}")

        # 빠진 seq 찾기
        if tr_seqs:
            expected = set(range(min(tr_seqs), max(tr_seqs) + 1))
            missing  = sorted(expected - set(tr_seqs))
            if missing:
                print(f"빠진 seq    : {missing}")
            else:
                print("빠진 seq    : 없음")

        print()
        print("── 건별 요약 ─────────────────────────────────────")
        print(f"{'seq':>4}  {'채널':<10}  {'취소':^4}  {'반품':^4}  {'실매출':>10}")
        print("-" * 45)
        for o in sorted(all_content, key=lambda x: int(x.get("trSeq", 0))):
            print(
                f"{int(o.get('trSeq', 0)):>4}  "
                f"{o.get('channelCd', '')::<10}  "
                f"{o.get('cancelYn', ''):^4}  "
                f"{o.get('returnYn', ''):^4}  "
                f"{int(o.get('actualSaleAmt', 0) or 0):>10,}"
            )


if __name__ == "__main__":
    asyncio.run(test())