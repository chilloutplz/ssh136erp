# scrapers/baemin/engine.py
"""
배민 스크래퍼 엔진
- 로그인 1회 → 날짜 범위로 한 번에 수집
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

from .browser import fetch_baemin_orders
from .parser  import parse_orders

API_BASE = os.getenv("API_BASE", "http://localhost:8000/api").rstrip("/")
DELIVERY_BULK_URL = f"{API_BASE}/sales/delivery/bulk-create/"


# ── Django 전송 ───────────────────────────────────────────────
async def push_to_django(records: list[dict]) -> dict:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(DELIVERY_BULK_URL, json=records)
        resp.raise_for_status()
        return resp.json()


# ── 에러 상세 출력 ────────────────────────────────────────────
def _print_errors(errors: list[dict], records: list[dict]) -> None:
    """저장 실패 건 상세 출력"""
    print()
    print("=" * 60)
    print(f"[BAEMIN] 저장 실패 {len(errors)}건 상세")
    print("=" * 60)

    for err in errors:
        idx    = err.get("index")
        errs   = err.get("errors", {})
        record = records[idx] if idx < len(records) else {}

        order_number   = record.get("order_number", "알수없음")
        order_datetime = record.get("order_datetime", "")
        pay_amount     = record.get("pay_amount", 0)

        print(f"\n  [{idx}] {order_number}  {order_datetime}  {pay_amount:,}원")
        print(f"  에러: {json.dumps(errs, ensure_ascii=False)}")

        # 문제 필드 값 출력
        for field in errs:
            if field == "baemin_info":
                baemin_info = record.get("baemin_info", {})
                for sub_field in errs[field]:
                    print(f"    baemin_info.{sub_field} = {baemin_info.get(sub_field)}")
            else:
                print(f"    {field} = {record.get(field)}")

    print("=" * 60)
    print()


# ── 날짜 형식 통일 ─────────────────────────────────────────────
def _normalize(d: str) -> str:
    """YYYYMMDD → YYYY-MM-DD"""
    d = d.replace("-", "")
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


# ── 메인 실행 함수 (run.py 에서 호출) ────────────────────────
async def run(start: str, end: str, dry_run: bool = False) -> dict:
    start = _normalize(start)
    end   = _normalize(end)

    print(f"[BAEMIN] 수집 시작: {start} ~ {end}")

    try:
        raw_list = await fetch_baemin_orders(start, end)

        if not raw_list:
            print("[BAEMIN] 수집된 데이터 없음")
            return {"days": 0, "records": 0, "errors": 0, "amount": 0, "deposit_amount": 0, "deposit_date": None}

        records = parse_orders(raw_list)
        print(f"[BAEMIN] 파싱 완료: {len(records)}건")

        # ── 금액 합산 ───────────────────────────────────────────
        total_pay_amount     = sum(r.get("pay_amount", 0) for r in records)
        total_deposit_amount = sum(r.get("deposit_due_amount", 0) for r in records)

        # 가장 가까운 입금예정일 찾기
        deposit_dates = [r.get("deposit_due_date") for r in records if r.get("deposit_due_date")]
        nearest_date  = min(deposit_dates) if deposit_dates else None

        if dry_run:
            return {
                "days": 0,
                "records": len(records),
                "errors": 0,
                "amount": total_pay_amount,
                "deposit_amount": total_deposit_amount,
                "deposit_date": nearest_date
            }

        result = await push_to_django(records)

        created = result.get("created", 0)
        updated = result.get("updated", 0)
        errors  = result.get("errors", [])

        if errors:
            _print_errors(errors, records)

        return {
            "days": 0,
            "records": created + updated,
            "errors": len(errors),
            "amount": total_pay_amount,
            "deposit_amount": total_deposit_amount,
            "deposit_date": nearest_date
        }

    except Exception as e:
        print(f"[BAEMIN] 오류: {e}")
        return {"days": 0, "records": 0, "errors": 1, "amount": 0, "deposit_amount": 0, "deposit_date": None}