"""
Website Access & SEO Traffic Analytics Service.
Logs public & portal requests, detects search engine bots/crawlers,
and aggregates traffic metrics to evaluate SEO and user reach.
"""

import json
import os
import re
import threading
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = BASE_DIR / "data"
LOG_FILE = DATA_DIR / "access_logs.jsonl"
MAX_LOG_ENTRIES = 10000

_log_lock = threading.Lock()

# Known Search Engine Crawlers and SEO Bots regex patterns
BOT_PATTERNS = [
    (r"Googlebot", "Googlebot"),
    (r"Googlebot-Image", "Googlebot Image"),
    (r"Google-InspectionTool", "Google Inspection Tool"),
    (r"bingbot", "Bingbot"),
    (r"BingPreview", "Bing Preview"),
    (r"YandexBot", "YandexBot"),
    (r"DuckDuckBot", "DuckDuckBot"),
    (r"Baiduspider", "Baiduspider"),
    (r"Sogou", "Sogou"),
    (r"Slurp", "Yahoo Slurp"),
    (r"facebookexternalhit", "Facebook Bot"),
    (r"Twitterbot", "Twitterbot"),
    (r"LinkedInBot", "LinkedInBot"),
    (r"WhatsApp", "WhatsApp Preview"),
    (r"TelegramBot", "TelegramBot"),
    (r"Applebot", "Applebot"),
    (r"AhrefsBot", "AhrefsBot"),
    (r"SemrushBot", "SemrushBot"),
    (r"MJ12bot", "MJ12bot"),
    (r"bot|crawler|spider|scraper", "Generic Crawler/Bot"),
]


def detect_bot(user_agent: str) -> Optional[str]:
    """Detect if User-Agent belongs to a search engine crawler or bot."""
    if not user_agent:
        return None
    for pattern, name in BOT_PATTERNS:
        if re.search(pattern, user_agent, re.IGNORECASE):
            return name
    return None


def record_request(
    method: str,
    path: str,
    client_ip: str,
    user_agent: str,
    referer: str = "",
    status_code: int = 200,
    duration_ms: float = 0.0,
):
    """
    Append an HTTP request event to access_logs.jsonl.
    Filters out high-frequency internal polling to keep metrics actionable.
    """
    # Skip noisy static assets or webcam streaming pings
    if path.startswith(("/static/", "/data/faces/", "/favicon.ico")) and status_code == 200:
        return
    if "/stream/ping" in path or "/health" in path:
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    bot_name = detect_bot(user_agent)

    entry = {
        "timestamp": datetime.now().isoformat(),
        "method": method,
        "path": path,
        "ip": client_ip or "127.0.0.1",
        "user_agent": user_agent[:250] if user_agent else "",
        "referer": referer[:200] if referer else "",
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
        "is_crawler": bool(bot_name),
        "bot_name": bot_name,
    }

    try:
        with _log_lock:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        # Non-blocking logging failure fallback
        pass


def get_traffic_summary() -> Dict[str, Any]:
    """
    Reads access_logs.jsonl and computes comprehensive SEO & traffic metrics.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not LOG_FILE.exists():
        return _empty_summary()

    entries: List[Dict[str, Any]] = []
    try:
        with _log_lock:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except Exception:
                            continue
    except Exception:
        return _empty_summary()

    if not entries:
        return _empty_summary()

    total_requests = len(entries)
    now = datetime.now()
    cutoff_24h = now - timedelta(hours=24)
    cutoff_7d = now - timedelta(days=7)

    requests_24h = 0
    requests_7d = 0
    unique_ips = set()
    unique_ips_24h = set()

    bot_count = 0
    bot_counter = Counter()
    path_counter = Counter()
    status_counter = Counter()
    referrer_counter = Counter()
    daily_traffic = Counter()

    for entry in entries:
        ip = entry.get("ip", "")
        path = entry.get("path", "")
        status = entry.get("status_code", 200)
        ref = entry.get("referer", "")
        is_bot = entry.get("is_crawler", False)
        bot_name = entry.get("bot_name")

        unique_ips.add(ip)
        path_counter[path] += 1
        status_counter[str(status)] += 1

        if is_bot:
            bot_count += 1
            bot_counter[bot_name or "Crawler"] += 1

        # Referrer classification
        if not ref or ref == "-":
            referrer_counter["Direct / Bookmark"] += 1
        elif "google." in ref:
            referrer_counter["Google Search"] += 1
        elif "bing." in ref:
            referrer_counter["Bing Search"] += 1
        elif any(s in ref for s in ["linkedin.com", "t.co", "twitter.com", "facebook.com", "instagram.com"]):
            referrer_counter["Social Media"] += 1
        else:
            referrer_counter["Other Referral"] += 1

        # Time-based aggregations
        ts_str = entry.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_str)
            date_key = ts.strftime("%Y-%m-%d")
            daily_traffic[date_key] += 1

            if ts >= cutoff_24h:
                requests_24h += 1
                unique_ips_24h.add(ip)
            if ts >= cutoff_7d:
                requests_7d += 1
        except Exception:
            pass

    # Top visited endpoints
    top_pages = [
        {"path": p, "views": count, "percentage": round((count / total_requests) * 100, 1)}
        for p, count in path_counter.most_common(10)
    ]

    # Top search bots
    top_bots = [
        {"bot": b, "hits": count}
        for b, count in bot_counter.most_common(5)
    ]

    # Top referrers
    top_referrers = [
        {"source": src, "visits": count, "percentage": round((count / total_requests) * 100, 1)}
        for src, count in referrer_counter.most_common(6)
    ]

    # Recent 40 log events (newest first)
    recent_events = entries[-40:][::-1]

    # Fill last 7 days chart data
    chart_labels = []
    chart_values = []
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        display_label = (now - timedelta(days=i)).strftime("%b %d")
        chart_labels.append(display_label)
        chart_values.append(daily_traffic.get(day, 0))

    return {
        "total_requests": total_requests,
        "requests_24h": requests_24h,
        "requests_7d": requests_7d,
        "unique_visitors": len(unique_ips),
        "unique_visitors_24h": len(unique_ips_24h),
        "crawler_hits": bot_count,
        "human_visits": max(0, total_requests - bot_count),
        "status_distribution": dict(status_counter),
        "top_pages": top_pages,
        "top_bots": top_bots,
        "top_referrers": top_referrers,
        "chart_labels": chart_labels,
        "chart_values": chart_values,
        "recent_logs": recent_events,
    }


def clear_traffic_logs():
    """Purge access log records."""
    try:
        with _log_lock:
            if LOG_FILE.exists():
                with open(LOG_FILE, "w", encoding="utf-8") as f:
                    f.write("")
    except Exception as e:
        pass


def _empty_summary() -> Dict[str, Any]:
    now = datetime.now()
    chart_labels = [(now - timedelta(days=i)).strftime("%b %d") for i in range(6, -1, -1)]
    return {
        "total_requests": 0,
        "requests_24h": 0,
        "requests_7d": 0,
        "unique_visitors": 0,
        "unique_visitors_24h": 0,
        "crawler_hits": 0,
        "human_visits": 0,
        "status_distribution": {"200": 0},
        "top_pages": [],
        "top_bots": [],
        "top_referrers": [],
        "chart_labels": chart_labels,
        "chart_values": [0] * 7,
        "recent_logs": [],
    }
