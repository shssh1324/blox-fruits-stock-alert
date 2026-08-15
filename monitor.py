import json, os, re, hashlib, time
from datetime import datetime, timezone
from urllib.request import Request, urlopen

STATE_FILE = "state.json"
SOURCES = [
    ("Jina → RBX Planet", "https://r.jina.ai/https://rbxplanet.com/game/blox-fruits/stock"),
    ("Jina → BloxInformer", "https://r.jina.ai/https://bloxinformer.com/blox-fruits-stock/"),
]
FRUITS = ["Rocket","Spin","Blade","Spring","Bomb","Smoke","Spike","Flame","Eagle","Ice","Sand","Dark","Diamond","Light","Rubber","Ghost","Magma","Quake","Buddha","Love","Creation","Spider","Sound","Phoenix","Portal","Lightning","Pain","Blizzard","Gravity","Mammoth","T-Rex","Dough","Shadow","Venom","Gas","Spirit","Tiger","Yeti","Kitsune","Control","Dragon"]

def http_get(url, timeout=30, attempts=3):
    last = None
    for i in range(1, attempts+1):
        try:
            req = Request(url, headers={"User-Agent":"BloxFruitsStockAlert/3.0","Accept":"text/plain,text/markdown,*/*","Cache-Control":"no-cache","X-Return-Format":"markdown"})
            with urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8","ignore")
        except Exception as e:
            last=e
            print(f"Attempt {i}/{attempts} failed for {url}: {e}")
            if i < attempts: time.sleep(3*i)
    raise RuntimeError(f"Failed after {attempts} attempts: {last}")

def find_fruits(section):
    hits=[]
    for fruit in FRUITS:
        m=re.search(r"(?<![A-Za-z0-9])"+re.escape(fruit)+r"(?![A-Za-z0-9])",section,re.I)
        if m: hits.append((m.start(),fruit))
    hits.sort()
    out=[]; seen=set()
    for _,f in hits:
        k=f.casefold()
        if k not in seen:
            seen.add(k); out.append(f)
    return out

def parse_normal_stock(text):
    patterns=[r"Normal\s+Stock(.*?)(?:Mirage\s+Stock)",r"##+\s*Normal\s+Stock(.*?)(?:##+\s*Mirage\s+Stock)",r"\bNormal\b(.*?)(?:\bMirage\b)"]
    for p in patterns:
        m=re.search(p,text,re.I|re.S)
        if m:
            names=find_fruits(m.group(1))
            if names: return names
    raise RuntimeError("Normal Stock 영역에서 과일 이름을 찾지 못했습니다.")

def get_stock():
    errs=[]
    for label,url in SOURCES:
        try:
            print("Trying source:", label)
            return parse_normal_stock(http_get(url)), label
        except Exception as e:
            print("Source failed:", label, e)
            errs.append(f"{label}: {e}")
    raise RuntimeError(" / ".join(errs))

def load_config():
    with open("config.json","r",encoding="utf-8") as f:
        cfg=json.load(f)
    targets=[str(x).strip() for x in cfg.get("targets",[]) if str(x).strip()]
    if not targets: raise RuntimeError("config.json targets가 비어 있습니다.")
    return targets

def load_state():
    try:
        with open(STATE_FILE,"r",encoding="utf-8") as f: return json.load(f)
    except Exception: return {}

def save_state(state):
    with open(STATE_FILE,"w",encoding="utf-8") as f: json.dump(state,f,ensure_ascii=False,indent=2)

def state_key(stock,targets):
    payload={"stock":sorted(x.casefold() for x in stock),"targets":sorted(x.casefold() for x in targets)}
    return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()

def discord_send(webhook,stock,found,source):
    if not webhook: raise RuntimeError("DISCORD_WEBHOOK_URL secret이 없습니다.")
    now=datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    content=f"🚨 **Blox Fruits Stock 알림!**\n🦊 **등장한 열매:** {', '.join(found)}\n🏪 **Normal Stock:** {', '.join(stock)}\n📡 **데이터 출처:** {source}\n🕒 **확인 시간:** {now}"
    data=json.dumps({"content":content,"allowed_mentions":{"parse":[]}}).encode()
    req=Request(webhook,data=data,method="POST",headers={"Content-Type":"application/json","User-Agent":"BloxFruitsStockAlert/3.0"})
    with urlopen(req,timeout=20) as r:
        if r.status not in (200,204): raise RuntimeError(f"Discord Webhook HTTP {r.status}")

def main():
    targets=load_config()
    try:
        stock,source=get_stock()
    except Exception as e:
        print("WARNING: Stock check could not be completed.")
        print(e)
        print("The next cron-job.org trigger will try again.")
        return
    lookup={x.casefold():x for x in stock}
    found=[lookup[t.casefold()] for t in targets if t.casefold() in lookup]
    print("Data source:",source)
    print("Current Normal Stock:",", ".join(stock))
    print("Targets:",", ".join(targets))
    print("Matched:",", ".join(found) if found else "none")
    state=load_state(); key=state_key(stock,targets); old=state.get("key")
    if found and key!=old:
        discord_send(os.environ.get("DISCORD_WEBHOOK_URL",""),stock,found,source)
        print("Discord alert sent.")
    elif key==old:
        print("No new alert: same stock/target state.")
    else:
        print("No matching target fruit.")
    save_state({"key":key,"stock":stock,"targets":targets,"source":source,"updated_at":datetime.now(timezone.utc).isoformat()})

if __name__=="__main__":
    main()
