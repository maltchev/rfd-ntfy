import feedparser
import requests
import time
import os
import re

# --- CONFIGURATION ---
RSS_URL = "https://forums.redflagdeals.com/feed/forum/9"
# CHANGE THIS to something unique so strangers don't see your alerts!
NTFY_TOPIC = "rfd-hotdeals" 
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"
HISTORY_FILE = "last_seen_id.txt"

# Keywords that trigger a High Priority alert (Priority 5)
URGENT_KEYWORDS = ["price error", "freebie", "100% off", "lava hot"]
# Keywords to completely ignore
IGNORE_KEYWORDS = ["sold out", "oos", "expired"]

def get_last_seen_id():
    if not os.path.exists(HISTORY_FILE):
        return None
    with open(HISTORY_FILE, "r") as f:
        return f.read().strip()

def save_last_seen_id(entry_id):
    with open(HISTORY_FILE, "w") as f:
        f.write(entry_id)

def parse_title_info(title):
    retailer = "RFD"
    priority = "3"
    tags = ["money_with_wings", "canada"]
    
    match = re.match(r"^\[(.*?)\]", title)
    if match:
        retailer = match.group(1).strip()

    title_lower = title.lower()
    for kw in URGENT_KEYWORDS:
        if kw in title_lower:
            priority = "5"
            tags.append("rotating_light")
            tags.append("loudspeaker") 
            break
    return retailer, priority, tags

def send_notification(title, link):
    for kw in IGNORE_KEYWORDS:
        if kw in title.lower():
            print(f"Ignored: {title}")
            return

    retailer, priority, tags = parse_title_info(title)
    header_title = f"Deal @ {retailer}"
    if priority == "5":
        header_title = f"URGENT: {header_title}"

    headers = {
        "Title": header_title,
        "Priority": priority,
        "Tags": ",".join(tags),
        "Click": link
    }
    
    data = f"{title}\n{link}"
    try:
        requests.post(NTFY_URL, data=data.encode('utf-8'), headers=headers)
        print(f"Sent: {title}")
    except Exception as e:
        print(f"Failed: {e}")

def check_feed():
    feed = feedparser.parse(RSS_URL)
    if not feed.entries: return

    last_seen_id = get_last_seen_id()
    
    if last_seen_id is None:
        if feed.entries:
            save_last_seen_id(feed.entries[0].id)
            print("Initialized history.")
        return

    new_entries = []
    for entry in feed.entries:
        if entry.id == last_seen_id:
            break
        new_entries.append(entry)

    if len(new_entries) == len(feed.entries):
        new_entries = new_entries[:5]

    for entry in reversed(new_entries):
        send_notification(entry.title, entry.link)
        time.sleep(1)

    if new_entries:
        save_last_seen_id(new_entries[-1].id)

if __name__ == "__main__":
    check_feed()
