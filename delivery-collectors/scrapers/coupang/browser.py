# scrapers/coupang/browser.py
"""
쿠팡이츠 브라우저 자동화
- 실제 Chrome 사용 (개발 중 Akamai 봇 탐지 우회)
- 날짜 picker → hidden input JS 설정 → 검색 → API 응답 캡처
"""
import os
import asyncio
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page, BrowserContext

load_dotenv(Path(__file__).parent.parent.parent / ".env")

# ── 설정 ──────────────────────────────────────────────────────
LOGIN_URL      = "https://store.coupangeats.com/merchant/login"
STORE_ID       = os.getenv("COUPANG_STORE_ID", "631104")
ORDER_PAGE_URL = f"https://store.coupangeats.com/merchant/management/orders/{STORE_ID}"
ORDER_API_PATH = "/api/v1/merchant/web/order/condition"
COOKIE_FILE    = Path(__file__).parent.parent.parent / ".coupang_cookies.json"

PAGE_SIZE  = 10
DATA_WAIT  = 10
HEADLESS   = os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() == "true"


# ── 실제 Chrome 경로 탐색 ─────────────────────────────────────
def _find_chrome() -> str:
    custom = os.getenv("CHROME_PATH", "")
    if custom and Path(custom).exists():
        return custom
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome",
    ]
    return next((c for c in candidates if Path(c).exists()), "")


# ── 날짜 → KST ms timestamp ───────────────────────────────────
def _to_kst_ms(date_str: str, end: bool = False) -> int:
    """YYYY-MM-DD → KST 기준 ms timestamp"""
    y, m, d = map(int, date_str.split("-"))
    kst = timezone(timedelta(hours=9))
    if end:
        dt = datetime(y, m, d, 23, 59, 59, tzinfo=kst)
    else:
        dt = datetime(y, m, d, 0, 0, 0, tzinfo=kst)
    return int(dt.timestamp() * 1000)


# ── 쿠키 저장/로드 ────────────────────────────────────────────
async def _save_cookies(context: BrowserContext) -> None:
    cookies = await context.cookies()
    COOKIE_FILE.write_text(json.dumps(cookies, ensure_ascii=False))
    print(f"[coupang][browser] 쿠키 저장: {len(cookies)}개")


async def _load_cookies(context: BrowserContext) -> bool:
    if not COOKIE_FILE.exists():
        return False
    try:
        cookies = json.loads(COOKIE_FILE.read_text())
        await context.add_cookies(cookies)
        print(f"[coupang][browser] 쿠키 로드: {len(cookies)}개")
        return True
    except Exception as e:
        print(f"[coupang][browser] 쿠키 로드 실패: {e}")
        return False


# ── 로그인 ────────────────────────────────────────────────────
async def _login(page: Page, context: BrowserContext) -> None:
    print("[coupang][browser] 로그인 시도 중...")
    await page.goto(LOGIN_URL)
    await page.wait_for_selector('input#loginId', state="visible", timeout=15000)

    await page.fill('input#loginId',  os.getenv("COUPANG_USER_ID", ""))
    await page.fill('input#password', os.getenv("COUPANG_PASSWORD", ""))
    await page.click('button[type="submit"]')

    try:
        await page.wait_for_url(lambda url: "login" not in url, timeout=30000)
        print("[coupang][browser] 로그인 성공")
    except Exception:
        print(f"[coupang][browser] URL 미변경 — 현재: {page.url}, 성공으로 간주")

    await _save_cookies(context)
    await asyncio.sleep(3)


# ── 세션 유효 확인 ────────────────────────────────────────────
async def _is_session_valid(page: Page) -> bool:
    try:
        await page.goto(
            ORDER_PAGE_URL,
            wait_until="domcontentloaded",
            timeout=15000
        )

        await asyncio.sleep(2)

        # ── 모든 modal/dialog 팝업 제거 ─────────────────────
        try:
            popup_selectors = [
                '[data-testid="Dialog__CloseButton"]',
                '[data-testid="unified-popup-close-button"]',
                'button[aria-label="Close"]',
                '.dialog-modal-wrapper button',
                '.modal__contents button',
            ]

            for selector in popup_selectors:
                try:
                    buttons = page.locator(selector)

                    count = await buttons.count()

                    for i in range(count):
                        btn = buttons.nth(i)

                        try:
                            if await btn.is_visible():
                                await btn.click(force=True)

                                await asyncio.sleep(0.3)

                                print(
                                    f"[coupang][browser] 팝업 닫기 성공: {selector}"
                                )

                        except:
                            pass

                except:
                    pass

            # ── 마지막 방어: modal DOM 자체 제거 ───────────
            await page.evaluate("""
            () => {
                const selectors = [
                    '.dialog-modal-wrapper',
                    '.modal__contents',
                    '[role="dialog"]',
                    '.ReactModalPortal'
                ];

                selectors.forEach(sel => {
                    document.querySelectorAll(sel).forEach(el => {
                        el.remove();
                    });
                });

                document.body.style.overflow = 'auto';
            }
            """)

            await asyncio.sleep(1)

        except Exception as e:
            print(f"[coupang][browser] 팝업 제거 실패: {e}")

        # ── 로그인 여부 확인 ───────────────────────────────
        if "login" in page.url:
            print("[coupang][browser] 세션 만료")
            return False

        print("[coupang][browser] 세션 유효")
        return True

    except Exception as e:
        print(f"[coupang][browser] 세션 확인 실패: {e}")
        return False


# ── 날짜 설정 (hidden input + React event) ────────────────────
async def _select_day(page: Page, target_date: datetime):
    month_map = {
        1: "January",
        2: "February",
        3: "March",
        4: "April",
        5: "May",
        6: "June",
        7: "July",
        8: "August",
        9: "September",
        10: "October",
        11: "November",
        12: "December",
    }

    target_caption = f"{month_map[target_date.month]} {target_date.year}"

    while True:
        caption = await page.locator(
            ".DayPicker-Caption div"
        ).inner_text()

        caption = caption.strip()

        if caption == target_caption:
            break

        current = datetime.strptime(caption, "%B %Y")
        target = datetime.strptime(target_caption, "%B %Y")

        if current < target:
            await page.locator(
                ".DayPicker-NavButton--next"
            ).click()
        else:
            await page.locator(
                ".DayPicker-NavButton--prev"
            ).click()

        await asyncio.sleep(0.5)

    aria = target_date.strftime("%a %b %d %Y")

    await page.locator(
        f'[aria-label="{aria}"]'
    ).click()

    await asyncio.sleep(0.5)

# ── 날짜 범위 선택 + 검색 ─────────────────────────────────────
async def _select_date_and_search(
    page: Page,
    start_ms: int,
    end_ms: int,
) -> None:
    # 날짜 picker 드롭다운 클릭
    await page.locator(".css-1q4nwoj").click()
    await asyncio.sleep(1)

    start_dt = datetime.fromtimestamp(start_ms / 1000)
    end_dt   = datetime.fromtimestamp(end_ms / 1000)

    # 시작일 선택
    start_input = page.locator('input[name="startDate"]')
    await start_input.locator("..").click()

    await asyncio.sleep(1)

    await _select_day(page, start_dt)

    # 종료일 선택
    end_input = page.locator('input[name="endDate"]')
    await end_input.locator("..").click()

    await asyncio.sleep(1)

    await _select_day(page, end_dt)

    # 검색 버튼 클릭
    await page.evaluate("""
    () => {
        const btn = document.querySelector(
            'button.css-casqo8'
        );

        if (btn) {
            btn.click();
        }
    }
    """)

    await asyncio.sleep(2)
    print(f"[coupang][browser] 검색 실행: {start_ms} ~ {end_ms}")


# ── 메인 수집 함수 ────────────────────────────────────────────
async def fetch_coupang_orders(start_date: str, end_date: str) -> list[dict]:
    """
    날짜 범위 쿠팡이츠 주문 전체 수집.
    start_date, end_date: YYYY-MM-DD
    """
    start_ms = _to_kst_ms(start_date, end=False)
    end_ms   = _to_kst_ms(end_date,   end=True)
    print(f"[coupang][browser] 수집 범위: {start_date} ~ {end_date}")

    captured_pages: dict[int, list] = {}
    total_elements: int | None = None

    async with async_playwright() as p:
        # ── 실제 Chrome 또는 Playwright Chromium ──────────────
        chrome_path = _find_chrome()
        if chrome_path and not HEADLESS:
            print(f"[coupang][browser] 실제 Chrome 사용: {chrome_path}")
            browser = await p.chromium.launch(
                executable_path=chrome_path,
                headless=False,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            )
        else:
            browser = await p.chromium.launch(
                headless=HEADLESS,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )

        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = await context.new_page()

        # ── 쿠키 로드 → 세션 확인 → 필요시 로그인 ────────────
        if await _load_cookies(context):
            session_ok = await _is_session_valid(page)
        else:
            session_ok = False

        if not session_ok:
            await _login(page, context)
            await page.goto(ORDER_PAGE_URL, wait_until="domcontentloaded")
            await asyncio.sleep(2)

        # ── API 응답 인터셉트 ──────────────────────────────────
        async def handle_response(response):
            nonlocal total_elements
            if ORDER_API_PATH not in response.url or response.status != 200:
                return
            try:
                body = await response.json()
                if not isinstance(body, dict):
                    return
                page_vo  = body.get("orderPageVo", {})
                contents = page_vo.get("content", [])
                total    = page_vo.get("totalElements", 0)
                page_num = page_vo.get("pageNumber", 0)

                if not contents and total == 0:
                    return

                if page_num not in captured_pages:
                    captured_pages[page_num] = contents
                total_elements = total
                print(f"[coupang][browser] 캡처: page={page_num}, {len(contents)}건 / 전체 {total}건")
            except Exception as e:
                if "closed" not in str(e).lower():
                    print(f"[coupang][browser] 응답 파싱 오류: {e}")

        page.on("response", handle_response)

        # ── 날짜 선택 + 검색 ──────────────────────────────────
        await _select_date_and_search(page, start_ms, end_ms)

        # ── 0페이지 캡처 대기 ──────────────────────────────────
        print("[coupang][browser] 데이터 대기 중...")
        for _ in range(DATA_WAIT):
            if 0 in captured_pages:
                break
            await asyncio.sleep(1)

        if 0 not in captured_pages:
            print(f"[coupang][browser] 데이터 미수신. URL: {page.url}")
            await browser.close()
            return []

        # ── 페이지네이션 ───────────────────────────────────────
        if total_elements and total_elements > PAGE_SIZE:
            total_pages = (total_elements + PAGE_SIZE - 1) // PAGE_SIZE
            print(f"[coupang][browser] 총 {total_pages}페이지 처리")

            for pg in range(1, total_pages):
                try:
                    # 페이지 번호 버튼 클릭
                    await page.locator(f"button:has-text('{pg + 1}')").first.click(force=True)
                except Exception:
                    try:
                        await page.locator("button[aria-label='다음']").first.click(force=True)
                    except Exception:
                        pass
                await asyncio.sleep(2)
                for _ in range(DATA_WAIT):
                    if pg in captured_pages:
                        break
                    await asyncio.sleep(1)

        await _save_cookies(context)
        await browser.close()

    # ── 정렬 후 반환 ──────────────────────────────────────────
    all_contents: list[dict] = []
    for pg in sorted(captured_pages.keys()):
        all_contents.extend(captured_pages[pg])

    print(f"[coupang][browser] 수집 완료: {len(all_contents)}건")
    return all_contents