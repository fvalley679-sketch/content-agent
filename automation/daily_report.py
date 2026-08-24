"""
Daily Content Agent Report
Pulls fresh Instagram data via Apify, computes real stats, sends a report to Telegram.
Runs automatically via GitHub Actions (see .github/workflows/daily-report.yml)
"""
import os
import json
import time
import datetime
import requests

APIFY_TOKEN = os.environ["APIFY_API_TOKEN"]
TG_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TG_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

YOU = "talharao.475"
COMPETITORS = ["ahmadshahofficial1", "raiyanbuttt", "sudaisation", "thearbazarif", "mushisamagic"]
ALL_HANDLES = [YOU] + COMPETITORS

APIFY_ACTOR = "apify~instagram-scraper"

SCRIPTS = [
    {
        "title": "Reaction-only, zero-caption post",
        "based_on": "ahmadshahofficial1",
        "hook": "(No words. Just your face hearing the audio for the first time.)",
        "steps": [
            "0-1s: Trending audio starts, you're mid-scroll, unaware.",
            "1-2s: Audio hits the punch moment, your face reacts, no acting, just real.",
            "2-3s: Hard cut to black or freeze frame on your reaction."
        ],
        "caption": "😂"
    },
    {
        "title": "Drama/movie recap in your voice",
        "based_on": "mushisamagic",
        "hook": "Bacho ye jo trend chal raha hai na... wo asal mein aisa nahi hai.",
        "steps": [
            "0-3s: Hook line to camera, deadpan attitude.",
            "3-15s: Fast recap of the trending scene/plot in your words, comedic exaggeration.",
            "15-20s: Twist it, end on YOUR punchline, not the original's."
        ],
        "caption": "Ye scene dekh ke pata chala asli drama kaun hai. Tag that friend 👀"
    },
    {
        "title": "Local-flavor comedy skit",
        "based_on": "sudaisation",
        "hook": "Karachi walo, ye sirf tumhe samajh aayega.",
        "steps": [
            "0-2s: Hook line, direct to camera, confident tone.",
            "2-12s: Skit built around one very specific local situation (traffic, rickshaw, chai stall, etc).",
            "12-15s: Punchline delivered with attitude, not explanation."
        ],
        "caption": "Sirf Karachi/Lahore wale relate karenge. Prove me wrong 😤"
    },
    {
        "title": "Two-line caption + attitude punchline",
        "based_on": "thearbazarif",
        "hook": "(Visual-first, no spoken hook needed, caption does the talking.)",
        "steps": [
            "0-5s: Simple visual, you, confident pose or expression, no explanation.",
            "5-10s: Nothing more needed. Let the caption land the joke."
        ],
        "caption": "Haters will say it's fake confidence. It's not."
    },
    {
        "title": "Comment-bait direct address",
        "based_on": "sudaisation",
        "hook": "Ye us bande/bandi ke liye jo hamesha late aata hai.",
        "steps": [
            "0-2s: Direct address hook, call out a 'type of person'.",
            "2-10s: Quick relatable bit built around that person's habits.",
            "10-12s: End on direct instruction to viewer."
        ],
        "caption": "Send this to the friend who's always 30 min late 🕐"
    }
]


def run_scraper():
    """Kick off an Apify Instagram Scraper run and wait for it to finish."""
    urls = [{"url": f"https://www.instagram.com/{h}/"} for h in ALL_HANDLES]
    payload = {
        "directUrls": [u["url"] for u in urls],
        "resultsType": "posts",
        "resultsLimit": 30,
    }
    start_url = f"https://api.apify.com/v2/acts/{APIFY_ACTOR}/runs?token={APIFY_TOKEN}"
    run = requests.post(start_url, json=payload, timeout=60).json()
    run_id = run["data"]["id"]

    status_url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={APIFY_TOKEN}"
    for _ in range(60):
        time.sleep(10)
        status = requests.get(status_url, timeout=30).json()
        state = status["data"]["status"]
        if state == "SUCCEEDED":
            dataset_id = status["data"]["defaultDatasetId"]
            return dataset_id
        if state in ("FAILED", "ABORTED", "TIMED-OUT"):
            raise RuntimeError(f"Apify run failed: {state}")
    raise RuntimeError("Apify run timed out waiting for completion")


def fetch_dataset(dataset_id):
    url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={APIFY_TOKEN}&clean=true"
    return requests.get(url, timeout=60).json()


def compute_stats(posts_by_account):
    stats = {}
    for owner, posts in posts_by_account.items():
        likes = [p["likesCount"] for p in posts if p.get("likesCount", -1) >= 0]
        comments = [p["commentsCount"] for p in posts if p.get("commentsCount", -1) >= 0]
        avg_likes = round(sum(likes) / len(likes)) if likes else None
        avg_comments = round(sum(comments) / len(comments)) if comments else None
        stats[owner] = {"count": len(posts), "avg_likes": avg_likes, "avg_comments": avg_comments}
    return stats


def fmt(n):
    if n is None:
        return "hidden"
    if n >= 1000:
        return f"{n/1000:.1f}".rstrip("0").rstrip(".") + "k"
    return str(n)


def get_todays_script():
    day_of_year = datetime.date.today().timetuple().tm_yday
    return SCRIPTS[day_of_year % len(SCRIPTS)]


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=30)


def main():
    dataset_id = run_scraper()
    raw = fetch_dataset(dataset_id)

    posts_by_account = {h: [] for h in ALL_HANDLES}
    for item in raw:
        owner = item.get("ownerUsername")
        if owner in posts_by_account:
            posts_by_account[owner].append(item)

    stats = compute_stats(posts_by_account)
    ranked = sorted(
        [(h, s["avg_likes"] or -1) for h, s in stats.items()],
        key=lambda x: x[1], reverse=True
    )
    leader = ranked[0][0]
    script = get_todays_script()

    you_stats = stats.get(YOU, {})

    script_text = f"🎬 *Today's Script*\n\n"
    script_text += f"*{script['title']}*\n"
    script_text += f"_Based on @{script['based_on']}'s top posts_\n\n"
    script_text += f"*Hook (first 3 sec):*\n{script['hook']}\n\n"
    script_text += f"*Steps:*\n"
    for step in script["steps"]:
        script_text += f"- {step}\n"
    script_text += f"\n*Caption:*\n{script['caption']}"
    send_telegram(script_text)

    stats_text = f"📊 *Daily Content Report*\n@{YOU}\n\n"
    stats_text += f"*Posts scanned:* {you_stats.get('count', 0)}\n"
    stats_text += f"*Your avg likes:* {fmt(you_stats.get('avg_likes'))}\n"
    stats_text += f"*Your avg comments:* {fmt(you_stats.get('avg_comments'))}\n\n"
    stats_text += f"*Leader right now:* @{leader} ({fmt(dict(ranked)[leader])} avg likes)\n\n"
    stats_text += "Rankings:\n"
    for h, likes in ranked:
        marker = "⭐ " if h == YOU else ""
        stats_text += f"{marker}@{h}: {fmt(likes if likes >= 0 else None)}\n"
    send_telegram(stats_text)

    with open("dashboard/data.json", "w", encoding="utf-8") as f:
        json.dump({"owner_handle": YOU, "competitors": COMPETITORS, "posts_by_account": posts_by_account}, f, ensure_ascii=False)


if __name__ == "__main__":
    main()
