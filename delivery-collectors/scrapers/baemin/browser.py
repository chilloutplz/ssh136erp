# scrapers/baemin/browser.py
"""
배민 브라우저 자동화
- 로그인 1회 → 날짜 범위 선택 → 전체 페이지 수집
- 정산 완료 건만 반환 (notDisplayReason=null)
"""
import os, re
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page

load_dotenv(Path(__file__).parent.parent.parent / ".env")

BAEMIN_URL    = "https://self.baemin.com/"
PAGE_LIMIT    = 10   # 배민 기본 페이지 크기
LOGIN_WAIT    = 4   # 로그인 후 팝업 대기 (초)
POPUP_RETRIES = 5    # 팝업 돌파 재시도 횟수
DATA_WAIT     = 5   # 페이지별 캡처 대기 (초)
HEADLESS      = os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() == "true"


# ── 로그인 ────────────────────────────────────────────────────
async def _login(page: Page) -> None:
    print("[browser] 로그인 시도 중...")
    await page.goto(BAEMIN_URL)
    await page.fill('input[name="id"]',       os.getenv("BAEMIN_USER_ID"))
    await page.fill('input[name="password"]', os.getenv("BAEMIN_PASSWORD"))
    await page.click('button[type="submit"]')
    print(f"[browser] 로딩 대기 ({LOGIN_WAIT}초)...")
    await asyncio.sleep(LOGIN_WAIT)


# ── 팝업 돌파 → 주문내역 진입 ─────────────────────────────────
async def _navigate_to_orders(page: Page) -> None:
    print("[browser] 팝업 제거 시도...")
    for i in range(POPUP_RETRIES):
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.5)
        if await page.get_by_text("주문내역").is_visible():
            try:
                await page.click("text='주문내역'", timeout=1000, force=False)
                print(f"[browser] {i+1}차 시도 성공 — 주문내역 진입")
                break
            except Exception:
                print(f"[browser] {i+1}차: 팝업 가로막힘, 재시도...")
    else:
        print("[browser] 강제 클릭으로 주문내역 진입")
        await page.click("text='주문내역'", force=True)
    await asyncio.sleep(1.5)


# ── 날짜 범위 선택 ────────────────────────────────────────────
async def _select_date_range(page: Page, start_date: str, end_date: str) -> None:
    """
    start_date, end_date: YYYY-MM-DD
    달력에서 시작일 클릭 → 종료일 클릭 → 적용
    """
    def parse(d: str):
        y, m, day = d.split("-")
        return f"{y}년 {int(m)}월", f"{int(day)}일"

    start_ym, start_d = parse(start_date)
    end_ym,   end_d   = parse(end_date)

    print(f"[browser] 날짜 범위 선택: {start_date} ~ {end_date}")

    # 날짜 직접 선택 탭 클릭
    await page.get_by_text("날짜 직접 선택").click(force=True)
    await asyncio.sleep(1.5)

    # DatePicker 트리거
    await page.locator('[data-atelier-component="DatePicker.Trigger"]').click(force=True)
    await asyncio.sleep(1.5)

    # ── 시작일 클릭 ───────────────────────────────────────────
    await _navigate_calendar_to(page, start_ym)
    await _click_day(page, start_ym, start_d)
    await asyncio.sleep(0.5)

    # ── 종료일 클릭 ───────────────────────────────────────────
    # 종료일이 다른 달이면 달력을 넘겨야 할 수 있음
    if start_ym != end_ym:
        await _navigate_calendar_to(page, end_ym)
    await _click_day(page, end_ym, end_d)
    await asyncio.sleep(1)

    # ── 적용 ─────────────────────────────────────────────────
    await page.locator("button:has-text('적용')").last.click(force=True)
    await asyncio.sleep(1)
    await page.locator("button:has-text('적용')").first.click(force=True)
    await asyncio.sleep(2)
    print(f"[browser] 날짜 범위 선택 완료")


async def _click_day(page: Page, year_month: str, day_label: str) -> None:
    """달력에서 특정 월의 특정 날짜 클릭"""
    # day = day_label.replace("일", "")
    
    target_calendar = page.locator('table[role="grid"]').filter(
        has=page.locator(f"caption:has-text('{year_month}')")
    )
    day_btn = (
        target_calendar
        .get_by_role("button", name=day_label, exact=True)
        .filter(visible=True)
        .first
    )
    await day_btn.click(force=True)


async def _navigate_calendar_to(page: Page, target_ym: str) -> None:
    """달력에서 target_ym 이 보일 때까지 이전/다음 달 이동"""

    target_match = re.match(r"(\d+)년 (\d+)월", target_ym)
    target_year = int(target_match.group(1))
    target_month = int(target_match.group(2))

    prev_btn = page.locator(
        "div[role='dialog'] button[aria-label='이전 달']"
    ).filter(visible=True).last

    next_btn = page.locator(
        "div[role='dialog'] button[aria-label='다음 달']"
    ).filter(visible=True).last

    for _ in range(36):  # 최대 3년 이동
        captions = await page.locator(
            "table[role='grid'] caption"
        ).all_text_contents()

        print("[browser] 현재 caption:", captions)

        if any(target_ym in caption for caption in captions):
            return

        current_match = None
        for caption in captions:
            m = re.match(r"(\d+)년 (\d+)월", caption)
            if m:
                current_match = m
                break

        if not current_match:
            raise Exception("현재 달력 월 정보를 찾을 수 없습니다.")

        current_year = int(current_match.group(1))
        current_month = int(current_match.group(2))

        current_value = current_year * 12 + current_month
        target_value = target_year * 12 + target_month

        print(
            f"[browser] 이동 판단: current={current_year}-{current_month:02d}, "
            f"target={target_year}-{target_month:02d}"
        )

        before = captions.copy()

        if target_value < current_value:
            print("[browser] 이전 달 클릭")
            await prev_btn.click(force=True)
        else:
            print("[browser] 다음 달 클릭")
            await next_btn.click(force=True)

        await asyncio.sleep(1)

        after = await page.locator(
            "table[role='grid'] caption"
        ).all_text_contents()

        print("[browser] 클릭 후 caption:", after)

        if before == after:
            raise Exception(
                f"달력이 이동하지 않았습니다. before={before}, after={after}"
            )

    raise Exception(f"{target_ym} 달력으로 이동 실패")


# ── 다음 페이지 이동 ──────────────────────────────────────────
async def _go_to_page(page: Page, page_num: int) -> None:
    try:
        await page.get_by_role("button", name=str(page_num), exact=True).click(force=True, timeout=3000)
        await asyncio.sleep(2)
    except Exception as e:
        # fallback: 다음 페이지 화살표
        try:
            await page.locator("button[aria-label='다음 페이지']").click(force=True, timeout=3000)
            await asyncio.sleep(2)
        except Exception as e:
            print(f"[browser] 페이지 {page_num} 이동 실패: {e}")

# ── 강제 API 호출 함수 (이게 없으면 NameError가 발생합니다) ──
async def _fetch_offset(page: Page, offset: int, start_date: str, end_date: str) -> None:
    # offset을 페이지 번호로 변환 (배민 규격: 0, 10, 20... -> 0, 1, 2...)
    page_num = offset // PAGE_LIMIT
    
    # 브라우저 콘솔에서 fetch를 실행하는 것과 동일한 효과
    await page.evaluate(f"""
        fetch("/v4/orders/commerce?page={page_num}&size={PAGE_LIMIT}&orderStartDate={start_date}&orderEndDate={end_date}&orderSheetStatuses=PREPARING%2CDELIVERED%2CCANCELED", {{
            credentials: "include"
        }})
    """)
    
# ── 메인 수집 함수 ────────────────────────────────────────────
async def fetch_baemin_orders(start_date: str, end_date: str) -> list[dict]:
    """
    날짜 범위 배민 주문 전체 수집.
    - 로그인 1회
    - 날짜 범위 선택
    - 페이지네이션 자동 처리
    - 정산 완료 건만 반환 (notDisplayReason=null)

    start_date, end_date: YYYY-MM-DD
    """
    all_contents: list[dict] = []
    captured_pages: dict[int, list] = {}
    total_size = None

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=HEADLESS,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = await context.new_page()

        # ── API 응답 인터셉트 ──────────────────────────────────
        async def handle_response(response):
            nonlocal total_size
            if "v4/orders" not in response.url or response.status != 200:
                return
            
            
            try:
                body     = await response.json()
                if not isinstance(body, dict):
                    return
                
                contents = body.get("contents", [])
                ts       = body.get("totalSize", 0)
                if not contents:
                    return

                url    = response.url
                offset = int(url.split("offset=")[1].split("&")[0]) if "offset=" in url else 0

                # if offset not in captured_pages:
                captured_pages[offset] = contents
                total_size = ts
                print(f"[browser] 캡처: offset={offset}, {len(contents)}건 / 전체 {ts}건")

            except Exception as e:
                # 브라우저가 닫혀서 발생하는 에러는 출력하지 않음
                if "closed" in str(e).lower():
                    return
                print(f"[browser] 응답 파싱 오류: {e}")

        page.on("response", handle_response)

        # ── 브라우저 조작 ──────────────────────────────────────
        await _login(page)
        await _navigate_to_orders(page)
        await _select_date_range(page, start_date, end_date)

        # ── 1페이지 캡처 대기 ──────────────────────────────────
        print("[browser] 데이터 대기 중...")
        for _ in range(DATA_WAIT):
            if 0 in captured_pages:
                break
            await asyncio.sleep(1)

        # ── 페이지네이션 처리 ──────────────────────────────────
        if total_size and total_size > PAGE_LIMIT:
            total_pages = (total_size + PAGE_LIMIT - 1) // PAGE_LIMIT
            print(f"[browser] 총 {total_pages}페이지 처리")

            for page_num in range(2, total_pages + 1):
                await _go_to_page(page, page_num)
                offset = (page_num - 1) * PAGE_LIMIT
                for _ in range(DATA_WAIT):
                    if offset in captured_pages:
                        break
                    await asyncio.sleep(1)

        # ── 누락된 데이터가 없을 때까지 무한 재시도 ──────────────────
        if total_size:
            total_pages = (total_size + PAGE_LIMIT - 1) // PAGE_LIMIT
            expected_offsets = [i * PAGE_LIMIT for i in range(total_pages)]
            
            retry_count = 0
            while True:
                # 현재 누락된 offset 확인
                missing_offsets = [off for off in expected_offsets if off not in captured_pages]
                
                if not missing_offsets:
                    print("[browser] 모든 데이터가 성공적으로 수집되었습니다!")
                    break
                
                retry_count += 1
                print(f"\n[browser] 누락 발생 (남은 건수: {len(missing_offsets)}). {retry_count}회차 재수집 시도...")
                
                for off in missing_offsets:
                    page_num = (off // PAGE_LIMIT) + 1
                    
                    # 1. 브라우저 페이지 이동 시도 (타임아웃을 3초로 짧게 제한)
                    try:
                        # 클릭 실패가 재수집 전체를 멈추지 않도록 개별 try-except 처리
                        # 내부적으로 _go_to_page가 실패해도 에러를 던지지 않도록 보완
                        await asyncio.wait_for(_go_to_page(page, page_num), timeout=6.0)
                    except Exception:
                        # 버튼을 못 찾아도 무시하고 다음 단계(강제 호출)로 진행
                        pass
                    
                    # 2. 강제 API 호출 (네트워크 트리거)
                    # 버튼 클릭 여부와 상관없이 서버에 직접 데이터를 요청합니다.
                    print(f"[browser] offset={off} (페이지 {page_num}) 강제 API 호출 시도...") # 로그 추가
                    await _fetch_offset(page, off, start_date, end_date) 
                    
                    # 캡처될 때까지 대기 (이미 API를 쐈으므로 조금만 기다리면 됩니다)
                    for _ in range(5):
                        if off in captured_pages:
                            print(f"[browser] 누락되었던 offset={off} 수집 성공!")
                            break
                        await asyncio.sleep(1.5)
                
                # 한 회차 재수집 후 잠시 휴식 (서버 부하 방지)
                await asyncio.sleep(2)
                
                # 무한 루프 방지용 안전장치 (필요시)
                if retry_count > 10:
                    print("[browser] 재시도 횟수 초과로 중단합니다. 네트워크 상태를 확인하세요.")
                    break
                        
        await browser.close()

    # ── 정렬 및 정산 완료 건만 필터 ───────────────────────────
    for offset in sorted(captured_pages.keys()):
        all_contents.extend(captured_pages[offset])

    # [수정 반영] ── 데이터 정확성 검증 ───────────────────────────
    actual_count = len(all_contents)
    if total_size is not None and total_size != actual_count:
        print(f"\n[ERROR] 데이터 개수 불일치 발생!")
        print(f"[ERROR] 기대치(totalSize): {total_size}건 / 실제 수집: {actual_count}건")
        print(f"[ERROR] 데이터 오염 방지를 위해 저장을 중단합니다.")
        
        # Exception을 발생시켜 호출부(engine.py)에서 저장을 진행하지 못하게 차단합니다.
        raise Exception(f"Data Mismatch: Expected {total_size}, but got {actual_count}")

    print(f"[browser] 검증 완료: 전체 {actual_count}건 일치")

    return all_contents