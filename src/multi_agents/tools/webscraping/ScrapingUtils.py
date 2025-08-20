# --- Generic scraping helpers for the retrieval agent (add to ScrapingUtils.py) ---

import random
import requests
from typing import Optional
from urllib.parse import urlparse

# Clean extraction
try:
    import trafilatura
except Exception:
    trafilatura = None

from playwright.sync_api import sync_playwright
from undetected_playwright import Tarnished  # you already use this stealth layer:contentReference[oaicite:4]{index=4}
from selectolax.parser import HTMLParser

# Pull your proxy settings from Config.py (server / username / password)
try:
    from multi_agents.tools.webscraping import  Config
    _PROXY = getattr(Config, "CONFIG_PROXY", None)  # {"server": "http://host:port", "username": "...", "password": "..."}
except Exception:
    _PROXY = None

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123 Safari/537.36",
]

def _clean_text(txt: Optional[str]) -> str:
    if not txt:
        return ""
    try:
        # fix common mojibake (Â, â, …) conservatively
        txt = txt.encode("latin1", errors="ignore").decode("utf-8", errors="ignore")
    except Exception:
        pass
    return txt.strip()

def _requests_proxy():
    """
    Map your Config.CONFIG_PROXY to requests proxies if present.
    Example Config value (already in your repo):
      {"server": "http://host:port", "username": "...", "password": "..."}:contentReference[oaicite:5]{index=5}
    """
    if not _PROXY or "server" not in _PROXY:
        return None
    server = _PROXY["server"]
    if _PROXY.get("username") and _PROXY.get("password"):
        url = server.replace("://", f"://{_PROXY['username']}:{_PROXY['password']}@")
    else:
        url = server
    return {"http": url, "https": url}

def fast_scrape(url: str, timeout: int = 12) -> str:
    """
    Generic fast scrape for static pages:
      - requests + UA rotation (+ your proxy)
      - trafilatura extraction (fallback to selectolax body text)
    """
    headers = {"User-Agent": random.choice(_USER_AGENTS)}
    proxies = _requests_proxy()
    try:
        r = requests.get(url, headers=headers, proxies=proxies, timeout=timeout)
        r.raise_for_status()
        html = r.text

        if trafilatura is not None:
            text = trafilatura.extract(html, url=url)
            if text:
                return _clean_text(text)

        tree = HTMLParser(html)
        body = tree.css_first("body")
        return _clean_text(body.text(separator=" ", strip=True)) if body else ""
    except Exception:
        # stay quiet; let caller try js_scrape next
        return ""

def js_scrape(url: str, timeout_ms: int = 30000, headless: bool = True) -> str:
    """
    Generic, stealthy scrape for JS-heavy pages:
      - Playwright Chromium + Tarnished stealth (you already use this):contentReference[oaicite:6]{index=6}
      - honors Config.CONFIG_PROXY directly (server/username/password):contentReference[oaicite:7]{index=7}
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context_kwargs = {}
            if _PROXY:
                context_kwargs["proxy"] = _PROXY  # pass as-is to Playwright

            context = browser.new_context(**context_kwargs)
            Tarnished.apply_stealth(context)  # stealth layer, per your original code:contentReference[oaicite:8]{index=8}
            page = context.new_page()
            page.set_default_timeout(timeout_ms)

            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle", timeout=timeout_ms)

            html = page.content()
            context.close()
            browser.close()

        if trafilatura is not None:
            text = trafilatura.extract(html, url=url)
            if text:
                return _clean_text(text)
        tree = HTMLParser(html)
        body = tree.css_first("body")
        return _clean_text(body.text(separator=" ", strip=True)) if body else ""
    except Exception:
        return ""
