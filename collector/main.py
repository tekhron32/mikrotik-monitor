"""
MikroTik Monitor Collector v2
"""
import asyncio,logging,os,re,socket,struct,threading,time,urllib.parse,urllib.request
from collections import defaultdict

logging.basicConfig(level=logging.INFO,format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log=logging.getLogger("collector")

CH_HOST=os.getenv("CLICKHOUSE_HOST","clickhouse")
CH_PORT=int(os.getenv("CLICKHOUSE_PORT","8123"))
CH_DB=os.getenv("CLICKHOUSE_DB","nebulanet")
CH_USER=os.getenv("CLICKHOUSE_USER","nebulanet")
CH_PASS=os.getenv("CLICKHOUSE_PASSWORD","nebulanet_secret")
LOC_ID=int(os.getenv("LOCATION_ID","1"))
FLUSH_INTERVAL=10
MAX_BATCH=2000

RE_DNS=re.compile(r"dns query from ([\d.]+):\s*#\d+\s+([\w.\-]+)\.",re.I)
RE_DHCP=re.compile(r"dhcp\S*\s+assigned\s+([\d.]+)\s+for\s+([\dA-Fa-f:]{17})(?:\s+\(([^)]*)\))?",re.I)

SKIP_SFX=(".compute.amazonaws.com",".compute.internal",".in-addr.arpa",".ip6.arpa",".m.ringcentral.com")
SKIP_PFX=("sip","stun")

def valid_domain(d):
    d=d.lower().rstrip(".")
    if not d or len(d)<4:return False
    for s in SKIP_SFX:
        if d.endswith(s):return False
    p=d.split(".")
    if p[0].replace("-","").isdigit():return False
    for x in SKIP_PFX:
        if p[0].startswith(x):return False
    skip={"local","localhost","localdomain","lan","home","corp","internal"}
    if p[-1] in skip:return False
    return len(p)>=2 and len(p[-1])>=2 and p[-1].isalpha()

def local_ip(ip):
    return ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172.")

class Writer:
    def __init__(self):
        self._fb=[]
        self._db=[]
        self._lock=threading.Lock()
    def add_flows(self,rows):
        with self._lock:self._fb.extend(rows)
    def add_dns(self,ip,domain,qt="A"):
        with self._lock:self._db.append({"ts":int(time.time()),"ip":ip,"domain":domain,"qt":qt})
    def flush(self):
        with self._lock:
            flows=self._fb[:MAX_BATCH];self._fb=self._fb[MAX_BATCH:]
            dns=self._db[:MAX_BATCH];self._db=self._db[MAX_BATCH:]
        if flows:self._ins_flows(flows)
        if dns:self._ins_dns(dns)
        with self._lock:
            fb,db=len(self._fb),len(self._db)
        if fb>500:log.warning("Flow buf: %d",fb)
        if db>200:log.warning("DNS buf: %d",db)
    def _post(self,q,body):
        import urllib.parse,urllib.request
        p=urllib.parse.urlencode({"database":CH_DB,"user":CH_USER,"password":CH_PASS,"query":q})
        req=urllib.request.Request(f"http://{CH_HOST}:{CH_PORT}/?{p}",data=body,method="POST")
        with urllib.request.urlopen(req,timeout=30) as r:return r.read()
    def _ins_flows(self,rows):
        try:
            body="\n".join(f"{r['ts']}\t{LOC_ID}\t{r['src']}\t{r['dst']}\t{r['sp']}\t{r['dp']}\t{r['proto']}\t{r['bytes']}\t{r['pkts']}" for r in rows).encode()
            self._post("INSERT INTO flows (ts,location_id,src_ip,dst_ip,src_port,dst_port,proto,bytes_in,packets_in) FORMAT TabSeparated",body)
            log.info("Flows: %d",len(rows))
        except Exception as e:log.error("Flows err: %s",e)
    def _ins_dns(self,rows):
        try:
            body="\n".join(f"{r['ts']}\t{LOC_ID}\t{r['ip']}\t{r['domain']}\t{r['qt']}" for r in rows).encode()
            self._post("INSERT INTO dns_log (ts,location_id,src_ip,domain,qtype) FORMAT TabSeparated",body)
            log.info("DNS: %d",len(rows))
        except Exception as e:log.error("DNS err: %s",e)
    def loop(self):
        while True:
            time.sleep(FLUSH_INTERVAL)
            try:self.flush()
            except Exception as e:log.error("Flush err: %s",e)

class NFParser:
    def __init__(self,w):
        self.w=w
        self.tmpl={}
    def parse(self,data,src):
        try:
            if len(data)<20:return
            if struct.unpack("!H",data[:2])[0]!=9:return
            count=struct.unpack("!H",data[2:4])[0]
            off=20;rows=[]
            for _ in range(count):
                if off+4>len(data):break
                fid,flen=struct.unpack("!HH",data[off:off+4])
                fdata=data[off+4:off+4+flen];off+=4+flen
                if fid==0:self._tmpl(fdata,src)
                elif fid>255:rows.extend(self._data(fdata,src,fid))
            if rows:self.w.add_flows(rows)
        except Exception as e:log.debug("NF err: %s",e)
    def _tmpl(self,data,src):
        off=0
        while off+4<=len(data):
            tid,fc=struct.unpack("!HH",data[off:off+4]);off+=4
            if fc==0:continue
            fields=[]
            for _ in range(fc):
                if off+4>len(data):break
                ft,fl=struct.unpack("!HH",data[off:off+4]);fields.append((ft,fl));off+=4
            self.tmpl[(src,tid)]=fields
    def _data(self,data,src,tid):
        tmpl=self.tmpl.get((src,tid))
        if not tmpl:return []
        rs=sum(f[1] for f in tmpl)
        if rs==0:return []
        rows=[];ts=int(time.time())
        for i in range(0,len(data)-rs+1,rs):
            rec=data[i:i+rs];off=0;f={}
            for ft,fl in tmpl:
                f[ft]=rec[off:off+fl];off+=fl
            try:
                s=socket.inet_ntoa(f.get(8,b'\x00'*4))
                d=socket.inet_ntoa(f.get(12,b'\x00'*4))
                if s=="0.0.0.0" or d=="0.0.0.0":continue
                b=int.from_bytes(f.get(1,b'\x00'*4),'big')
                if b==0:continue
                rows.append({"ts":ts,"src":s,"dst":d,
                    "sp":int.from_bytes(f.get(7,b'\x00\x00'),'big'),
                    "dp":int.from_bytes(f.get(11,b'\x00\x00'),'big'),
                    "proto":int.from_bytes(f.get(4,b'\x00'),'big'),
                    "bytes":b,"pkts":int.from_bytes(f.get(2,b'\x00'*4),'big')})
            except:continue
        return rows

class SyslogProto(asyncio.DatagramProtocol):
    def __init__(self,w):
        self.w=w
    def connection_made(self,t):log.info("Syslog on UDP :514")
    def datagram_received(self,data,addr):
        try:
            msg=data.decode("utf-8",errors="replace").strip()
            m=RE_DNS.search(msg)
            if m:
                ip=m.group(1);domain=m.group(2).rstrip(".")
                if local_ip(ip) and valid_domain(domain):
                    self.w.add_dns(ip,domain)
                    log.info("DNS: %s -> %s",ip,domain)
                return
            m=RE_DHCP.search(msg)
            if m:log.debug("DHCP: %s->%s(%s)",m.group(2),m.group(1),m.group(3) or "")
        except Exception as e:log.debug("Syslog err: %s",e)

class NFProto(asyncio.DatagramProtocol):
    def __init__(self,p):
        self.p=p
    def connection_made(self,t):log.info("NetFlow on UDP :2055")
    def datagram_received(self,data,addr):self.p.parse(data,addr[0])

async def main():
    log.info("Collector v2 starting...")
    w=Writer()
    threading.Thread(target=w.loop,daemon=True).start()
    loop=asyncio.get_running_loop()
    await loop.create_datagram_endpoint(lambda:NFProto(NFParser(w)),local_addr=("0.0.0.0",2055))
    await loop.create_datagram_endpoint(lambda:SyslogProto(w),local_addr=("0.0.0.0",514))
    log.info("Ready!")
    await asyncio.sleep(float("inf"))

if __name__=="__main__":
    asyncio.run(main())