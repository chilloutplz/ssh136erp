# scrapers/coupang/engine.py
"""
쿠팡이츠 스크래퍼 엔진
- browser.py 로 수집
- parser.py 로 매핑
- Django API 로 전송
- run.py 에서 호출
"""
import httpx
import asyncio
import json
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).parent.parent.parent / ".env")

from .browser import fetch_coupang_orders
from .parser  import parse_orders

API_BASE          = os.getenv("API_BASE", "http://localhost:8000/api").rstrip("/")
DELIVERY_BULK_URL = f"{API_BASE}/sales/delivery/bulk-create/"


# ── Django 전송 ───────────────────────────────────────────────
async def push_to_django(records: list[dict]) -> dict:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(DELIVERY_BULK_URL, json=records)
        resp.raise_for_status()
        return resp.json()


# ── 에러 상세 출력 ────────────────────────────────────────────
def _print_errors(errors: list[dict], records: list[dict]) -> None:
    print()
    print("=" * 60)
    print(f"[COUPANG] 저장 실패 {len(errors)}건 상세")
    print("=" * 60)
    for err in errors:
        idx    = err.get("index")
        errs   = err.get("errors", {})
        record = records[idx] if idx < len(records) else {}
        print(f"\n  [{idx}] {record.get('order_number')}  {record.get('order_datetime')}  {record.get('pay_amount', 0):,}원")
        print(f"  에러: {json.dumps(errs, ensure_ascii=False)}")
        for field in errs:
            print(f"    {field} = {record.get(field)}")
    print("=" * 60)
    print()


# ── 날짜 형식 통일 ─────────────────────────────────────────────
def _normalize(d: str) -> str:
    d = d.replace("-", "")
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


# ── 메인 실행 함수 ────────────────────────────────────────────
async def run(start: str, end: str, dry_run: bool = False) -> dict:
    start = _normalize(start)
    end   = _normalize(end)

    print(f"[COUPANG] 수집 시작: {start} ~ {end}")

    try:
        # 1. 브라우저로 수집
        raw_list = await fetch_coupang_orders(start, end)

        if not raw_list:
            print("[COUPANG] 수집된 데이터 없음")
            return {"days": 0, "records": 0, "errors": 0}

        # 2. 파싱
        records = parse_orders(raw_list)
        print(f"[COUPANG] 파싱 완료: {len(records)}건")

        if dry_run:
            print(f"[COUPANG] dry_run: {len(records)}건 (전송 생략)")
            return {"days": 0, "records": len(records), "errors": 0}

        # 3. Django 전송
        print(f"[COUPANG] Django 전송 시작: {len(records)}건")
        result  = await push_to_django(records)
        created = result.get("created", 0)
        updated = result.get("updated", 0)
        errors  = result.get("errors", [])

        print(
            f"[COUPANG] 전송 결과: 수집 {len(records)}건 / "
            f"저장 {created + updated}건 (신규 {created} / 업데이트 {updated}) / "
            f"실패 {len(errors)}건"
        )

        if errors:
            _print_errors(errors, records)

        return {
            "days":    0,
            "records": created + updated,
            "errors":  len(errors),
        }

    except Exception as e:
        print(f"[COUPANG] 오류: {e}")
        return {"days": 0, "records": 0, "errors": 1}