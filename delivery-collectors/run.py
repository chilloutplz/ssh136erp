"""
스크래퍼 실행 진입점
- 사용: python run.py --scraper matepos --start 20240301 --end 20240331
- 하루치: python run.py --scraper matepos --start 20240301
- dry-run: python run.py --scraper matepos --start 20240301 --end 20240331 --dry-run
"""
import os
import asyncio
import argparse
import importlib
from pathlib import Path
from dotenv import load_dotenv
from notifier import send_discord

# .env 는 프로젝트 루트에 하나만 유지
load_dotenv(Path(__file__).parent / ".env")

# ── 등록된 스크래퍼 ───────────────────────────────────────────
SCRAPERS = {
    "matepos": "scrapers.matepos",
    "baemin":  "scrapers.baemin",
    "coupang": "scrapers.coupang",
}

async def main(scraper: str, start: str, end: str, dry_run: bool):
    if scraper not in SCRAPERS:
        print(f"[오류] 알 수 없는 스크래퍼: {scraper}")
        print(f"사용 가능: {', '.join(SCRAPERS.keys())}")
        return

    # end가 없으면 start와 동일하게 설정 → 하루치 처리
    if not end:
        end = start

    module = importlib.import_module(SCRAPERS[scraper])
    print(f"[run] 스크래퍼: {scraper} / {start} ~ {end} / dry_run={dry_run}")

    # 실제 스크래핑 실행
    result = await module.run(start=start, end=end, dry_run=dry_run)
    print(f"[run] 완료: {result}")

    # dry-run이 아닐 때만 디스코드 알림
    if not dry_run:
        await send_discord(scraper, start, result)

    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ssh136 스크래퍼 실행")
    parser.add_argument("--scraper", required=True, help=f"스크래퍼 선택: {', '.join(SCRAPERS.keys())}")
    parser.add_argument("--start",   required=True, help="시작일 YYYYMMDD")
    parser.add_argument("--end",     help="종료일 YYYYMMDD (생략 시 시작일과 동일)")
    parser.add_argument("--dry-run", action="store_true", help="DB 저장 없이 수신만 확인")
    args = parser.parse_args()

    asyncio.run(main(args.scraper, args.start, args.end, args.dry_run))
