import json
import os
import re
import hashlib
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen

STATE_FILE = "state.json"

SOURCES = [
    ("Jina → RBX Planet", "https://r.jina.ai/https://rbxplanet.com/game/blox-fruits/stock"),
    ("Jina → BloxInformer", "https://r.jina.ai/https://bloxinformer.com/blox-fruits-stock/"),
]

FRUITS = [
    "Rocket","Spin","Blade","Spring","Bomb","Smoke","Spike","Flame","Eagle","Ice","Sand","Dark",
    "Diamond","Light","Rubber","Ghost","Magma","Quake","Buddha","Love","Creation","Spider",
    "Sound","Phoenix","Portal","Lightning","Pain","Blizzard","Gravity","Mammoth","T-Rex",
    "Dough","Shadow","Venom","Gas","Spirit","Tiger","Yeti","Kitsune","Control","Dragon"
]

CANONICAL = {f.casefold(): f for f in FRUITS}

def http_get(url, timeout=30, attempts=3):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            req = Request(
                url,
                headers={
                    "User-Agent": "BloxFruitsStockAlert/4.0",
                    "Accept": "text/plain,text/markdown,*/*",
                    "Cache-Control": "no-cache",
                    "X-Return-Format": "markdown",
                },
            )
            with urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:
            last_error = e
            print(f"Attempt {attempt}/{attempts} failed for {url}: {e}")
            if attempt < attempts:
                time.sleep(3 * attempt)
    raise RuntimeError(f"Failed after {attempts} attempts: {last_error}")

def normalize_heading(line):
    # Markdown heading -> plain heading text.
    # Examples:
    # "## Normal Stock" -> "Normal Stock"
    # "### Rocket" -> "Rocket"
    s = line.strip()
    s = re.sub(r"^#{1,6}\s*", "", s)
    s = re.sub(r"\s*#+\s*$", "", s)
    # Strip simple markdown links/images if ever present in a heading.
    s = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    return s.strip()

def is_heading_line(line):
    return bool(re.match(r"^\s*#{1,6}\s+\S", line))

def extract_normal_block(markdown):
    lines = markdown.splitlines()

    start = None
    end = None

    # Prefer exact Markdown heading lines.
    for i, line in enumerate(lines):
        if is_heading_line(line) and normalize_heading(line).casefold() == "normal stock":
            start = i + 1
            break

    if start is None:
        # Tolerant fallback for a plain line containing only "Normal Stock".
        for i, line in enumerate(lines):
            if normalize_heading(line).casefold() == "normal stock":
                start = i + 1
                break

    if start is None:
        raise RuntimeError("Jina 응답에서 'Normal Stock' 제목 줄을 찾지 못했습니다.")

    for i in range(start, len(lines)):
        line = lines[i]
        if is_heading_line(line) and normalize_heading(line).casefold() == "mirage stock":
            end = i
            break

    if end is None:
        # Tolerant fallback for a plain line containing only "Mirage Stock".
        for i in range(start, len(lines)):
            if normalize_heading(lines[i]).casefold() == "mirage stock":
                end = i
                break

    if end is None:
        raise RuntimeError("Jina 응답에서 'Mirage Stock' 제목 줄을 찾지 못했습니다.")

    return lines[start:end]

def parse_normal_stock(markdown):
    block_lines = extract_normal_block(markdown)

    names = []
    seen = set()

    # Primary parser:
    # RBX Planet/Jina currently exposes each fruit as a Markdown H3 such as:
    # ### Rocket
    # ### Spin
    # ### Ice
    for line in block_lines:
        if not is_heading_line(line):
            continue
        heading = normalize_heading(line)
        key = heading.casefold()
        if key in CANONICAL and key not in seen:
            seen.add(key)
            names.append(CANONICAL[key])

    # Fallback: exact fruit-only lines in case a source loses Markdown hashes.
    if not names:
        for line in block_lines:
            plain = normalize_heading(line)
            key = plain.casefold()
            if key in CANONICAL and key not in seen:
                seen.add(key)
                names.append(CANONICAL[key])

    if not names:
        sample = " | ".join(x.strip() for x in block_lines[:30] if x.strip())[:1000]
        raise RuntimeError(
            "Normal Stock 구간은 찾았지만 과일 제목을 찾지 못했습니다. "
            "Block sample: " + sample
        )

    return names

def get_stock():
    errors = []
    for label, url in SOURCES:
        try:
            print("Trying source:", label)
            markdown = http_get(url)
            stock = parse_normal_stock(markdown)
            return stock, label
        except Exception as e:
            print("Source failed:", label, e)
            errors.append(f"{label}: {e}")

    raise RuntimeError(" / ".join(errors))

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
    payload = {
        "stock": sorted(x.casefold() for x in stock),
        "targets": sorted(x.casefold() for x in targets),
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()

def discord_send(webhook, stock, found, source):
    if not webhook:
        raise RuntimeError("DISCORD_WEBHOOK_URL secret이 설정되지 않았습니다.")

    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    payload = json.dumps(
        {
            "content": (
                "🚨 **Blox Fruits Stock 알림!**\n"
                f"🦊 **등장한 열매:** {', '.join(found)}\n"
                f"🏪 **Normal Stock:** {', '.join(stock)}\n"
                f"📡 **데이터 출처:** {source}\n"
                f"🕒 **확인 시간:** {now}"
            ),
            "allowed_mentions": {"parse": []},
        }
    ).encode("utf-8")

    req = Request(
        webhook,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "BloxFruitsStockAlert/4.0",
        },
    )

    with urlopen(req, timeout=20) as r:
        if r.status not in (200, 204):
            raise RuntimeError(f"Discord Webhook HTTP {r.status}")

def main():
    targets = load_config()

    try:
        stock, source = get_stock()
    except Exception as e:
        # Don't mark the GitHub job red for a temporary source outage.
        print("WARNING: Stock check could not be completed.")
        print(str(e))
        print("The next cron-job.org trigger will try again.")
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
        discord_send(
            os.environ.get("DISCORD_WEBHOOK_URL", ""),
            stock,
            found,
            source,
        )
        print("Discord alert sent.")
    elif key == old_key:
        print("No new alert: same stock/target state.")
    else:
        print("No matching target fruit.")

    save_state(
        {
            "key": key,
            "stock": stock,
            "targets": targets,
            "source": source,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    )

if __name__ == "__main__":
    main()
