import os
import logging
from contextlib import asynccontextmanager
from datetime import date, timedelta, datetime
from typing import Optional

import asyncpg
from clickhouse_driver import Client
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, JSONResponse
import bcrypt
import secrets
import json
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
    # Запускаем фоновый heartbeat
    import asyncio
    async def heartbeat_loop():
        await asyncio.sleep(10)  # Первый heartbeat через 10 сек после старта
        while True:
            try:
                await send_heartbeat()
            except Exception as e:
                log.warning(f"Heartbeat loop error: {e}")
            await asyncio.sleep(300)  # Каждые 5 минут

    task = asyncio.create_task(heartbeat_loop())
    yield
    task.cancel()
    if _pg_pool:
        await _pg_pool.close()

app = FastAPI(title="NebulaNet API", version="1.0.0", lifespan=lifespan)

# ============================================================
# AUTH — сессии в памяти (простой dict)
# ============================================================
_sessions: dict = {}  # token → {username, checked_at}
LICENSE_CACHE_TTL = 30  # Перепроверяем лицензию каждые 30 секунд
HEARTBEAT_INTERVAL = 300  # Heartbeat каждые 5 минут
_last_heartbeat = 0

async def send_heartbeat():
    """Отправляем heartbeat в v2.0 Super Admin"""
    global _last_heartbeat
    import time
    now = time.time()
    if now - _last_heartbeat < HEARTBEAT_INTERVAL:
        return
    _last_heartbeat = now

    license_key = os.getenv("LICENSE_KEY", "")
    admin_url   = os.getenv("ADMIN_URL", "")
    if not license_key or not admin_url:
        return

    try:
        import httpx
        import platform
        # Считаем устройства онлайн
        pg = await get_pg()
        device_count = await pg.fetchval("SELECT COUNT(*) FROM devices WHERE last_seen > NOW() - INTERVAL '24 hours'")

        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{admin_url}/api/heartbeat", json={
                "key":     license_key,
                "status":  "online",
                "devices": device_count or 0,
                "uptime":  int(now),
                "version": "1.0",
                "ip":      os.getenv("MIKROTIK_HOST", "unknown"),
            })
            log.info(f"Heartbeat sent: {device_count} devices")
    except Exception as e:
        log.warning(f"Heartbeat failed: {e}")

LOGIN_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NebulaNet — Вход</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', sans-serif; background: #0f1117; display: flex; align-items: center; justify-content: center; min-height: 100vh; }
.card { width: 360px; padding: 40px; }
.logo { text-align: center; margin-bottom: 32px; }
.logo svg { margin-bottom: 12px; }
.logo h1 { font-size: 20px; color: #e2e8f0; font-weight: 600; letter-spacing: 1px; }
.logo p { font-size: 12px; color: #4a5568; margin-top: 4px; }
.field { margin-bottom: 16px; }
label { display: block; font-size: 11px; color: #4a5568; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; }
input { width: 100%; padding: 10px 14px; background: #1a1f2e; border: 1px solid #1e2535; border-radius: 8px; color: #e2e8f0; font-size: 14px; outline: none; transition: border-color 0.2s; }
input:focus { border-color: #3b82f6; }
input::placeholder { color: #2d3748; }
.btn { width: 100%; padding: 11px; background: #2563eb; color: white; border: none; border-radius: 8px; font-size: 14px; font-weight: 500; cursor: pointer; margin-top: 8px; transition: background 0.2s; }
.btn:hover { background: #1d4ed8; }
.error { background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.2); border-radius: 8px; padding: 10px 14px; color: #f87171; font-size: 13px; margin-bottom: 16px; }
.footer { text-align: center; margin-top: 24px; font-size: 11px; color: #2d3748; }
</style>
</head>
<body>
<div class="card">
  <div class="logo">
    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="24" height="24" rx="8" fill="rgba(59,130,246,0.1)"/>
      <path d="M12 4L4 8l8 4 8-4-8-4zM4 16l8 4 8-4M4 12l8 4 8-4" stroke="#63b3ed" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    <h1>NebulaNet</h1>
    <p>Network Monitor</p>
  </div>
  {error}
  <form method="post" action="/login">
    <div class="field">
      <label>Логин</label>
      <input type="text" name="username" placeholder="admin" required autofocus>
    </div>
    <div class="field">
      <label>Пароль</label>
      <input type="password" name="password" placeholder="••••••••" required>
    </div>
    <button type="submit" class="btn">Войти</button>
  </form>
  <div class="footer">NebulaNet Network Monitor v1.0</div>
</div>
</body>
</html>"""



BLOCKED_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>NebulaNet — Доступ приостановлен</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', sans-serif; background: #0f1117; display: flex; align-items: center; justify-content: center; min-height: 100vh; }
.card { width: 420px; padding: 48px 40px; text-align: center; }
.icon { width: 64px; height: 64px; background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.2); border-radius: 16px; display: flex; align-items: center; justify-content: center; margin: 0 auto 24px; }
h1 { font-size: 20px; color: #e2e8f0; font-weight: 600; margin-bottom: 12px; }
p { font-size: 14px; color: #4a5568; line-height: 1.6; margin-bottom: 8px; }
.reason { background: rgba(239,68,68,0.05); border: 1px solid rgba(239,68,68,0.15); border-radius: 8px; padding: 12px 16px; margin: 20px 0; font-size: 13px; color: #f87171; }
.back { display: inline-block; margin-top: 24px; padding: 10px 24px; background: rgba(255,255,255,0.05); border: 1px solid #1e2535; border-radius: 8px; color: #8a9ab5; font-size: 13px; text-decoration: none; }
.footer { margin-top: 32px; font-size: 11px; color: #2d3748; }
</style>
</head>
<body>
<div class="card">
  <div class="icon">
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
      <path d="M12 9v4M12 17h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" stroke="#f87171" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
  </div>
  <h1>Доступ приостановлен</h1>
  <p>Ваша подписка на NebulaNet Network Monitor</p>
  <p>приостановлена или срок действия истёк.</p>
  <div class="reason">{reason}</div>
  <p style="font-size:13px;color:#4a5568">Для восстановления доступа обратитесь к администратору.</p>
  <a href="/logout" class="back">← Сменить аккаунт</a>
  <div style="margin-top:24px;padding:16px;background:rgba(255,255,255,0.03);border:1px solid #1e2535;border-radius:8px;">
    <p style="font-size:12px;color:#4a5568;margin-bottom:8px">Служба поддержки</p>
    <p style="font-size:13px;color:#8a9ab5;margin-bottom:4px">📞 +998 99 357 00 40</p>
    <p style="font-size:13px;color:#63b3ed"><a href="https://nebulanet.uz" style="color:#63b3ed;text-decoration:none">🌐 nebulanet.uz</a></p>
  </div>
  <div class="footer">NebulaNet Network Monitor v1.0</div>
</div>
</body>
</html>"""

async def check_auth(request: Request):
    """Возвращает (is_auth: bool, blocked: bool, reason: str)"""
    token = request.cookies.get("nn_session")
    if not token or token not in _sessions:
        return False, False, ""

    session = _sessions[token]
    now = datetime.utcnow().timestamp()

    # Перепроверяем лицензию каждые 5 минут
    if now - session.get("checked_at", 0) > LICENSE_CACHE_TTL:
        license_key = os.getenv("LICENSE_KEY", "")
        admin_url   = os.getenv("ADMIN_URL", "")
        log.info(f"License check: key={license_key[:10] if license_key else 'NONE'}, url={admin_url or 'NONE'}")
        if license_key and admin_url:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=5.0) as client:
                    r = await client.get(f"{admin_url}/api/license/check?key={license_key}")
                    data = r.json()
                    log.info(f"License response: {data}")
                    session["checked_at"] = now
                    if not data.get("active", False):
                        reason = data.get("reason", "Лицензия недействительна")
                        reason_map = {
                            "License expired": "Срок действия лицензии истёк",
                            "Organization disabled": "Организация заблокирована администратором",
                            "Invalid license key": "Неверный ключ лицензии",
                        }
                        session["blocked"] = True
                        session["reason"] = reason_map.get(reason, reason)
                    else:
                        session["blocked"] = False
                        session["reason"] = ""
            except Exception as e:
                log.warning(f"License check failed: {e}")
                session["checked_at"] = now  # Не блокируем если v2.0 недоступен
        else:
            session["checked_at"] = now

    if session.get("blocked"):
        return True, True, session.get("reason", "Доступ заблокирован")
    return True, False, ""

@app.get("/login")
async def login_page(request: Request, error: str = ""):
    is_auth, _, _ = await check_auth(request)
    if is_auth:
        return RedirectResponse("/", status_code=302)
    err_html = f'<div class="error">{error}</div>' if error else ""
    return HTMLResponse(LOGIN_HTML.replace("{error}", err_html))

@app.post("/login")
async def login_submit(request: Request):
    form = await request.form()
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))
    pg = await get_pg()
    row = await pg.fetchrow(
        "SELECT password, is_active FROM org_admins WHERE username=$1", username
    )
    if not row or not row["is_active"]:
        return RedirectResponse("/login?error=Неверный+логин+или+пароль", status_code=302)
    if not bcrypt.checkpw(password.encode(), row["password"].encode()):
        return RedirectResponse("/login?error=Неверный+логин+или+пароль", status_code=302)
    await pg.execute(
        "UPDATE org_admins SET last_login=now() WHERE username=$1", username
    )
    token = secrets.token_urlsafe(32)
    _sessions[token] = {"username": username, "checked_at": 0, "blocked": False, "reason": ""}
    response = RedirectResponse("/", status_code=302)
    response.set_cookie("nn_session", token, httponly=True, max_age=86400*7)
    return response

@app.get("/logout")
async def logout(request: Request):
    token = request.cookies.get("nn_session")
    if token:
        _sessions.pop(token, None)
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("nn_session")
    return response

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def fmt_bytes(b):
    for unit in ("B","KB","MB","GB","TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"

@app.get("/")
async def dashboard(request: Request):
    # При загрузке страницы всегда сбрасываем кэш — мгновенная проверка
    token = request.cookies.get("nn_session")
    if token and token in _sessions:
        _sessions[token]["checked_at"] = 0  # Сбрасываем кэш
    # Отправляем heartbeat в фоне
    import asyncio
    asyncio.create_task(send_heartbeat())
    is_auth, blocked, reason = await check_auth(request)
    if not is_auth:
        return RedirectResponse("/login", status_code=302)
    if blocked:
        return HTMLResponse(BLOCKED_HTML.replace("{reason}", reason))
    return FileResponse(_os.path.join(_os.path.dirname(__file__), "dashboard.html"))

@app.get("/api/health")
async def health():
    return {"status": "ok", "ts": datetime.utcnow().isoformat()}

@app.get("/api/license-status")
async def license_status(request: Request):
    """Проверка статуса лицензии для JS пуллинга"""
    is_auth, blocked, reason = await check_auth(request)
    if not is_auth:
        return JSONResponse({"active": False, "reason": "Not authenticated"}, status_code=401)
    if blocked:
        return JSONResponse({"active": False, "reason": reason}, status_code=403)
    return JSONResponse({"active": True})

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

# ─── Domain Categories (persistent) ──────────────────────────────
@app.get("/api/domain-categories")
async def get_domain_categories():
    """Получить все кастомные категории из БД"""
    pg = await get_pg()
    rows = await pg.fetch("SELECT service_name, category FROM domain_categories")
    return {"data": {r["service_name"]: r["category"] for r in rows}}

@app.post("/api/domain-categories")
async def save_domain_category(body: dict):
    """Сохранить категорию домена в БД"""
    pg = await get_pg()
    svc = body.get("service_name", "").strip()
    cat = body.get("category", "").strip()
    if not svc or not cat:
        return {"ok": False, "error": "service_name and category required"}
    # Нормализуем — первая буква заглавная для единообразия
    svc = svc[0].upper() + svc[1:] if svc else svc
    await pg.execute("""
        INSERT INTO domain_categories (service_name, category, updated_at)
        VALUES ($1, $2, NOW())
        ON CONFLICT (service_name) DO UPDATE
        SET category = EXCLUDED.category, updated_at = NOW()
    """, svc, cat)
    return {"ok": True}

@app.delete("/api/domain-categories/{service_name}")
async def delete_domain_category(service_name: str):
    """Удалить кастомную категорию (сброс к дефолту)"""
    pg = await get_pg()
    await pg.execute("DELETE FROM domain_categories WHERE service_name=$1", service_name)
    return {"ok": True}

# ─── MikroTik Integration ─────────────────────────────────────────
import os as _os_mt

def get_mikrotik():
    import librouteros
    return librouteros.connect(
        host=_os_mt.getenv('MIKROTIK_HOST','192.168.1.200'),
        username=_os_mt.getenv('MIKROTIK_USER','nebulanet'),
        password=_os_mt.getenv('MIKROTIK_PASS','Nebula2026!'),
        port=8728
    )

async def ensure_block_tables(pg):
    await pg.execute("""
        CREATE TABLE IF NOT EXISTS blocked_domains (
            id SERIAL PRIMARY KEY,
            domain VARCHAR(255) NOT NULL,
            department VARCHAR(255) NOT NULL DEFAULT 'all',
            comment TEXT,
            blocked_at TIMESTAMP DEFAULT NOW(),
            is_active BOOLEAN DEFAULT TRUE,
            UNIQUE(domain, department)
        )
    """)
    await pg.execute("""
        CREATE TABLE IF NOT EXISTS departments (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL UNIQUE,
            address_list VARCHAR(255) NOT NULL UNIQUE,
            description TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

# ─── Departments ──────────────────────────────────────────────────
@app.get("/api/departments")
async def get_departments():
    """Список отделов (address-lists из MikroTik)"""
    try:
        mt = get_mikrotik()
        al = list(mt(cmd='/ip/firewall/address-list/print'))
        mt.close()
        # Группируем по списку
        lists = {}
        for e in al:
            name = e.get('list','')
            if name in ('block','local-nets','steam_block','udp2raw','frankfurt','frankfurt-ovpn','usa','Monitor185'):
                continue  # пропускаем системные
            if name not in lists:
                lists[name] = []
            lists[name].append(e.get('address',''))
        return {"data": [{"name": k, "address_list": k, "members": v} for k,v in lists.items()]}
    except Exception as e:
        return {"data": [], "error": str(e)}

@app.post("/api/departments")
async def create_department(body: dict):
    """Создать отдел — добавить IP в address-list"""
    name = body.get("name","").strip()
    ip = body.get("ip","").strip()
    comment = body.get("comment","")
    if not name or not ip:
        return {"ok": False, "error": "name and ip required"}
    try:
        mt = get_mikrotik()
        list(mt(cmd='/ip/firewall/address-list/add', **{
            'list': name,
            'address': ip,
            'comment': comment or f'NebulaNet: {name}'
        }))
        mt.close()
        return {"ok": True, "department": name, "ip": ip}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.delete("/api/departments/{dept_name}/members/{ip}")
async def remove_from_department(dept_name: str, ip: str):
    """Удалить IP из отдела"""
    try:
        mt = get_mikrotik()
        entries = list(mt(cmd='/ip/firewall/address-list/print'))
        for e in entries:
            if e.get('list') == dept_name and e.get('address') == ip:
                list(mt(cmd='/ip/firewall/address-list/remove', **{'.id': e['.id']}))
        mt.close()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ─── DNS Block list ───────────────────────────────────────────────
@app.get("/api/block/dns-list")
async def get_dns_block_list():
    """Список DNS regexp блокировок"""
    try:
        mt = get_mikrotik()
        entries = list(mt(cmd='/ip/dns/static/print'))
        mt.close()
        nebulanet = [e for e in entries if 'NebulaNet:' in str(e.get('comment',''))]
        return {"data": [{
            "id": e.get('.id'),
            "regexp": e.get('regexp',''),
            "address": e.get('address',''),
            "comment": e.get('comment',''),
            "disabled": e.get('disabled', False)
        } for e in nebulanet]}
    except Exception as e:
        return {"data": [], "error": str(e)}

@app.post("/api/block/dns-toggle")
async def toggle_dns_block(body: dict):
    """Включить/выключить DNS regexp блокировку"""
    entry_id = body.get("id","").strip()
    disabled = body.get("disabled", False)
    if not entry_id:
        return {"ok": False, "error": "id required"}
    try:
        mt = get_mikrotik()
        if disabled:
            list(mt(cmd='/ip/dns/static/disable', **{'.id': entry_id}))
        else:
            list(mt(cmd='/ip/dns/static/enable', **{'.id': entry_id}))
        mt.close()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.delete("/api/block/dns/{entry_id}")
async def delete_dns_block(entry_id: str):
    """Удалить DNS regexp блокировку"""
    try:
        mt = get_mikrotik()
        list(mt(cmd='/ip/dns/static/remove', **{'.id': entry_id}))
        mt.close()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ─── Block rules ───────────────────────────────────────────────────
@app.get("/api/block/list")
async def get_block_list():
    """Список блокировок — address-list + SNI rules"""
    try:
        mt = get_mikrotik()
        entries = list(mt(cmd='/ip/firewall/address-list/print'))
        filter_rules = list(mt(cmd='/ip/firewall/filter/print'))
        mt.close()
        blocked = [e for e in entries if e.get('list') == 'block']
        # SNI правила созданные нами
        sni_rules = [r for r in filter_rules if 'NebulaNet-SNI:' in str(r.get('comment',''))]
        pg = await get_pg()
        await ensure_block_tables(pg)
        db_rows = await pg.fetch("SELECT * FROM blocked_domains WHERE is_active=TRUE ORDER BY blocked_at DESC")
        return {
            "mt_blocked": [{
                "id": e.get('.id'),
                "address": e.get('address'),
                "comment": e.get('comment',''),
                "disabled": e.get('disabled', False)
            } for e in blocked],
            "sni_rules": [{
                "id": r.get('.id'),
                "tls_host": r.get('tls-host',''),
                "src_list": r.get('src-address-list','all'),
                "action": r.get('action',''),
                "comment": r.get('comment',''),
                "disabled": r.get('disabled', False)
            } for r in sni_rules],
            "rules": [dict(r) for r in db_rows]
        }
    except Exception as e:
        return {"mt_blocked": [], "sni_rules": [], "rules": [], "error": str(e)}

@app.post("/api/block/toggle")
async def toggle_block(body: dict):
    """Включить/выключить address-list запись + SNI правило"""
    entry_id = body.get("id","").strip()
    disabled = body.get("disabled", False)
    domain = body.get("domain","").strip()
    if not entry_id:
        return {"ok": False, "error": "id required"}
    try:
        mt = get_mikrotik()
        # Toggle address-list
        if disabled:
            list(mt(cmd='/ip/firewall/address-list/disable', **{'.id': entry_id}))
        else:
            list(mt(cmd='/ip/firewall/address-list/enable', **{'.id': entry_id}))
        # Toggle SNI правила для этого домена
        if domain:
            filter_rules = list(mt(cmd='/ip/firewall/filter/print'))
            for r in filter_rules:
                if f'NebulaNet-SNI: {domain}' in str(r.get('comment','')) or                    f'NebulaNet-HTTP: {domain}' in str(r.get('comment','')):
                    if disabled:
                        list(mt(cmd='/ip/firewall/filter/disable', **{'.id': r['.id']}))
                    else:
                        list(mt(cmd='/ip/firewall/filter/enable', **{'.id': r['.id']}))
        mt.close()
        return {"ok": True, "id": entry_id, "disabled": disabled}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/api/block/sni-toggle")
async def toggle_sni(body: dict):
    """Включить/выключить SNI правило"""
    entry_id = body.get("id","").strip()
    disabled = body.get("disabled", False)
    if not entry_id:
        return {"ok": False, "error": "id required"}
    try:
        mt = get_mikrotik()
        if disabled:
            list(mt(cmd='/ip/firewall/filter/disable', **{'.id': entry_id}))
        else:
            list(mt(cmd='/ip/firewall/filter/enable', **{'.id': entry_id}))
        mt.close()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/api/block/domain")
async def block_domain(body: dict):
    """Добавить домен в block list + создать правило для отдела"""
    domain = body.get("domain","").strip()
    department = body.get("department","").strip()
    target_type = body.get("target_type","dept").strip()
    comment = body.get("comment", f"NebulaNet: {domain}")
    if not domain:
        return {"ok": False, "error": "domain required"}
    import re as _re
    # Определяем это подсеть или address-list
    is_subnet = target_type == 'subnet' or bool(_re.match(r'^\d+\.\d+\.\d+\.\d+', department))
    try:
        mt = get_mikrotik()
        # 1. Добавляем домен в address-list 'block'
        try:
            list(mt(cmd='/ip/firewall/address-list/add', **{
                'list': 'block',
                'address': domain,
                'comment': comment
            }))
        except Exception:
            pass  # уже существует

        # 2. Создаём правило блокировки
        if department and department != 'all':
            rules = list(mt(cmd='/ip/firewall/filter/print'))
            forward_rules = [r for r in rules if r.get('chain')=='forward']
            first_rule_id = forward_rules[0]['.id'] if forward_rules else None

            if is_subnet:
                # Блокировка по подсети
                rule_exists = any(
                    r.get('src-address') == department and
                    r.get('dst-address-list') == 'block' and
                    r.get('chain') == 'forward' and
                    not r.get('disabled')
                    for r in rules
                )
                if not rule_exists:
                    kwargs = {
                        'chain': 'forward',
                        'src-address': department,
                        'dst-address-list': 'block',
                        'action': 'reject',
                        'reject-with': 'icmp-network-unreachable',
                        'comment': f'NebulaNet: block subnet {department}'
                    }
                    if first_rule_id:
                        kwargs['place-before'] = first_rule_id
                    list(mt(cmd='/ip/firewall/filter/add', **kwargs))
                    log.info("Created subnet block rule for %s", department)
            else:
                # Блокировка по address-list (отдел)
                rule_exists = any(
                    r.get('src-address-list') == department and
                    r.get('dst-address-list') == 'block' and
                    r.get('chain') == 'forward' and
                    not r.get('disabled')
                    for r in rules
                )
                if not rule_exists:
                    kwargs = {
                        'chain': 'forward',
                        'src-address-list': department,
                        'dst-address-list': 'block',
                        'action': 'reject',
                        'reject-with': 'icmp-network-unreachable',
                        'comment': f'NebulaNet: block for {department}'
                    }
                    if first_rule_id:
                        kwargs['place-before'] = first_rule_id
                    list(mt(cmd='/ip/firewall/filter/add', **kwargs))
                    log.info("Created filter rule for department: %s", department)

        mt.close()

        # 3. Сохраняем в БД
        pg = await get_pg()
        await ensure_block_tables(pg)
        await pg.execute("""
            INSERT INTO blocked_domains (domain, department, comment)
            VALUES ($1, $2, $3)
            ON CONFLICT (domain, department) DO UPDATE
            SET is_active=TRUE, comment=EXCLUDED.comment, blocked_at=NOW()
        """, domain, department or 'all', comment)

        return {"ok": True, "domain": domain, "department": department}
    except Exception as e:
        log.error("block_domain error: %s", e)
        return {"ok": False, "error": str(e)}


@app.post("/api/block/unblock")
async def unblock_domain(body: dict):
    """Удалить домен из block list + убрать filter rules если нет других доменов"""
    domain = body.get("domain","").strip()
    department = body.get("department","").strip()
    if not domain:
        return {"ok": False, "error": "domain required"}
    try:
        mt = get_mikrotik()
        # 1. Удаляем из address-list block
        entries = list(mt(cmd='/ip/firewall/address-list/print'))
        removed = 0
        for e in entries:
            if e.get('list') == 'block' and e.get('address') == domain:
                list(mt(cmd='/ip/firewall/address-list/remove', **{'.id': e['.id']}))
                removed += 1

        # 2. Проверяем остались ли ещё домены в block list
        entries_after = list(mt(cmd='/ip/firewall/address-list/print'))
        block_count = sum(1 for e in entries_after if e.get('list') == 'block' and not e.get('disabled'))

        # 3. Если block list пустой — удаляем все NebulaNet filter rules
        if block_count == 0:
            filter_rules = list(mt(cmd='/ip/firewall/filter/print'))
            for r in filter_rules:
                if 'NebulaNet:' in str(r.get('comment','')):
                    list(mt(cmd='/ip/firewall/filter/remove', **{'.id': r['.id']}))
                    log.info("Removed filter rule (no more blocks): %s", r.get('comment'))

        mt.close()
        pg = await get_pg()
        await ensure_block_tables(pg)
        await pg.execute("UPDATE blocked_domains SET is_active=FALSE WHERE domain=$1", domain)
        return {"ok": True, "removed": removed, "block_remaining": block_count}
    except Exception as e:
        log.error("unblock error: %s", e)
        return {"ok": False, "error": str(e)}

@app.get("/api/mikrotik/subnets")
async def get_subnets():
    """Получить список подсетей из MikroTik"""
    try:
        mt = get_mikrotik()
        # Получаем IP адреса интерфейсов
        addresses = list(mt(cmd='/ip/address/print'))
        # Получаем address-lists (отделы)
        al = list(mt(cmd='/ip/firewall/address-list/print'))
        mt.close()

        # Подсети из интерфейсов
        subnets = []
        for a in addresses:
            addr = a.get('address','')
            iface = a.get('interface','')
            if addr and not a.get('disabled'):
                # Конвертируем IP/mask в подсеть
                import ipaddress
                try:
                    net = ipaddress.ip_interface(addr).network
                    subnets.append({
                        'subnet': str(net),
                        'interface': iface,
                        'type': 'interface'
                    })
                except:
                    pass

        # Уникальные address-lists (отделы)
        lists = {}
        for e in al:
            name = e.get('list','')
            skip = ['block','local-nets','steam_block','udp2raw','frankfurt',
                   'frankfurt-ovpn','usa','Monitor185']
            if name not in skip and name not in lists:
                lists[name] = []
            if name in lists:
                lists[name].append(e.get('address',''))

        departments = [{'name': k, 'members': v, 'type': 'department'}
                      for k,v in lists.items()]

        return {"subnets": subnets, "departments": departments}
    except Exception as e:
        return {"subnets": [], "departments": [], "error": str(e)}

@app.get("/api/reports/device-categories")
async def device_categories(hours: int = Query(24)):
    """Категории DNS активности по устройствам за период"""
    ch = get_ch()
    try:
        rows = ch.execute("""
            SELECT toString(src_ip) as ip, domain, count() as hits
            FROM dns_log
            WHERE ts >= now() - INTERVAL %(h)s HOUR
              AND match(toString(src_ip), '^192\\.168\\.')
            GROUP BY src_ip, domain
            ORDER BY src_ip, hits DESC
        """, {"h": hours})
        # Группируем по IP
        by_ip = {}
        for ip, domain, hits in rows:
            if ip not in by_ip:
                by_ip[ip] = []
            by_ip[ip].append({"domain": domain, "hits": hits})
        return {"data": by_ip}
    except Exception as e:
        log.error("device-categories error: %s", e)
        return {"data": {}}
