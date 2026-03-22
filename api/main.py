import os
import logging
from contextlib import asynccontextmanager
from datetime import date, timedelta, datetime
from typing import Optional

import asyncpg
from clickhouse_driver import Client
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
import os as _os
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

log = logging.getLogger("api")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

_pg_pool = None
_ch = None

def get_ch():
    global _ch
    if _ch is None:
        _ch = Client(
            host=os.getenv("CLICKHOUSE_HOST", "clickhouse"),
            port=int(os.getenv("CLICKHOUSE_PORT", 9000)),
            database=os.getenv("CLICKHOUSE_DB", "nebulanet"),
            user=os.getenv("CLICKHOUSE_USER", "nebulanet"),
            password=os.getenv("CLICKHOUSE_PASSWORD", "nebulanet_pass"),
        )
    return _ch

async def get_pg():
    global _pg_pool
    if _pg_pool is None:
        _pg_pool = await asyncpg.create_pool(
            os.getenv("POSTGRES_DSN"),
            min_size=2, max_size=20,
        )
    return _pg_pool

@asynccontextmanager
async def lifespan(app):
    global _pg_pool
    _pg_pool = await asyncpg.create_pool(
        os.getenv("POSTGRES_DSN"), min_size=2, max_size=10
    )
    log.info("API ready")
    yield
    if _pg_pool:
        await _pg_pool.close()

app = FastAPI(title="NebulaNet API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def fmt_bytes(b):
    for unit in ("B","KB","MB","GB","TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"

@app.get("/")
async def dashboard():
    return FileResponse(_os.path.join(_os.path.dirname(__file__), "dashboard.html"))

@app.get("/api/health")
async def health():
    return {"status": "ok", "ts": datetime.utcnow().isoformat()}

@app.get("/api/reports/summary")
async def summary(location_id: int = Query(1)):
    ch = get_ch()
    today = date.today()
    week_ago = today - timedelta(days=7)
    try:
        totals = ch.execute(
            "SELECT sum(total_bytes), sum(sessions), uniq(user_id) "
            "FROM user_stats_daily "
            "WHERE location_id=%(loc)s AND date BETWEEN %(f)s AND %(t)s ",
            {"loc": location_id, "f": week_ago, "t": today},
        )
        row = totals[0] if totals else (0, 0, 0)
    except Exception as e:
        log.error("Summary query error: %s", e)
        row = (0, 0, 0)
    return {
        "period_bytes": row[0],
        "period_bytes_fmt": fmt_bytes(row[0]),
        "period_sessions": row[1],
        "active_users": row[2],
    }

@app.get("/api/reports/top-users")
async def top_users(
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    location_id: int = Query(1),
    limit: int = Query(20, le=100),
):
    if not date_from: date_from = date.today() - timedelta(days=7)
    if not date_to:   date_to   = date.today()
    ch = get_ch()
    try:
        rows = ch.execute(
            "SELECT user_id, sum(total_bytes) AS b, sum(sessions) AS s "
            "FROM user_stats_daily "
            "WHERE location_id=%(loc)s AND date BETWEEN %(f)s AND %(t)s  "
            "GROUP BY user_id ORDER BY b DESC LIMIT %(lim)s",
            {"loc": location_id, "f": date_from, "t": date_to, "lim": limit},
        )
    except Exception:
        rows = []
    pg = await get_pg()
    uids = [r[0] for r in rows]
    umap = {}
    if uids:
        urs = await pg.fetch("SELECT id,username,full_name,department FROM users WHERE id=ANY($1)", uids)
        umap = {u["id"]: dict(u) for u in urs}
    return {"data": [
        {"user_id": r[0], "username": umap.get(r[0], {}).get("username", f"user_{r[0]}"),
         "full_name": umap.get(r[0], {}).get("full_name"),
         "department": umap.get(r[0], {}).get("department"),
         "bytes": r[1], "bytes_fmt": fmt_bytes(r[1]), "sessions": r[2]}
        for r in rows
    ], "period": {"from": str(date_from), "to": str(date_to)}}

@app.get("/api/reports/top-domains")
async def top_domains(
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    location_id: int = Query(1),
    limit: int = Query(30, le=200),
):
    if not date_from: date_from = date.today() - timedelta(days=7)
    if not date_to:   date_to   = date.today()
    ch = get_ch()
    try:
        rows = ch.execute(
            "SELECT domain, sum(total_bytes) AS b, sum(requests) AS r, uniq(user_id) AS u "
            "FROM domain_stats_daily "
            "WHERE location_id=%(loc)s AND date BETWEEN %(f)s AND %(t)s AND domain!='' "
            "GROUP BY domain ORDER BY b DESC LIMIT %(lim)s",
            {"loc": location_id, "f": date_from, "t": date_to, "lim": limit},
        )
    except Exception:
        rows = []
    return {"data": [
        {"domain": r[0], "bytes": r[1], "bytes_fmt": fmt_bytes(r[1]), "requests": r[2], "unique_users": r[3]}
        for r in rows
    ]}

@app.get("/api/reports/user/{user_id}/domains")
async def user_domains(
    user_id: int,
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    location_id: int = Query(1),
):
    if not date_from: date_from = date.today() - timedelta(days=7)
    if not date_to:   date_to   = date.today()
    ch = get_ch()
    try:
        rows = ch.execute(
            "SELECT domain, sum(total_bytes), sum(requests) FROM domain_stats_daily "
            "WHERE location_id=%(loc)s AND user_id=%(uid)s AND date BETWEEN %(f)s AND %(t)s AND domain!='' "
            "GROUP BY domain ORDER BY 2 DESC LIMIT 100",
            {"loc": location_id, "uid": user_id, "f": date_from, "t": date_to},
        )
    except Exception:
        rows = []
    pg = await get_pg()
    user = await pg.fetchrow("SELECT username,full_name FROM users WHERE id=$1", user_id)
    return {
        "user": dict(user) if user else {"username": f"user_{user_id}"},
        "data": [{"domain": r[0], "bytes": r[1], "bytes_fmt": fmt_bytes(r[1]), "requests": r[2]} for r in rows],
    }

@app.get("/api/reports/timeline")
async def timeline(
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    location_id: int = Query(1),
    granularity: str = Query("day"),
):
    if not date_from: date_from = date.today() - timedelta(days=7)
    if not date_to:   date_to   = date.today()
    ch = get_ch()
    try:
        rows = ch.execute(
            "SELECT date, sum(total_bytes) FROM user_stats_daily "
            "WHERE location_id=%(loc)s AND date BETWEEN %(f)s AND %(t)s "
            "GROUP BY date ORDER BY date",
            {"loc": location_id, "f": date_from, "t": date_to},
        )
    except Exception:
        rows = []
    return {"data": [{"ts": str(r[0]), "bytes": r[1], "bytes_fmt": fmt_bytes(r[1])} for r in rows]}

@app.get("/api/devices")
async def list_devices(location_id: int = Query(1), unassigned_only: bool = False):
    pg = await get_pg()
    where = "location_id=$1"
    args = [location_id]
    if unassigned_only:
        where += " AND user_id IS NULL"
    rows = await pg.fetch(
        f"SELECT id,mac_address,hostname,ip_current,user_id,last_seen FROM devices WHERE {where} ORDER BY last_seen DESC NULLS LAST LIMIT 500",
        *args,
    )
    return {"data": [dict(r) for r in rows]}

class AssignRequest(BaseModel):
    user_id: int

@app.put("/api/devices/{mac}/assign")
async def assign_device(mac: str, body: AssignRequest):
    pg = await get_pg()
    r = await pg.execute("UPDATE devices SET user_id=$1 WHERE mac_address=$2", body.user_id, mac)
    if r == "UPDATE 0":
        raise HTTPException(404, f"Device {mac} not found")
    return {"ok": True, "mac": mac, "user_id": body.user_id}

@app.get("/api/users")
async def list_users(location_id: int = Query(1)):
    pg = await get_pg()
    rows = await pg.fetch(
        "SELECT id,username,full_name,email,department,is_active FROM users WHERE location_id=$1 AND id!=0 ORDER BY username",
        location_id,
    )
    return {"data": [dict(r) for r in rows]}

class UserCreate(BaseModel):
    username: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    location_id: int = 1

@app.post("/api/users", status_code=201)
async def create_user(body: UserCreate):
    pg = await get_pg()
    row = await pg.fetchrow(
        "INSERT INTO users (username,full_name,email,department,location_id) VALUES ($1,$2,$3,$4,$5) RETURNING id,username",
        body.username, body.full_name, body.email, body.department, body.location_id,
    )
    return {"id": row["id"], "username": row["username"]}

@app.get("/api/reports/dns-activity")
async def dns_activity(
    location_id: int = Query(1),
    limit: int = Query(200, le=5000),
    local_only: bool = Query(True),
    hours: int = Query(24),
):
    ch = get_ch()
    where = "ts >= now() - INTERVAL %(h)s HOUR"
    if local_only:
        where += (" AND toUInt32(src_ip) BETWEEN "
                  "toUInt32(toIPv4('192.168.0.0')) AND toUInt32(toIPv4('192.168.255.255'))")
    try:
        rows = ch.execute(
            f"""
            SELECT toString(src_ip) as ip, domain,
                   count() as hits, max(ts) as last_seen
            FROM dns_log
            WHERE {where}
            GROUP BY ip, domain
            ORDER BY hits DESC
            LIMIT %(lim)s
            """,
            {"h": hours, "lim": limit},
        )
    except Exception as e:
        log.error("dns-activity error: %s", e)
        rows = []
    return {"data": [
        {"ip": r[0], "domain": r[1], "hits": r[2], "last_seen": str(r[3])}
        for r in rows
    ], "hours": hours, "local_only": local_only}

@app.get("/api/reports/ip-activity")
async def ip_activity(
    ip: str = Query(...),
    hours: int = Query(24),
    limit: int = Query(200, le=5000),
):
    ch = get_ch()
    skip = """
        AND domain NOT LIKE 'sip%%'
        AND domain NOT LIKE 'SIP%%'
        AND domain NOT LIKE 'stun%%'
        AND domain NOT LIKE '%%.m.ringcentral.com'
        AND domain NOT LIKE 'ec2-%%'
        AND domain NOT LIKE '%%.compute.amazonaws.com'
        AND domain NOT LIKE '%%-1111.ringcentral.com'
        AND domain NOT LIKE '%%relay%%.ringcentral.com'
        AND domain NOT LIKE 'a.nel.%%'
        AND domain NOT LIKE 'beacons.gcp.%%'
        AND domain NOT LIKE '%%.clients6.google.com'
        AND domain NOT LIKE '%%.statuspage.io'
        AND domain NOT LIKE '%%segment.io'
        AND domain NOT LIKE '%%datadoghq.com'
        AND domain != 'stun-guest-a.gdms.cloud'
        AND domain NOT LIKE '%%-%%-%%-%%'
    """
    try:
        query = """
            SELECT domain, sum(hits) as total, max(last_seen) as last
            FROM (
                SELECT domain, count() as hits, max(ts) as last_seen
                FROM dns_log
                WHERE toString(src_ip) = %(ip)s
                  AND ts >= now() - INTERVAL %(h)s HOUR
            """ + skip + """
                GROUP BY domain
            )
            GROUP BY domain
            ORDER BY total DESC
            LIMIT %(lim)s
        """
        rows = ch.execute(query, {"ip": ip, "h": hours, "lim": limit})
    except Exception as e:
        log.error("ip-activity error: %s", e)
        rows = []
    return {"ip": ip, "data": [
        {"domain": r[0], "hits": r[1], "last_seen": str(r[2])}
        for r in rows
    ]}

# ─── Auto-update devices last_seen from ClickHouse ────────────────
async def sync_devices_activity():
    """Обновляет last_seen устройств на основе последних DNS/Flow данных"""
    import asyncio
    while True:
        try:
            ch = get_ch()
            pg = await get_pg()
            # Берём последние IP которые были активны за последний час
            rows = ch.execute("""
                SELECT toString(src_ip) as ip, max(ts) as last_ts
                FROM dns_log
                WHERE ts >= now() - INTERVAL 2 HOUR
                GROUP BY src_ip
                UNION ALL
                SELECT toString(src_ip) as ip, max(ts) as last_ts
                FROM flows
                WHERE ts >= now() - INTERVAL 2 HOUR
                GROUP BY src_ip
            """)
            # Группируем по IP берём максимальный ts
            ip_ts = {}
            for ip, ts in rows:
                if ip not in ip_ts or ts > ip_ts[ip]:
                    ip_ts[ip] = ts

            # Обновляем devices
            updated = 0
            for ip, ts in ip_ts.items():
                result = await pg.execute(
                    "UPDATE devices SET last_seen=$1, ip_current=$2 WHERE ip_current=$2",
                    ts, ip
                )
                if result != "UPDATE 0":
                    updated += 1
                else:
                    # Устройство не найдено — создаём
                    await pg.execute("""
                        INSERT INTO devices (ip_current, mac_address, last_seen, location_id)
                        VALUES ($1, $2, $3, 1)
                        ON CONFLICT (mac_address) DO UPDATE
                        SET ip_current=EXCLUDED.ip_current, last_seen=EXCLUDED.last_seen
                    """, ip, f"00:00:00:00:{ip.split('.')[-2]:0>2}:{ip.split('.')[-1]:0>2}", ts)

            if updated > 0:
                log.info("Synced last_seen for %d devices", updated)
        except Exception as e:
            log.error("sync_devices error: %s", e)
        await asyncio.sleep(30)

@app.on_event("startup")
async def startup_sync():
    import asyncio
    asyncio.create_task(sync_devices_activity())

# ─── Domain details — кто заходил на домен ────────────────────────
@app.get("/api/reports/domain-users")
async def domain_users(
    domain: str = Query(...),
    hours: int = Query(24),
):
    ch = get_ch()
    try:
        rows = ch.execute("""
            SELECT
                toString(src_ip) as ip,
                count() as hits,
                max(ts) as last_seen
            FROM dns_log
            WHERE domain = %(domain)s
              AND ts >= now() - INTERVAL %(h)s HOUR
            GROUP BY src_ip
            ORDER BY hits DESC
            LIMIT 50
        """, {"domain": domain, "h": hours})

        pg = await get_pg()
        result = []
        for ip, hits, last_seen in rows:
            # Ищем имя устройства
            dev = await pg.fetchrow(
                "SELECT hostname, mac_address, user_id FROM devices WHERE ip_current=$1", ip)
            name = None
            if dev and dev["user_id"]:
                user = await pg.fetchrow("SELECT full_name FROM users WHERE id=$1", dev["user_id"])
                if user: name = user["full_name"]
            if not name and dev: name = dev["hostname"]
            if not name: name = ip

            result.append({
                "ip": ip,
                "name": name,
                "hits": hits,
                "last_seen": str(last_seen),
                "mac": dev["mac_address"] if dev else None,
            })
        return {"domain": domain, "hours": hours, "data": result}
    except Exception as e:
        log.error("domain-users error: %s", e)
        return {"domain": domain, "data": []}

# ─── Search devices by IP or name ─────────────────────────────────
@app.get("/api/devices/search")
async def search_devices(q: str = Query(...)):
    pg = await get_pg()
    rows = await pg.fetch("""
        SELECT d.id, d.mac_address, d.hostname, d.ip_current,
               d.user_id, d.last_seen, u.full_name
        FROM devices d
        LEFT JOIN users u ON u.id = d.user_id
        WHERE d.ip_current::text ILIKE $1
           OR d.hostname ILIKE $1
           OR u.full_name ILIKE $1
           OR d.mac_address::text ILIKE $1
        ORDER BY d.last_seen DESC NULLS LAST
        LIMIT 20
    """, f"%{q}%")
    return {"data": [dict(r) for r in rows]}

@app.get("/api/domain-category")
async def domain_category(domain: str = Query(...), custom_rules: str = Query("")):
    """AI категоризация домена через Claude API с учётом кастомных правил"""
    import urllib.request, json as _json
    import os as _os3
    api_key = _os3.getenv("ANTHROPIC_API_KEY","")
    if not api_key:
        return {"ok": False, "domain": domain, "error": "ANTHROPIC_API_KEY not set"}
    try:
        context = custom_rules if custom_rules else "No custom rules defined yet. Use default categories."
        payload = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 150,
            "messages": [{
                "role": "user",
                "content": f"""You are a cybersecurity and network monitoring expert for a company.

COMPANY CUSTOM RULES (HIGHEST PRIORITY - override everything else):
{context}

Analyze this domain/subdomain: "{domain}"

IMPORTANT - analyze the FULL domain including subdomains:
- Extract the root domain and check what service it belongs to
- Subdomains like "cdn.example.com", "api.example.com", "mail.example.com" belong to the root service
- Suspicious patterns: random strings, IP-like names, typosquatting (g00gle, micros0ft)
- Check if it could be malware C&C, phishing, ad tracker, or data harvester

Reply with JSON only, no other text:
{{"category":"work|social|entertainment|gaming|system|other","reason":"explanation in Russian 2-3 sentences including subdomain analysis","safe":true,"threat_level":"none|low|medium|high","threat_type":"none|malware|phishing|tracker|adware|cryptominer|suspicious"}}

Categories (apply only if no custom rule matches):
- work: business tools, office, CRM, finance, VoIP/SIP (RingCentral, Zoom, etc), logistics, productivity
- social: social networks (Facebook, Instagram, TikTok), messengers (Telegram, WhatsApp)
- entertainment: YouTube, Netflix, Spotify, news, sports, trading platforms used recreationally
- gaming: Steam, Epic, Roblox, game servers, gaming APIs
- system: Windows Update, antivirus, DNS resolvers (8.8.8.8, 1.1.1.1), CDN, SSL/TLS, NTP, monitoring
- other: unclassified or ambiguous"""
            }]
        }
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=_json.dumps(payload).encode(),
            headers={"Content-Type":"application/json","anthropic-version":"2023-06-01","x-api-key":api_key},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = _json.loads(r.read())
        text = data["content"][0]["text"].replace("```json","").replace("```","").strip()
        result = _json.loads(text)
        # Добавляем дефолты если AI не вернул
        result.setdefault("threat_level", "none")
        result.setdefault("threat_type", "none")
        return {"ok": True, "domain": domain, **result}
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        if "credit" in err.lower():
            return {"ok": False, "domain": domain, "error": "Нет кредитов Anthropic"}
        return {"ok": False, "domain": domain, "error": f"API error {e.code}"}
    except Exception as e:
        log.error("domain-category error: %s", e)
        return {"ok": False, "domain": domain, "error": str(e)}



@app.get("/api/reports/device-traffic")
async def device_traffic(hours: int = Query(168)):
    ch = get_ch()
    try:
        rows = ch.execute("""
            SELECT toString(src_ip) as ip,
                   sum(bytes_in) as bytes,
                   formatReadableSize(sum(bytes_in)) as bytes_fmt
            FROM flows
            WHERE ts >= now() - INTERVAL %(h)s HOUR
              AND toUInt32(src_ip) BETWEEN toUInt32(toIPv4('192.168.1.0'))
                                       AND toUInt32(toIPv4('192.168.1.255'))
            GROUP BY src_ip ORDER BY bytes DESC LIMIT 50
        """, {"h": hours})
        return {"data": [{"ip": r[0], "bytes": r[1], "bytes_fmt": r[2]} for r in rows]}
    except Exception as e:
        return {"data": [], "error": str(e)}
