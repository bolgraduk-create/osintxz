from __future__ import annotations
import json, time
from typing import Any
import httpx

class CommonCrawlHttpClient:
    COLLINFO_URL = "https://index.commoncrawl.org/collinfo.json"
    def __init__(self, *, transport=None, user_agent="OSINTXZ/1.0 CommonCrawlIndexClient", max_attempts=2, backoff_seconds=0.5):
        self.transport=transport; self.user_agent=user_agent
        self.max_attempts=max(1,min(int(max_attempts),3))
        self.backoff_seconds=max(0.0,min(float(backoff_seconds),5.0))
    def _client(self, timeout:int):
        return httpx.Client(timeout=httpx.Timeout(float(timeout)),follow_redirects=True,transport=self.transport,headers={"User-Agent":self.user_agent,"Accept":"application/json, application/x-ndjson, text/plain"})
    def _get_with_retry(self,url,*,timeout,params=None):
        last=None
        for attempt in range(1,self.max_attempts+1):
            try:
                with self._client(timeout) as c: r=c.get(url,params=params)
                if r.status_code not in {429,503} or attempt>=self.max_attempts: return r
                last=RuntimeError(f"Common Crawl rate limited request with HTTP {r.status_code}.")
            except (httpx.TimeoutException,httpx.ConnectError) as exc:
                last=exc
                if attempt>=self.max_attempts: raise
            if self.backoff_seconds>0: time.sleep(self.backoff_seconds*attempt)
        if last: raise last
        raise RuntimeError("Common Crawl request failed.")
    def latest_index(self,*,timeout=30)->dict[str,Any]:
        r=self._get_with_retry(self.COLLINFO_URL,timeout=timeout); r.raise_for_status(); payload=r.json()
        if not isinstance(payload,list) or not payload or not isinstance(payload[0],dict): raise RuntimeError("Common Crawl collinfo returned no valid indexes.")
        latest=dict(payload[0])
        if not str(latest.get('id','')).strip() or not str(latest.get('cdx-api','')).strip(): raise RuntimeError("Common Crawl latest index is missing id/cdx-api.")
        return latest
    def recent_indexes(self,*,limit=4,timeout=30)->list[dict[str,Any]]:
        safe=max(1,min(int(limit),8))
        r=self._get_with_retry(self.COLLINFO_URL,timeout=timeout)
        r.raise_for_status()
        payload=r.json()
        if not isinstance(payload,list):
            raise RuntimeError("Common Crawl collinfo returned invalid index list.")
        out=[]
        seen=set()
        for item in payload:
            if not isinstance(item,dict):
                continue
            crawl_id=str(item.get('id','')).strip()
            cdx_api=str(item.get('cdx-api','')).strip()
            if not crawl_id or not cdx_api or crawl_id in seen:
                continue
            seen.add(crawl_id)
            out.append(dict(item))
            if len(out)>=safe:
                break
        if not out:
            raise RuntimeError("Common Crawl collinfo returned no usable indexes.")
        return out
    def query(self,*,cdx_api,url_pattern,limit,timeout=30):
        safe=max(1,min(int(limit),250))
        r=self._get_with_retry(cdx_api,timeout=timeout,params={"url":url_pattern,"output":"json","matchType":"exact","limit":str(safe)})
        if r.status_code==404: return []
        r.raise_for_status(); out=[]
        for line in r.text.splitlines():
            line=line.strip()
            if not line: continue
            try: item=json.loads(line)
            except json.JSONDecodeError: continue
            if isinstance(item,dict): out.append(item)
            if len(out)>=safe: break
        return out
