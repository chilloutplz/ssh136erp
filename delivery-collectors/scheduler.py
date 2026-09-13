"""
스크래퍼 스케줄러 실행 진입점
- 기본: python scheduler.py        → 매일 새벽 2시 자동 실행 (컨테이너 상시 실행)
- 즉시 실행: python scheduler.py --now → 전날 하루치 즉시 실행
"""

import asyncio
import logging
from datetime import date, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from notifier import send_discord   # 디스코드 알림 모듈 불러오기

# ── 로깅 설정 ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
log = logging.getLogger(__name__)

# ── 스크래핑 작업 ─────────────────────────────────────────────
async def run_daily():
    """
    전날 데이터 수집.
    MATE POS → 배민 순차 실행.
    """
    yesterday = (date.today() - timedelta(days=1)).strftime("%Y%m%d")
    log.info(f"일일 스크래핑 시작: {yesterday}")

    results = {}
    errors  = []

    # ── 1. MATE POS ───────────────────────────────────────────
    try:
        log.info("[1/2] MATE POS 스크래핑 시작")
        from scrapers.matepos import run as matepos_run
        result = await matepos_run(start=yesterday, end=yesterday)
        results["matepos"] = result
        log.info(f"[1/2] MATE POS 완료: {result}")
    except Exception as e:
        log.error(f"[1/2] MATE POS 오류: {e}")
        errors.append(f"MATEPOS: {e}")

    # ── 2. 배민 ──────────────────────────────────────────────
    try:
        log.info("[2/2] 배민 스크래핑 시작")
        from scrapers.baemin import run as baemin_run
        result = await baemin_run(start=yesterday, end=yesterday)
        results["baemin"] = result
        log.info(f"[2/2] 배민 완료: {result}")
    except Exception as e:
        log.error(f"[2/2] 배민 오류: {e}")
        errors.append(f"BAEMIN: {e}")

    # ── 디스코드 알림 ─────────────────────────────────────────
    matepos = results.get("matepos", {})
    baemin  = results.get("baemin", {})

    # 플랫폼별로 각각 메시지 전송
    await send_discord("matepos", yesterday, matepos)
    await send_discord("baemin", yesterday, baemin)

    log.info("일일 스크래핑 완료")


# ── 메인 ─────────────────────────────────────────────────────
async def main():
    scheduler = AsyncIOScheduler(timezone="Asia/Seoul")

    # 매일 새벽 2시 실행
    scheduler.add_job(
        run_daily,
        CronTrigger(hour=7, minute=0, timezone="Asia/Seoul"),
        id="daily_scrape",
        name="일일 스크래핑",
        replace_existing=True,
    )

    scheduler.start()
    log.info("스케줄러 시작 — 매일 02:00 KST 실행")
    log.info(f"다음 실행: {scheduler.get_job('daily_scrape').next_run_time}")

    # 컨테이너 상시 실행 유지
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        log.info("스케줄러 종료")


if __name__ == "__main__":
    import sys
    if "--now" in sys.argv:
        asyncio.run(run_daily())
    else:
        asyncio.run(main())
