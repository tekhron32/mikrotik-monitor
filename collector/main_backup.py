import asyncio, logging, os, re, signal, struct, time, urllib.request, urllib.parse, urllib.error
from dataclasses import dataclass
from datetime import datetime
import redis.asyncio as aioredis
import asyncpg

logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("collector")

CH_HOST     = os.getenv("CLICKHOUSE_HOST","clickhouse")
CH_PORT     = int(os.getenv("CLICKHOUSE_PORT","8123"))
CH_DB       = os.getenv("CLICKHOUSE_DB","nebulanet")
CH_USER     = os.getenv("CLICKHOUSE_USER","nebulanet")
CH_PASS     = os.getenv("CLICKHOUSE_PASSWORD","nebulanet_secret")
PG_DSN      = os.getenv("POSTGRES_DSN","postgresql://nebulanet:nebulanet_secret@postgres:5432/nebulanet")
REDIS_URL   = os.getenv("REDIS_URL","redis://redis:6379/0")
FLUSH_INT   = int(os.getenv("FLUSH_INTERVAL","30"))
LOCATION_ID = int(os.getenv("LOCATION_ID","1"))

@dataclass
class Flow:
    ts: datetime
    location_id: int
    user_id: int
    src_ip: str
    dst_ip: str
    domain: str
    sni_host: str
    proto: int
    src_port: int
    dst_port: int
    bytes_in: int
    bytes_out: int
    packets_in: int
    packets_out: int

class ClickHouseWriter:
    BATCH = 500
    INSERT_URL = None

    def _url(self):
        if not self.INSERT_URL:
            q = urllib.parse.urlencode({
                "database": CH_DB,
                "user": CH_USER,
                "password": CH_PASS,
                "query": (
                    "INSERT INTO flows "
                    "(ts,location_id,user_id,src_ip,dst_ip,domain,sni_host,"
                    "proto,src_port,dst_port,bytes_in,bytes_out,packets_in,packets_out) "
                    "FORMAT TabSeparated"
                ),
            })
            self.INSERT_URL = f"http://{CH_HOST}:{CH_PORT}/?{q}"
        return self.INSERT_URL

    def insert_dns(self, rows):
        if not rows: return
        url = (f"http://{CH_HOST}:{CH_PORT}/?database={CH_DB}&user={CH_USER}"
               f"&password={urllib.parse.quote(CH_PASS)}"
               f"&query=INSERT+INTO+dns_log+(ts,location_id,src_ip,domain,qtype)+FORMAT+TabSeparated")
        lines = []
        for r in rows:
            lines.append(f"{r['ts']}	1	{r['src_ip']}	{r['domain']}	A")
        body = "\n".join(lines).encode("utf-8")
        try:
            req = urllib.request.Request(url, data=body, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp.read()
            log.info("Flushed %d DNS records", len(rows))
        except urllib.error.HTTPError as e:
            log.error("DNS ClickHouse HTTP %d: %s", e.code, e.read().decode()[:200])
        except Exception as e:
            log.error("DNS flush error: %s", e)

    def insert_flows(self, flows):
        if not flows:
            return
        url = self._url()
        for i in range(0, len(flows), self.BATCH):
            batch = flows[i : i + self.BATCH]
            lines = []
            for f in batch:
                row = "\t".join([
                    str(int(f.ts.timestamp())),
                    str(f.location_id),
                    str(f.user_id),
                    f.src_ip or "0.0.0.0",
                    f.dst_ip or "0.0.0.0",
                    (f.domain or "").replace("\t","").replace("\n",""),
                    "",
                    str(f.proto),
                    str(f.src_port),
                    str(f.dst_port),
                    str(f.bytes_in),
                    str(f.bytes_out),
                    str(f.packets_in),
                    str(f.packets_out),
                ])
                lines.append(row)
            body = "\n".join(lines).encode("utf-8")
            try:
                req = urllib.request.Request(url, data=body, method="POST")
                with urllib.request.urlopen(req, timeout=30) as resp:
                    resp.read()
                log.info("Flushed %d flows to ClickHouse", len(batch))
            except urllib.error.HTTPError as e:
                log.error("ClickHouse HTTP %d: %s", e.code, e.read().decode()[:300])
            except Exception as e:
                log.error("ClickHouse error: %s", e)

class Enricher:
    def __init__(self, r, pg):
        self.r = r
        self.pg = pg
        self._dns = {}

    async def record_dns(self, ip, domain):
        self._dns[ip] = (domain, time.time() + 120)
        await self.r.setex(f"dns:{ip}", 120, domain)
        if hasattr(self, "_dns_buf"):
            self._dns_buf.append({"ts": int(time.time()), "src_ip": ip, "domain": domain, "qtype": "A"})

    async def get_domain(self, ip):
        e = self._dns.get(ip)
        if e and time.time() < e[1]:
            return e[0]
        v = await self.r.get(f"dns:{ip}")
        return v.decode() if v else ""

    async def record_dhcp(self, mac, ip, hostname):
        async with self.pg.acquire() as c:
            uid = await c.fetchval(
                "SELECT user_id FROM devices WHERE mac_address=$1", mac) or 0
            await c.execute(
                "INSERT INTO dhcp_leases (mac_address,ip_address,user_id,hostname,location_id) "
                "VALUES ($1,$2,$3,$4,$5) ON CONFLICT DO NOTHING",
                mac, ip, uid, hostname, LOCATION_ID)
            await c.execute(
                "INSERT INTO devices (mac_address,ip_current,hostname,last_seen,location_id) "
                "VALUES ($1,$2,$3,NOW(),$4) ON CONFLICT (mac_address) DO UPDATE "
                "SET ip_current=$2,hostname=$3,last_seen=NOW()",
                mac, ip, hostname, LOCATION_ID)
        await self.r.setex(f"user:{ip}", 86400, str(uid))
        log.info("DHCP: %s -> %s", mac, ip)

    async def get_user_id(self, ip):
        v = await self.r.get(f"user:{ip}")
        if v:
            return int(v)
        async with self.pg.acquire() as c:
            uid = await c.fetchval(
                "SELECT user_id FROM dhcp_leases WHERE ip_address=$1::inet "
                "ORDER BY assigned_at DESC LIMIT 1", ip)
        if uid:
            await self.r.setex(f"user:{ip}", 86400, str(uid))
            return uid
        return 0

def ip4(b):
    return ".".join(str(x) for x in b)

class NetFlowParser:
    def __init__(self):
        self._tpl = {}
        self._cnt = 0

    def parse(self, data, src):
        if len(data) < 20:
            return []
        ver = struct.unpack_from("!H", data, 0)[0]
        self._cnt += 1
        if self._cnt <= 5 or self._cnt % 100 == 0:
            log.info("PKT #%d from %s ver=%d len=%d", self._cnt, src, ver, len(data))
        if ver != 9:
            return []
        _, _, ts = struct.unpack_from("!HII", data, 2)
        offset = 20
        tsets = []
        dsets = []
        while offset + 4 <= len(data):
            fid, flen = struct.unpack_from("!HH", data, offset)
            if flen < 4:
                break
            content = data[offset + 4 : offset + flen]
            if fid == 0:
                tsets.append(content)
            elif fid >= 256:
                dsets.append((fid, content, ts))
            pad = (4 - flen % 4) % 4
            offset += flen + pad
        for t in tsets:
            self._parse_tpl(t, src)
        recs = []
        for fid, content, ts in dsets:
            k = (src, fid)
            tpl = self._tpl.get(k)
            if tpl:
                r = self._parse_data(content, tpl, ts)
                recs.extend(r)
                if r:
                    log.debug("FlowSet id=%d: %d records", fid, len(r))
            else:
                log.debug("No template for id=%d from %s", fid, src)
        return recs

    def _parse_tpl(self, data, src):
        off = 0
        while off + 4 <= len(data):
            tid, fc = struct.unpack_from("!HH", data, off)
            off += 4
            if fc == 0 or off + fc * 4 > len(data):
                break
            fields = []
            for _ in range(fc):
                ft, fl = struct.unpack_from("!HH", data, off)
                fields.append((ft, fl))
                off += 4
            k = (src, tid)
            is_new = k not in self._tpl
            self._tpl[k] = fields
            if is_new:
                log.info("Template id=%d from %s (%d fields)", tid, src, fc)

    def _parse_data(self, data, tpl, ts):
        rlen = sum(fl for _, fl in tpl)
        if not rlen:
            return []
        recs = []
        off = 0
        while off + rlen <= len(data):
            rec = {
                "src_ip":"0.0.0.0","dst_ip":"0.0.0.0",
                "bytes_in":0,"bytes_out":0,"packets_in":0,"packets_out":0,
                "proto":0,"src_port":0,"dst_port":0,
            }
            p = off
            for ft, fl in tpl:
                raw = data[p : p + fl]
                p += fl
                if   ft == 8  and fl == 4: rec["src_ip"]     = ip4(raw)
                elif ft == 12 and fl == 4: rec["dst_ip"]     = ip4(raw)
                elif ft == 1:              rec["bytes_in"]   = int.from_bytes(raw,"big")
                elif ft == 2:              rec["packets_in"] = int.from_bytes(raw,"big")
                elif ft == 4:              rec["proto"]      = raw[0]
                elif ft == 7:              rec["src_port"]   = int.from_bytes(raw,"big")
                elif ft == 11:             rec["dst_port"]   = int.from_bytes(raw,"big")
                elif ft == 23:             rec["bytes_out"]  = int.from_bytes(raw,"big")
                elif ft == 24:             rec["packets_out"]= int.from_bytes(raw,"big")
            rec["ts"] = datetime.utcfromtimestamp(ts)
            if rec["src_ip"] != "0.0.0.0":
                recs.append(rec)
            off += rlen
        return recs

RE_DNS  = re.compile(r"dns.*?query.*?from\s+([\d.]+).*?for\s+([\w.\-]+)", re.I)
RE_DNS2 = re.compile(r"got query from ([\d.]+):\d+", re.I)
RE_DNS3 = re.compile(r"dns,packet question: ([\w.\-]+)\.:(?:A|AAAA|ALL|CNAME|MX)", re.I)
# RouterOS v7: "dns query from 192.168.1.5: #12345 google.com. A"
RE_DNS4 = re.compile(r"dns query from ([\d.]+):\s*#\d+\s+([\w.\-]+)\.", re.I)
RE_DHCP = re.compile(
    r"dhcp\S*\s+assigned\s+([\d.]+)\s+(?:to|for)\s+([0-9A-Fa-f:]{17})"
    r"(?:[^(]*\(([^)]*)\))?", re.I)

class SyslogProtocol(asyncio.DatagramProtocol):
    def __init__(self, enricher, loop):
        self.e = enricher
        self.loop = loop
        self._last_dns_ip = {}  # src_port -> ip

    def datagram_received(self, data, addr):
        msg = data.decode("utf-8", errors="replace")
        if "192.168" in msg and "query" in msg.lower():
            log.info("RAW_SYSLOG: %s", repr(msg[:120]))
        self.loop.create_task(self._handle(msg, addr))

    async def _handle(self, msg, addr):
        # Формат 0: RouterOS v7 "dns query from 192.168.1.5: #123 google.com. A"
        m0 = RE_DNS4.search(msg)
        if m0:
            src_ip = m0.group(1)
            domain = m0.group(2).rstrip(".")
            if (src_ip.startswith("192.168.") or src_ip.startswith("10.")) and self._valid_domain(domain):
                await self.e.record_dns(src_ip, domain)
                log.info("DNS(4): %s -> %s", src_ip, domain)
            return

        # Формат 1: классический "query from IP for domain"
        m = RE_DNS.search(msg)
        if m:
            d = m.group(2).rstrip(".")
            if self._valid_domain(d):
                await self.e.record_dns(m.group(1), d)
                log.info("DNS(1): %s -> %s", m.group(1), d)
            return

        # Формат 2 (MikroTik RouterOS v7):
        # Пакет 1: "got query from IP:port:"  -> запоминаем IP
        # Пакет 2: "dns,packet question: domain.:TYPE" -> берём домен
        m2 = RE_DNS2.search(msg)
        if m2:
            src_port = addr[1]
            self._last_dns_ip[src_port] = m2.group(1)
            # Чистим старые записи
            if len(self._last_dns_ip) > 1000:
                self._last_dns_ip.clear()
            return

        m3 = RE_DNS3.search(msg)
        if m3:
            domain = m3.group(1).rstrip(".")
            src_port = addr[1]
            ip = self._last_dns_ip.get(src_port)
            if ip and self._valid_domain(domain):
                await self.e.record_dns(ip, domain)
                log.info("DNS(2): %s -> %s", ip, domain)
            return

        # DHCP
        m = RE_DHCP.search(msg)
        if m:
            await self.e.record_dhcp(
                m.group(2).lower(), m.group(1), m.group(3) or "")

    @staticmethod
    def _valid_domain(d):
        skip = {"local","localhost","localdomain","lan","home","corp","internal"}
        if not d or len(d) < 4: return False
        parts = d.lower().split(".")
        return len(parts) >= 2 and len(parts[-1]) >= 2 and parts[-1].isalpha() and parts[-1] not in skip

class NetFlowProtocol(asyncio.DatagramProtocol):
    def __init__(self, parser, enricher, buf, loop):
        self.p = parser
        self.e = enricher
        self.b = buf
        self.loop = loop
    def datagram_received(self, data, addr):
        self.loop.create_task(self._handle(data, addr[0]))
    async def _handle(self, data, src):
        try:
            records = self.p.parse(data, src)
            if records:
                log.info("Parsed %d records from %s, buf=%d", len(records), src, len(self.b))
            for rec in records:
                try:
                    uid = await self.e.get_user_id(rec["src_ip"])
                    dom = await self.e.get_domain(rec["src_ip"])
                    self.b.append(Flow(
                        rec["ts"], LOCATION_ID, uid,
                        rec["src_ip"], rec["dst_ip"], dom, "",
                        rec["proto"], rec["src_port"], rec["dst_port"],
                        rec["bytes_in"], rec["bytes_out"],
                        rec["packets_in"], rec["packets_out"],
                    ))
                except Exception as ex:
                    log.error("Flow enrich error: %s", ex)
        except Exception as ex:
            log.error("Handle error: %s", ex)

async def flush_loop(buf, writer, dns_buf):
    import threading
    def _flush_thread():
        import time as _time
        while True:
            _time.sleep(FLUSH_INT)
            if not buf:
                continue
            batch = buf[:200]
            del buf[:200]
            for attempt in range(3):
                try:
                    writer.insert_flows(batch)
                    break
                except Exception as ex:
                    log.error("Flush attempt %d error: %s", attempt+1, ex)
                    _time.sleep(2)
            if dns_buf:
                dbatch = dns_buf[:1000]
                del dns_buf[:1000]
                try:
                    writer.insert_dns(dbatch)
                except Exception as ex:
                    log.error("DNS flush error: %s", ex)
    t = threading.Thread(target=_flush_thread, daemon=True)
    t.start()
    log.info("Flush thread started (interval=%ds)", FLUSH_INT)
    while True:
        await asyncio.sleep(60)

async def main():
    log.info("NebulaNet Collector starting...")
    r   = await aioredis.from_url(REDIS_URL, decode_responses=False)
    pg  = await asyncpg.create_pool(PG_DSN, min_size=2, max_size=5)
    writer   = ClickHouseWriter()
    enricher = Enricher(r, pg)
    buf      = []
    dns_buf  = []
    enricher._dns_buf = dns_buf
    loop     = asyncio.get_event_loop()
    parser   = NetFlowParser()

    nt, _ = await loop.create_datagram_endpoint(
        lambda: NetFlowProtocol(parser, enricher, buf, loop),
        local_addr=("0.0.0.0", 2055))
    log.info("NetFlow listener on UDP 2055")

    st, _ = await loop.create_datagram_endpoint(
        lambda: SyslogProtocol(enricher, loop),
        local_addr=("0.0.0.0", 514))
    log.info("Syslog listener on UDP 514")

    ft = asyncio.create_task(flush_loop(buf, writer, dns_buf))
    stop = asyncio.Event()
    loop.add_signal_handler(signal.SIGTERM, stop.set)
    loop.add_signal_handler(signal.SIGINT,  stop.set)
    await stop.wait()

    log.info("Shutting down...")
    ft.cancel()
    nt.close()
    st.close()
    await pg.close()
    await r.aclose()

if __name__ == "__main__":
    asyncio.run(main())
