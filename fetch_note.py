import feedparser
import json
import re
import os
import urllib.request
from datetime import datetime

FEED_URL = "https://note.com/remusee/rss"
POSTS_FILE = "posts.json"
THUMB_DIR = "thumbs"

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


def extract_note_id(url):
    m = re.search(r"/n/([a-z0-9]+)", url)
    return m.group(1) if m else "unknown"


def download_thumb(cdn_url, note_id):
    """CDN URLの画像をダウンロードしてローカルパスを返す"""
    if not cdn_url:
        return ""
    os.makedirs(THUMB_DIR, exist_ok=True)

    # 拡張子を判定
    ext = "jpg"
    lower = cdn_url.lower()
    if ".png" in lower:
        ext = "png"
    elif ".webp" in lower:
        ext = "webp"
    elif ".jpeg" in lower or ".jpg" in lower:
        ext = "jpg"

    local_path = f"{THUMB_DIR}/thumb-{note_id}.{ext}"

    # すでにダウンロード済みならスキップ
    if os.path.exists(local_path):
        return local_path

    try:
        req = urllib.request.Request(
            cdn_url,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            with open(local_path, "wb") as f:
                f.write(resp.read())
        print(f"  画像保存: {local_path}")
        return local_path
    except Exception as e:
        print(f"  画像ダウンロード失敗 ({note_id}): {e}")
        return cdn_url  # 失敗したらCDN URLをそのまま使う


def load_existing():
    if os.path.exists(POSTS_FILE):
        with open(POSTS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []


def parse_date(d):
    try:
        return datetime.strptime(d, "%Y.%m.%d")
    except ValueError:
        return datetime.min


existing = load_existing()

# 既存記事でCDN URLのままのサムネをダウンロードして置換
updated = False
for p in existing:
    if p.get("thumbnail", "").startswith("http"):
        note_id = extract_note_id(p["url"])
        local = download_thumb(p["thumbnail"], note_id)
        if local != p["thumbnail"]:
            p["thumbnail"] = local
            updated = True

existing_urls = {normalize_url(p["url"]) for p in existing}

feed = feedparser.parse(FEED_URL)
new_posts = []

for entry in feed.entries:
    url = normalize_url(entry.link)
    if url in existing_urls:
        continue

    tags = [t.term for t in getattr(entry, "tags", [])]
    category = infer_category(entry.title, tags)

    # CDN URL取得（enclosure → description内のimg）
    cdn_thumb = ""
    for enc in getattr(entry, "enclosures", []):
        if enc.get("type", "").startswith("image/"):
            cdn_thumb = enc.get("url", "")
            break
    if not cdn_thumb:
        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', entry.get("summary", ""))
        if m:
            cdn_thumb = m.group(1)

    # ダウンロードしてローカルパスに変換
    note_id = extract_note_id(entry.link)
    thumb = download_thumb(cdn_thumb, note_id)

    pub = entry.get("published_parsed") or entry.get("updated_parsed")
    date_str = ""
    if pub:
        date_str = f"{pub.tm_year}.{pub.tm_mon:02d}.{pub.tm_mday:02d}"

    new_posts.append({
        "url": entry.link,
        "title": entry.title,
        "category": category,
        "date": date_str,
        "excerpt": "",
        "thumbnail": thumb,
    })
    existing_urls.add(url)

all_posts = new_posts + existing
all_posts.sort(key=lambda p: parse_date(p["date"]), reverse=True)

with open(POSTS_FILE, "w", encoding="utf-8") as f:
    json.dump(all_posts, f, ensure_ascii=False, indent=2)

print(f"新規追加: {len(new_posts)}件 / 合計: {len(all_posts)}件")
