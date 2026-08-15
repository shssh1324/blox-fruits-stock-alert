import json
import os
import re
import hashlib
import html
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen

STOCK_URL = "https://rbxplanet.com/game/blox-fruits/stock"
API_URL = "https://blox-fruits-api.onrender.com/api/bloxfruits/stock"
STATE_FILE = "state.json"

FRUITS = [
    "Rocket","Spin","Blade","Spring","Bomb","Smoke","Spike","Flame","Eagle","Ice","Sand","Dark",
    "Diamond","Light","Rubber","Ghost","Magma","Quake","Buddha","Love","Creation","Spider",
    "Sound","Phoenix","Portal","Lightning","Pain","Blizzard","Gravity","Mammoth","T-Rex",
    "Dough","Shadow","Venom","Gas","Spirit","Tiger","Yeti","Kitsune","Control","Dragon"
]

def http_get(url, timeout=35, attempts=4):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            req = Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/151 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Cache-Control": "no-cache",
                "Connection": "close",
            })
            with urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:
            last_error = e
            print(f"Attempt {attempt}/{attempts} failed for {url}: {e}")
            if attempt < attempts:
                time.sleep(3 * attempt)
    raise RuntimeError(f"Failed to fetch {url} after {attempts} attempts: {last_error}")

def clean(raw):
    s = re.sub(r"<!--.*?-->", " ", raw, flags=re.S)
    s = re.sub(r"<script\b.*?</script>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<style\b.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()

def find_fruits(section):
    positions = []
    for fruit in FRUITS:
        m = re.search(r"(?<![A-Za-z0-9])" + re.escape(fruit) + r"(?![A-Za-z0-9])", section, re.I)
        if m:
            positions.append((m.start(), fruit))
    positions.sort()
    result, seen = [], set()
    for _, fruit in positions:
        if fruit.casefold() not in seen:
            seen.add(fruit.casefold())
            result.append(fruit)
    return result

def parse_rbxplanet(raw):
    text = clean(raw)
    m = re.search(r"Normal\s+Stock(.*?)(?:Mirage\s+Stock)", text, re.I)
    if not m:
        raise RuntimeError("RBX Planet: Normal Stock → Mirage Stock 구간을 찾지 못했습니다.")
    names = find_fruits(m.group(1))
    if not names:
        raise RuntimeError("RBX Planet: Normal Stock에서 과일 이름을 찾지 못했습니다.")
    return names

def parse_api(raw):
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"API JSON 파싱 실패: {e}")
    if isinstance(data, dict) and "stock" in data:
        data = data["stock"]
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            pass
    if data in ({}, [], "", None):
        raise RuntimeError("공개 API가 빈 Stock 데이터를 반환했습니다.")
    names = find_fruits(json.dumps(data, ensure_ascii=False))
    if not names:
        raise RuntimeError("공개 API 응답에서 현재 Stock 과일을 찾지 못했습니다.")
    return names

def load_config():
    with open("config.json", "r", encoding="utf-8") as f:
        cfg = json.load(f)
    targets = [str(x).strip() for x in cfg.get("targets", []) if str(x).strip()]
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

def state_key(stock, targets):
    value = {"stock": sorted(x.casefold() for x in stock), "targets": sorted(x.casefold() for x in targets)}
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

def discord_send(webhook, stock, found):
    if not webhook:
        raise RuntimeError("DISCORD_WEBHOOK_URL secret이 없습니다.")
    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    payload = json.dumps({
        "content": (
            "🚨 **Blox Fruits Stock 알림!**\n"
            f"🦊 **등장한 열매:** {', '.join(found)}\n"
            f"🏪 **Normal Stock:** {', '.join(stock)}\n"
            f"🕒 **확인 시간:** {now}"
        ),
        "allowed_mentions": {"parse": []},
    }).encode("utf-8")
    req = Request(webhook, data=payload, method="POST", headers={
        "Content-Type": "application/json",
        "User-Agent": "BloxFruitsGitHubStockAlert/2.0",
    })
    with urlopen(req, timeout=20) as r:
        if r.status not in (200, 204):
            raise RuntimeError(f"Discord Webhook HTTP {r.status}")

def get_stock():
    errors = []
    try:
        return parse_rbxplanet(http_get(STOCK_URL, 35, 4)), "RBX Planet"
    except Exception as e:
        errors.append(f"RBX Planet: {e}")
    try:
        return parse_api(http_get(API_URL, 25, 2)), "Blox Fruits public API"
    except Exception as e:
        errors.append(f"API: {e}")
    raise RuntimeError(" / ".join(errors))

def main():
    targets = load_config()
    try:
        stock, source = get_stock()
    except Exception as e:
        print("WARNING: Stock check could not be completed.")
        print(str(e))
        print("This run will exit successfully so the next scheduled check can retry.")
        return

    lookup = {x.casefold(): x for x in stock}
    found = [lookup[t.casefold()] for t in targets if t.casefold() in lookup]
    print("Data source:", source)
    print("Current Normal Stock:", ", ".join(stock))
    print("Targets:", ", ".join(targets))
    print("Matched:", ", ".join(found) if found else "none")

    state = load_state()
    key = state_key(stock, targets)
    old_key = state.get("key")

    if found and key != old_key:
        discord_send(os.environ.get("DISCORD_WEBHOOK_URL", ""), stock, found)
        print("Discord alert sent.")
    elif key == old_key:
        print("No new alert: same stock/target state.")
    else:
        print("No matching target fruit.")

    save_state({
        "key": key,
        "stock": stock,
        "targets": targets,
        "source": source,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

if __name__ == "__main__":
    main()
