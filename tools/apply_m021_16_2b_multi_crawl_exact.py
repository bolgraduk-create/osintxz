from __future__ import annotations

from pathlib import Path


HTTP = Path("app/infrastructure/open_web/common_crawl_client.py")
META = Path("app/infrastructure/open_web/common_crawl_metadata_client.py")
PROVIDER = Path("app/osint/open_web/providers/common_crawl.py")


def patch_http(text: str) -> str:
    if "def recent_indexes(" in text:
        return text

    needle = """    def latest_index(self,*,timeout=30)->dict[str,Any]:
        r=self._get_with_retry(self.COLLINFO_URL,timeout=timeout); r.raise_for_status(); payload=r.json()
        if not isinstance(payload,list) or not payload or not isinstance(payload[0],dict): raise RuntimeError("Common Crawl collinfo returned no valid indexes.")
        latest=dict(payload[0])
        if not str(latest.get('id','')).strip() or not str(latest.get('cdx-api','')).strip(): raise RuntimeError("Common Crawl latest index is missing id/cdx-api.")
        return latest
"""

    replacement = needle + """    def recent_indexes(self,*,limit=4,timeout=30)->list[dict[str,Any]]:
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
"""

    if needle not in text:
        raise RuntimeError("HTTP latest_index contract not found.")
    return text.replace(needle, replacement, 1)


def patch_meta(text: str) -> str:
    if "def recent_indexes(" in text:
        return text

    needle = """    def query(self,*,cdx_api,url_pattern,limit,timeout=30):
"""

    method = """    def recent_indexes(self,*,limit=4,timeout=30):
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

"""

    if needle not in text:
        raise RuntimeError("Metadata query contract not found.")
    return text.replace(needle, method + needle, 1)


def patch_provider(text: str) -> str:
    if '"query_strategy":"bounded_exact_variants_multi_crawl"' in text:
        return text

    old_proto = """class CommonCrawlClientProtocol(Protocol):
    def latest_index(self,*,timeout:int=30)->dict[str,Any]: ...
    def query(self,*,cdx_api:str,url_pattern:str,limit:int,timeout:int=30)->list[dict[str,Any]]: ...
"""

    new_proto = """class CommonCrawlClientProtocol(Protocol):
    def latest_index(self,*,timeout:int=30)->dict[str,Any]: ...
    def recent_indexes(self,*,limit:int=4,timeout:int=30)->list[dict[str,Any]]: ...
    def query(self,*,cdx_api:str,url_pattern:str,limit:int,timeout:int=30)->list[dict[str,Any]]: ...
"""
    if old_proto in text:
        text = text.replace(old_proto, new_proto, 1)

    old_search = """    def search(self,query):
        if not self.supports(query): return OpenWebResult(provider=self.info.name,status=OpenWebStatus.NOT_SUPPORTED,error="DOMAIN/URL only.")
        try:
            idx=self.client.latest_index(timeout=query.timeout); crawl_id=str(idx['id']).strip(); cdx=str(idx['cdx-api']).strip(); probes=self._probes(query)
            docs=self._discover(query=query,cdx_api=cdx,crawl_id=crawl_id,probes=probes)
            return OpenWebResult(provider=self.info.name,status=OpenWebStatus.SUCCESS,documents=docs,metadata={"crawl_id":crawl_id,"cdx_api":cdx,"query_probes":probes,"query_strategy":"bounded_exact_probes","records_returned":len(docs),"public_index_only":True,"warc_body_fetched":False,"broad_domain_query":False})
        except Exception as exc:
            return OpenWebResult(provider=self.info.name,status=OpenWebStatus.FAILED,error=str(exc) or exc.__class__.__name__,metadata={"failure_isolated":True,"public_index_only":True,"broad_domain_query":False})
"""

    new_search = """    def search(self,query):
        if not self.supports(query):
            return OpenWebResult(
                provider=self.info.name,
                status=OpenWebStatus.NOT_SUPPORTED,
                error="DOMAIN/URL only.",
            )
        try:
            probes=self._probes(query)
            indexes=self.client.recent_indexes(
                limit=4,
                timeout=query.timeout,
            )
            docs=[]
            crawl_ids=[]
            per_crawl=[]
            seen=set()
            for idx in indexes:
                if len(docs)>=query.limit:
                    break
                crawl_id=str(idx.get("id","")).strip()
                cdx=str(idx.get("cdx-api","")).strip()
                if not crawl_id or not cdx:
                    continue
                crawl_ids.append(crawl_id)
                remaining=query.limit-len(docs)
                crawl_query=OpenWebQuery(
                    target_type=query.target_type,
                    value=query.value,
                    case_id=query.case_id,
                    limit=remaining,
                    timeout=query.timeout,
                    depth=query.depth,
                    parent_entity_id=query.parent_entity_id,
                )
                current=self._discover(
                    query=crawl_query,
                    cdx_api=cdx,
                    crawl_id=crawl_id,
                    probes=probes,
                )
                accepted=0
                for document in current:
                    key=document.url.strip().casefold()
                    if not key or key in seen:
                        continue
                    seen.add(key)
                    docs.append(document)
                    accepted+=1
                    if len(docs)>=query.limit:
                        break
                per_crawl.append(
                    {
                        "crawl_id":crawl_id,
                        "records_returned":accepted,
                    }
                )
            return OpenWebResult(
                provider=self.info.name,
                status=OpenWebStatus.SUCCESS,
                documents=docs,
                metadata={
                    "crawl_ids":crawl_ids,
                    "crawl_count":len(crawl_ids),
                    "per_crawl":per_crawl,
                    "query_probes":probes,
                    "query_strategy":"bounded_exact_variants_multi_crawl",
                    "records_returned":len(docs),
                    "public_index_only":True,
                    "warc_body_fetched":False,
                    "broad_domain_query":False,
                },
            )
        except Exception as exc:
            return OpenWebResult(
                provider=self.info.name,
                status=OpenWebStatus.FAILED,
                error=str(exc) or exc.__class__.__name__,
                metadata={
                    "failure_isolated":True,
                    "public_index_only":True,
                    "broad_domain_query":False,
                },
            )
"""

    if old_search not in text:
        raise RuntimeError("Provider search contract not found.")
    return text.replace(old_search, new_search, 1)


def main() -> int:
    for path in (HTTP, META, PROVIDER):
        if not path.is_file():
            print(f"[FAIL] Missing {path}")
            return 1

    originals = {
        HTTP: HTTP.read_text(encoding="utf-8"),
        META: META.read_text(encoding="utf-8"),
        PROVIDER: PROVIDER.read_text(encoding="utf-8"),
    }

    try:
        updated = {
            HTTP: patch_http(originals[HTTP]),
            META: patch_meta(originals[META]),
            PROVIDER: patch_provider(originals[PROVIDER]),
        }
        for path, text in updated.items():
            compile(text, str(path), "exec")
    except Exception as exc:
        print(f"[FAIL] {exc}")
        return 1

    for path, text in updated.items():
        backup = path.with_suffix(".py.m021_16_2b_backup")
        if not backup.exists():
            backup.write_text(originals[path], encoding="utf-8")
        path.write_text(text, encoding="utf-8")

    print("[PASS] Added bounded recent-index discovery (max 4 crawls).")
    print("[PASS] Common Crawl remains exact-match only.")
    print("[PASS] Results deduplicated across crawl indexes.")
    print("[PASS] Existing WARC/extraction/persistence pipeline preserved.")
    print("[PASS] Raw ZipNum fallback preserved.")
    print("[PASS] No database migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
