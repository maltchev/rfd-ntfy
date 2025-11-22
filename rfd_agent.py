import feedparser
import requests
import time
import os
import re
import json

# --- CONFIGURATION ---
RSS_URL = "https://forums.redflagdeals.com/feed/forum/9"
NTFY_TOPIC = "rfd-hotdeals"
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"
HISTORY_FILE = "last_seen_id.txt"

# Remember the last 150 threads to ensure we ignore "bumped" old deals
MAX_HISTORY = 150

URGENT_KEYWORDS = ["price error", "freebie", "100% off", "lava hot"]
IGNORE_KEYWORDS = ["sold out", "oos", "expired"]

def get_thread_id(link):
    """
    Extracts the unique thread ID (t=XXXXX) from the URL.
    """
    match = re.search(r't=(\d+)', link)
    if match:
        return match.group(1)
    return link # Fallback

def get_history():
    """
    Loads the list of seen thread IDs.
    Handles migration from the old single-line file to the new JSON list.
    """
    if not os.path.exists(HISTORY_FILE):
        return []
    
    with open(HISTORY_FILE, "r") as f:
        content = f.read().strip()
        if not content: return []
        
        try:
            # Try to load as a JSON list
            return json.loads(content)
        except json.JSONDecodeError:
            # Fallback: Old format was a single URL string
            old_id = get_thread_id(content)
            return [old_id]

def save_history(seen_ids):
    """
    Saves the list of seen IDs, keeping only the most recent MAX_HISTORY.
    """
    if len(seen_ids) > MAX_HISTORY:
        seen_ids = seen_ids[-MAX_HISTORY:]
        
    with open(HISTORY_FILE, "w") as f:
        json.dump(seen_ids, f)

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
            print(f"Ignored (Filter): {title}")
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
    print(f"Checking {RSS_URL}...")
    feed = feedparser.parse(RSS_URL)
    
    if not feed.entries: 
        return

    seen_ids = get_history()
    
    # First run with new logic? Initialize cleanly.
    if not seen_ids:
        print("Initializing new history format...")
        for entry in feed.entries:
            t_id = get_thread_id(entry.link)
            seen_ids.append(t_id)
        save_history(seen_ids)
        return

    new_entries = []
    
    for entry in feed.entries:
        t_id = get_thread_id(entry.link)
        
        # IF the ID is in our history list, skip it (it's a bump)
        if t_id in seen_ids:
            continue
            
        new_entries.append(entry)

    # Cap at 5 to prevent flood
    if len(new_entries) > 5:
        new_entries = new_entries[:5]

    # Send oldest first
    for entry in reversed(new_entries):
        send_notification(entry.title, entry.link)
        
        t_id = get_thread_id(entry.link)
        seen_ids.append(t_id)
        time.sleep(1)

    save_history(seen_ids)

if __name__ == "__main__":
    check_feed()
