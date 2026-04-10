import asyncio
from playwright.async_api import async_playwright
from backend.utils import get_logger

logger = get_logger("BrowserAgent")

# Global reference to keep browser alive across calls if needed
_browser = None
_playwright = None

async def play_youtube_video(search_query: str):
    """
    Automates opening YouTube, searching for a video, and clicking the first result.
    """
    try:
        async with async_playwright() as p:
            # We launch headless=False so the user can see it
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            
            logger.info(f"Opening YouTube for: {search_query}")
            await page.goto("https://www.youtube.com")
            
            # Type search query
            await page.fill('input#search', search_query)
            await page.press('input#search', 'Enter')
            
            # Wait for results
            await page.wait_for_selector('ytd-video-renderer')
            
            # Click first video
            videos = await page.query_selector_all('ytd-video-renderer a#video-title')
            if videos:
                await videos[0].click()
                logger.info(f"Playing video: {search_query}")
                
                # Sleep briefly to let it load, then we close context. 
                # In a full desktop app, you'd manage the browser process explicitly.
                await asyncio.sleep(5)
            else:
                logger.warning("No YouTube results found.")
    except Exception as e:
        logger.error(f"Browser Agent error: {e}")

async def open_and_interact(url: str, selector_to_click: str = None):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            await page.goto(url)
            if selector_to_click:
                await page.click(selector_to_click)
            await asyncio.sleep(5)
    except Exception as e:
        logger.error(f"Browser interaction error: {e}")
