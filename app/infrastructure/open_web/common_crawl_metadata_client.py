from __future__ import annotations
import json,re
from pathlib import Path
class CommonCrawlMetadataClient:
    _CRAWL_RE=re.compile(r"CC-MAIN-\d{4}-\d{2}")
    def __init__(self,*,primary,raw_index,state_path="storage/cache/common_crawl/crawl_state.json",bootstrap_crawl_id="CC-MAIN-2026-34"):
        self.primary=primary; self.raw_index=raw_index; self.state_path=Path(state_path); self.bootstrap_crawl_id=bootstrap_crawl_id; self._active_crawl_id=None; self._using_fallback=False
    def latest_index(self,*,timeout=30):
        try:info=self.primary.latest_index(timeout=timeout)
        except Exception:
            crawl_id=self._load_crawl_id() or self.bootstrap_crawl_id; self._active_crawl_id=crawl_id; self._using_fallback=True
            return {"id":crawl_id,"cdx-api":f"raw-zipnum://{crawl_id}","metadata_fallback":"raw_zipnum"}
        crawl_id=str(info["id"]).strip(); self._active_crawl_id=crawl_id; self._using_fallback=False; self._save_crawl_id(crawl_id); return info
    def recent_indexes(self,*,limit=4,timeout=30):
        safe=max(1,min(int(limit),8))
        try:
            rows=self.primary.recent_indexes(limit=safe,timeout=timeout)
        except Exception:
            crawl_id=self._load_crawl_id() or self.bootstrap_crawl_id
            return [{
                "id":crawl_id,
                "cdx-api":f"raw-zipnum://{crawl_id}",
                "metadata_fallback":"raw_zipnum",
            }]
        out=[]
        seen=set()
        for row in rows:
            crawl_id=str(row.get("id","")).strip()
            cdx_api=str(row.get("cdx-api","")).strip()
            if not self._CRAWL_RE.fullmatch(crawl_id) or not cdx_api:
                continue
            if crawl_id in seen:
                continue
            seen.add(crawl_id)
            out.append(dict(row))
            if len(out)>=safe:
                break
        if out:
            self._active_crawl_id=str(out[0]["id"]).strip()
            self._using_fallback=False
            self._save_crawl_id(self._active_crawl_id)
        return out

    def query(self,*,cdx_api,url_pattern,limit,timeout=30):
        crawl_id=self._crawl_from_api(cdx_api) or self._active_crawl_id
        if not self._using_fallback:
            try:return self.primary.query(cdx_api=cdx_api,url_pattern=url_pattern,limit=limit,timeout=timeout)
            except Exception:pass
        crawl_id=crawl_id or self._load_crawl_id() or self.bootstrap_crawl_id
        return self.raw_index.query(crawl_id=crawl_id,url_pattern=url_pattern,limit=limit,timeout=timeout)
    def _load_crawl_id(self):
        try:p=json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError,json.JSONDecodeError):return None
        c=str(p.get("crawl_id","")).strip(); return c if self._CRAWL_RE.fullmatch(c) else None
    def _save_crawl_id(self,c):
        if not self._CRAWL_RE.fullmatch(c):return
        try:self.state_path.parent.mkdir(parents=True,exist_ok=True); self.state_path.write_text(json.dumps({"crawl_id":c},indent=2),encoding="utf-8")
        except OSError:return
    @classmethod
    def _crawl_from_api(cls,v):
        m=cls._CRAWL_RE.search(str(v)); return m.group(0) if m else None
