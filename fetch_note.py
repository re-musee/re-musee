import feedparser
import json
import re
import os
from datetime import datetime

FEED_URL = "https://note.com/remusee/rss"
POSTS_FILE = "posts.json"

CATEGORY_MAP = {
    "EXHIBITION": ["展覧会", "exhibition", "recommend", "展示"],
    "MEMBERS BLOG": ["メンバー", "members blog", "membersblog", "member", "日常", "大学生"],
    "EVENT": ["event", "イベント", "活動紹介", "パーティー"],
}


def infer_category(title, tags):
    text = (title + " " + " ".join(tags)).lower().replace("　", " ")
    for cat, keywords in CATEGORY_MAP.items():
        for kw in keywords:
            if kw.lower() in text:
                return cat
    return "BLOG"


def normalize_url(url):
    return url.split("?")[0]


def load_existing():
    if os.path.exists(POSTS_FILE):
        with open(POSTS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []


def parse_date(d):
    for fmt in ("%Y.%m.%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(d, fmt)
        except ValueError:
            pass
    return datetime.min


existing = load_existing()
existing_urls = {normalize_url(p["url"]) for p in existing}

feed = feedparser.parse(FEED_URL)
new_posts = []

for entry in feed.entries:
    url = normalize_url(entry.link)
    if url in existing_urls:
        continue

    tags = [t.term for t in getattr(entry, "tags", [])]
    category = infer_category(entry.title, tags)

    # サムネイル取得（enclosure → description内のimg → 空）
    thumb = ""
    for enc in getattr(entry, "enclosures", []):
        if enc.get("type", "").startswith("image/"):
            thumb = enc.get("url", "")
            break
    if not thumb:
        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', entry.get("summary", ""))
        if m:
            thumb = m.group(1)

    pub = entry.get("published_parsed") or entry.get("updated_parsed")
    date_str = ""
    if pub:
        date_str = f"{pub.tm_year}.{pub.tm_mon:02d}.{pub.tm_mday:02d}"

    new_posts.append({
        "url": entry.link,
        "title": entry.title,
        "category": category,
        "date": date_str,
        "excerpt": "",  # 文頭テキストは表示しない
        "thumbnail": thumb,
    })
    existing_urls.add(url)

all_posts = new_posts + existing
all_posts.sort(key=lambda p: parse_date(p["date"]), reverse=True)

with open(POSTS_FILE, "w", encoding="utf-8") as f:
    json.dump(all_posts, f, ensure_ascii=False, indent=2)

print(f"新規追加: {len(new_posts)}件 / 合計: {len(all_posts)}件")
