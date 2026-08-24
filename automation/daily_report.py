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

IDEAS = [
    {
        "title": "Reaction-only, zero-caption post",
        "based_on": "ahmadshahofficial1",
        "angle": "React to a trending audio or clip with just your face + one emoji. Let the reaction carry it."
    },
    {
        "title": "Drama/movie recap in your voice",
        "based_on": "mushisamagic",
        "angle": "Recap a trending drama/movie scene, comedy + attitude tone, but end on YOUR punchline instead of the movie's."
    },
    {
        "title": "Local-flavor comedy skit",
        "based_on": "sudaisation",
        "angle": "A short skit built around a very local, very specific situation (something only Karachi/Lahore crowd gets)."
    },
    {
        "title": "Two-line caption + attitude punchline",
        "based_on": "thearbazarif",
        "angle": "One bold, slightly cocky one-liner as the caption. No hashtag stuffing needed."
    },
    {
        "title": "Comment-bait direct address",
        "based_on": "sudaisation",
        "angle": "End your caption or video with a direct instruction: tag someone, reply with an emoji, send to X kind of person."
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


def get_todays_idea():
    day_of_year = datetime.date.today().timetuple().tm_yday
    return IDEAS[day_of_year % len(IDEAS)]


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
    idea = get_todays_idea()

    you_stats = stats.get(YOU, {})
    text = f"📊 *Daily Content Report*\n@{YOU}\n\n"
    text += f"*Today's idea:* {idea['title']}\n"
    text += f"_Based on @{idea['based_on']}'s top posts_\n"
    text += f"{idea['angle']}\n\n"
    text += f"*Posts scanned:* {you_stats.get('count', 0)}\n"
    text += f"*Your avg likes:* {fmt(you_stats.get('avg_likes'))}\n"
    text += f"*Your avg comments:* {fmt(you_stats.get('avg_comments'))}\n\n"
    text += f"*Leader right now:* @{leader} ({fmt(dict(ranked)[leader])} avg likes)\n\n"
    text += "Rankings:\n"
    for h, likes in ranked:
        marker = "⭐ " if h == YOU else ""
        text += f"{marker}@{h}: {fmt(likes if likes >= 0 else None)}\n"
    text += "\nOpen your dashboard for the full script + this idea's hook."

    send_telegram(text)

    with open("dashboard/data.json", "w", encoding="utf-8") as f:
        json.dump({"owner_handle": YOU, "competitors": COMPETITORS, "posts_by_account": posts_by_account}, f, ensure_ascii=False)


if __name__ == "__main__":
    main()
