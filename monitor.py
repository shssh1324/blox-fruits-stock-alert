import json
import os
import re
import hashlib
import html
from datetime import datetime, timezone
from urllib.request import Request, urlopen

STOCK_URL = "https://rbxplanet.com/game/blox-fruits/stock"
STATE_FILE = "state.json"

FRUITS = [
    "Rocket","Spin","Blade","Spring","Bomb","Smoke","Spike","Flame","Eagle","Ice","Sand","Dark",
    "Diamond","Light","Rubber","Ghost","Magma","Quake","Buddha","Love","Creation","Spider",
    "Sound","Phoenix","Portal","Lightning","Pain","Blizzard","Gravity","Mammoth","T-Rex",
    "Dough","Shadow","Venom","Gas","Spirit","Tiger","Yeti","Kitsune","Control","Dragon"
]

def get(url, timeout=20):
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/151 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    })
    with urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")

def clean(raw):
    s = re.sub(r"<!--.*?-->", " ", raw, flags=re.S)
    s = re.sub(r"<script\b.*?</script>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<style\b.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()

def parse_stock(raw):
    text = clean(raw)
    m = re.search(r"Normal\s+Stock(.*?)(?:Mirage\s+Stock)", text, re.I)
    if not m:
        raise RuntimeError("Normal Stock → Mirage Stock 구간을 찾지 못했습니다.")

    section = m.group(1)
    hits = []
    for fruit in FRUITS:
        if re.search(r"(?<![A-Za-z0-9])" + re.escape(fruit) + r"(?![A-Za-z0-9])",
                     section, re.I):
            hits.append(fruit)

    # Preserve source order, remove duplicates.
    ordered = []
    seen = set()
    for fruit in sorted(
        hits,
        key=lambda f: re.search(
            r"(?<![A-Za-z0-9])" + re.escape(f) + r"(?![A-Za-z0-9])",
            section, re.I
        ).start()
    ):
        if fruit.casefold() not in seen:
            seen.add(fruit.casefold())
            ordered.append(fruit)

    if not ordered:
        raise RuntimeError("Normal Stock에서 열매 이름을 찾지 못했습니다.")
    return ordered

def load_config():
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        cfg = {"targets": ["Kitsune"]}
    targets = cfg.get("targets", ["Kitsune"])
    targets = [str(x).strip() for x in targets if str(x).strip()]
    if not targets:
        raise RuntimeError("config.json의 targets가 비어 있습니다.")
    return targets

def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def stock_key(stock, targets):
    payload = {
        "stock": sorted(x.casefold() for x in stock),
        "targets": sorted(x.casefold() for x in targets),
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()

def discord_send(webhook, stock, found):
    if not webhook:
        raise RuntimeError("DISCORD_WEBHOOK_URL secret이 설정되지 않았습니다.")

    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    content = (
        "🚨 **Blox Fruits Stock 알림!**\n"
        f"🦊 **등장한 열매:** {', '.join(found)}\n"
        f"🏪 **Normal Stock:** {', '.join(stock)}\n"
        f"🕒 **확인 시간:** {now}"
    )

    payload = json.dumps({
        "content": content,
        "allowed_mentions": {"parse": []},
    }).encode("utf-8")

    req = Request(
        webhook,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "BloxFruitsGitHubStockAlert/1.0",
        },
    )
    with urlopen(req, timeout=20) as r:
        if r.status not in (200, 204):
            raise RuntimeError(f"Discord Webhook HTTP {r.status}")

def main():
    targets = load_config()
    raw = get(STOCK_URL)
    stock = parse_stock(raw)

    stock_cf = {x.casefold(): x for x in stock}
    found = [stock_cf[t.casefold()] for t in targets if t.casefold() in stock_cf]

    state = load_state()
    new_key = stock_key(stock, targets)
    old_key = state.get("key")

    print("Current Normal Stock:", ", ".join(stock))
    print("Targets:", ", ".join(targets))
    print("Matched:", ", ".join(found) if found else "none")

    if found and new_key != old_key:
        discord_send(os.environ.get("DISCORD_WEBHOOK_URL", ""), stock, found)
        print("Discord alert sent.")
    elif old_key == new_key:
        print("No new alert: same stock/target state.")
    else:
        print("No matching target fruit.")

    save_state({
        "key": new_key,
        "stock": stock,
        "targets": targets,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

if __name__ == "__main__":
    main()
