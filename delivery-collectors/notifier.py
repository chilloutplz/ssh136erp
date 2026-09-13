import os
import httpx
import logging
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")

log = logging.getLogger(__name__)
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

async def send_discord(scraper: str, start: str, result: dict):
    """디스코드 웹훅으로 알림 전송"""
    if not DISCORD_WEBHOOK_URL:
        log.warning("DISCORD_WEBHOOK_URL 미설정 — 알림 건너뜀")
        return

    kst = timezone(timedelta(hours=9))
    now_kst = datetime.now(timezone.utc).astimezone(kst)
    time_str = now_kst.strftime('%Y-%m-%d %H:%M:%S')

    records_count = result.get('records', 0)
    errors        = result.get('errors', [])

    # ── 플랫폼별 메시지 ────────────────────────────────
    if scraper == "matepos":
        total_amount = result.get('amount', 0)
        content = (
            f"🏪 **[POS 매출 업로드 완료]**\n"
            f"📅 대상 날짜: `{start}`\n"
            f"📊 등록 건수: `{records_count}건`\n"
            f"💰 총 매출액: `{total_amount:,}원`\n"
            f"⏰ 완료 시각: {time_str} (KST)"
        )

    elif scraper == "baemin":
        pay_amount     = result.get('amount', 0)
        deposit_amount = result.get('deposit_amount', 0)
        deposit_date   = result.get('deposit_date')
        content = (
            f"🛵 **[배민 매출 업로드 완료]**\n"
            f"📅 대상 날짜: `{start}`\n"
            f"📊 등록 건수: `{records_count}건`\n"
            f"💰 결제액 합계: `{pay_amount:,}원`\n"
            f"💵 입금예정금액: `{deposit_amount:,}원`\n"
            f"📆 가장 가까운 입금예정일: `{deposit_date or '없음'}`\n"
            f"⏰ 완료 시각: {time_str} (KST)"
        )

    else:
        # 기본 포맷
        content = (
            f"📊 **[{scraper.upper()} 매출 업로드 완료]**\n"
            f"📅 대상 날짜: `{start}`\n"
            f"📊 등록 건수: `{records_count}건`\n"
            f"⏰ 완료 시각: {time_str} (KST)"
        )

    if errors:
        # 1. errors가 문자열 리스트일 때 (기존 로직 유지)
        if isinstance(errors, list):
            content += "\n❌ 오류:\n" + "\n".join(str(e) for e in errors)
        # 2. errors가 숫자형(int)이거나 단건일 때
        else:
            content += f"\n❌ 오류 발생 건수: {errors}건"

    try:
        async with httpx.AsyncClient() as client:
            await client.post(DISCORD_WEBHOOK_URL, json={"content": content})
            log.info(f"디스코드 메시지 전송 완료 ({scraper})")
    except Exception as e:
        log.error(f"디스코드 전송 실패 ({scraper}): {e}")
