from __future__ import annotations
from dataclasses import dataclass
import gzip, json, re
from pathlib import Path
from urllib.parse import urlsplit
import httpx

@dataclass(frozen=True, slots=True)
class ZipNumBlock:
    first_key: str
    timestamp: str
    shard: str
    offset: int
    length: int
    ordinal: int

class CommonCrawlRawIndexClient:
    DATA_BASE="https://data.commoncrawl.org"
    _CRAWL_RE=re.compile(r"^CC-MAIN-\d{4}-\d{2}$")
    def __init__(self,*,transport=None,user_agent="OSINTXZ/1.0 CommonCrawlRawIndex",cluster_probe_bytes=65536,max_cluster_probes=28,max_cdx_block_bytes=1000000):
        self.transport=transport; self.user_agent=user_agent
        self.cluster_probe_bytes=max(4096,min(int(cluster_probe_bytes),262144))
        self.max_cluster_probes=max(4,min(int(max_cluster_probes),40))
        self.max_cdx_block_bytes=max(32768,min(int(max_cdx_block_bytes),4000000))
    def query(self,*,crawl_id,url_pattern,limit,timeout=30):
        self._validate_crawl_id(crawl_id)
        block=self._find_block(crawl_id=crawl_id,target_key=self._surt_key(url_pattern),timeout=timeout)
        if block is None:return []
        if block.length>self.max_cdx_block_bytes: raise ValueError("Selected CDX block exceeds bounded-size limit.")
        payload=self._range_get(self._shard_url(crawl_id,block.shard),offset=block.offset,length=block.length,timeout=timeout)
        try:text=gzip.decompress(payload).decode("utf-8",errors="replace")
        except OSError as exc: raise ValueError("Invalid gzip CDX block.") from exc
        wanted=self._normalize_exact_url(url_pattern); rows=[]; safe=max(1,min(int(limit),250))
        for line in text.splitlines():
            parts=line.split(" ",2)
            if len(parts)!=3:continue
            _,timestamp,raw_json=parts
            try:item=json.loads(raw_json)
            except json.JSONDecodeError:continue
            if not isinstance(item,dict):continue
            url=str(item.get("url","")).strip()
            if not url or self._normalize_exact_url(url)!=wanted:continue
            item.setdefault("timestamp",timestamp); rows.append(item)
            if len(rows)>=safe:break
        return rows
    def _find_block(self,*,crawl_id,target_key,timeout):
        url=self._cluster_url(crawl_id); size=self._content_length(url,timeout=timeout)
        low,high,best=0,size-1,None
        for _ in range(self.max_cluster_probes):
            if low>high:break
            mid=(low+high)//2; start=max(0,mid-self.cluster_probe_bytes//4); length=min(self.cluster_probe_bytes,size-start)
            parsed=[]
            for a,b,raw in self._complete_lines(self._range_get(url,offset=start,length=length,timeout=timeout),absolute_start=start):
                block=self._parse_cluster_line(raw)
                if block is not None:parsed.append((a,b,block))
            if not parsed:break
            le=[x for x in parsed if x[2].first_key<=target_key]; gt=[x for x in parsed if x[2].first_key>target_key]
            if le:
                c=le[-1]
                if best is None or c[2].first_key>=best.first_key:best=c[2]
                low=c[1]+1
            else:high=parsed[0][0]-1
            if gt:high=min(high,gt[0][0]-1)
            if high-low<2:break
        return best
    def _content_length(self,url,*,timeout):
        with self._client(timeout) as c:r=c.head(url)
        r.raise_for_status(); v=r.headers.get("Content-Length")
        if not v:raise RuntimeError("cluster.idx Content-Length is unavailable.")
        return int(v)
    def _range_get(self,url,*,offset,length,timeout):
        with self._client(timeout) as c:r=c.get(url,headers={"Range":f"bytes={offset}-{offset+length-1}"})
        if r.status_code not in {200,206}:r.raise_for_status()
        if r.status_code==206 and len(r.content)>length:raise ValueError("Range response exceeded requested byte budget.")
        return r.content
    def _client(self,timeout):
        return httpx.Client(timeout=httpx.Timeout(float(timeout)),follow_redirects=True,transport=self.transport,headers={"User-Agent":self.user_agent,"Accept":"application/octet-stream,text/plain"})
    @staticmethod
    def _complete_lines(data,*,absolute_start):
        if not data:return []
        first=0
        if absolute_start>0:
            nl=data.find(b"\n")
            if nl<0:return []
            first=nl+1
        out=[]; pos=first
        while pos<len(data):
            nl=data.find(b"\n",pos)
            if nl<0:break
            raw=data[pos:nl].decode("utf-8",errors="replace").strip()
            if raw:out.append((absolute_start+pos,absolute_start+nl,raw))
            pos=nl+1
        return out
    @staticmethod
    def _parse_cluster_line(line):
        p=line.split()
        if len(p)<6:return None
        try:return ZipNumBlock(p[0],p[1],p[2],int(p[3]),int(p[4]),int(p[5]))
        except (TypeError,ValueError):return None
    @classmethod
    def _surt_key(cls,url):
        p=urlsplit(url.strip()); host=(p.hostname or "").lower().rstrip(".")
        if not host:raise ValueError("Exact URL must contain a hostname.")
        key=",".join(reversed([x for x in host.split(".") if x]))+")"+(p.path or "/")
        if p.query:key+="?"+p.query
        return key
    @staticmethod
    def _normalize_exact_url(value):
        p=urlsplit(value.strip()); scheme=(p.scheme or "https").lower(); host=(p.hostname or "").lower().rstrip("."); port=p.port
        if port and not ((scheme=="http" and port==80) or (scheme=="https" and port==443)):host=f"{host}:{port}"
        return f"{scheme}://{host}{p.path or '/'}"+(f"?{p.query}" if p.query else "")
    @classmethod
    def _validate_crawl_id(cls,crawl_id):
        if not cls._CRAWL_RE.fullmatch(str(crawl_id).strip()):raise ValueError("Invalid Common Crawl crawl id.")
    @classmethod
    def _cluster_url(cls,crawl_id):return f"{cls.DATA_BASE}/cc-index/collections/{crawl_id}/indexes/cluster.idx"
    @classmethod
    def _shard_url(cls,crawl_id,shard):
        safe=Path(shard).name
        if not re.fullmatch(r"cdx-\d{5}\.gz",safe):raise ValueError("Invalid Common Crawl CDX shard name.")
        return f"{cls.DATA_BASE}/cc-index/collections/{crawl_id}/indexes/{safe}"
