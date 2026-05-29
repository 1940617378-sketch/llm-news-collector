#!/usr/bin/env python3
import feedparser, json, hashlib, os, re, requests
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
SEEN_FILE = os.path.join(BASE_DIR, "seen.json")

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=2)

def make_id(url):
    return hashlib.md5(url.encode()).hexdigest()[:12]

def clean_summary(text):
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'Article URL:\s*https?://\S+', '', text)
    text = re.sub(r'Comments URL:\s*https?://\S+', '', text)
    text = re.sub(r'Points:\s*\d+', '', text)
    text = re.sub(r'#\s*Comments:\s*\d+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def is_relevant(title, summary, keywords):
    text = f"{title} {summary}".lower()
    return any(kw.lower() in text for kw in keywords)

def collect(config):
    seen = load_seen()
    today = datetime.now().strftime("%Y-%m-%d")
    articles = []
    for feed_url in config["rss_feeds"]:
        try:
            print(f"  Reading: {feed_url}")
            feed = feedparser.parse(feed_url)
            source_name = feed.feed.get("title", feed_url[:40])
            for entry in feed.entries:
                link = entry.get("link", "")
                if not link:
                    continue
                aid = make_id(link)
                if aid in seen:
                    continue
                title = re.sub(r'<[^>]+>', '', entry.get("title", "")).strip()
                summary = clean_summary(entry.get("summary", ""))
                if is_relevant(title, summary, config["keywords"]):
                    articles.append({
                        "title": title,
                        "link": link,
                        "source": source_name,
                        "summary": summary[:200],
                    })
                    seen[aid] = today
        except Exception as e:
            print(f"  [Error] {feed_url}: {e}")
    articles = articles[:config.get("max_articles_per_day", 20)]
    save_seen(seen)
    return articles

def save_markdown(articles):
    today = datetime.now().strftime("%Y-%m-%d")
    filename = os.path.join(BASE_DIR, f"digest_{today}.md")
    lines = [f"# LLM Daily Digest - {today}\n"]
    for i, a in enumerate(articles, 1):
        lines.append(f"### {i}. [{a['title']}]({a['link']})")
        lines.append(f"*Source: {a['source']}*\n")
        if a["summary"]:
            lines.append(f"> {a['summary']}\n")
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  Saved: digest_{today}.md")

def format_telegram(articles):
    today = datetime.now().strftime("%Y-%m-%d")
    if not articles:
        return f"No new LLM news today ({today})"
    lines = [f"LLM Daily - {today}\n"]
    for i, a in enumerate(articles, 1):
        lines.append(f"{i}. {a['title']}")
        lines.append(f"   {a['link']}")
        lines.append(f"   [{a['source']}]\n")
    lines.append(f"Total: {len(articles)} articles")
    return "\n".join(lines)

def send_telegram(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": True,
    })
    if resp.ok:
        print("  Telegram sent!")
    else:
        print(f"  Telegram failed: {resp.text}")

def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"Collecting LLM news... [{now}]")
    config = load_config()
    articles = collect(config)
    print(f"  Found {len(articles)} new articles")
    save_markdown(articles)
    token = os.environ.get("TELEGRAM_BOT_TOKEN", config.get("telegram_bot_token", ""))
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", config.get("telegram_chat_id", ""))
    if token and chat_id:
        msg = format_telegram(articles)
        send_telegram(token, chat_id, msg)
    else:
        print("  No Telegram config, skipping push")

if __name__ == "__main__":
    main()
