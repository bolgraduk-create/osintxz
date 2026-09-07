from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Protocol
from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebDocument, OpenWebProviderInfo, OpenWebQuery, OpenWebResult, OpenWebStatus
from app.osint.open_web.provider import OpenWebProvider

class CommonCrawlClientProtocol(Protocol):
    def latest_index(self,*,timeout:int=30)->dict[str,Any]: ...
    def recent_indexes(self,*,limit:int=4,timeout:int=30)->list[dict[str,Any]]: ...
    def query(self,*,cdx_api:str,url_pattern:str,limit:int,timeout:int=30)->list[dict[str,Any]]: ...

class CommonCrawlOpenWebProvider(OpenWebProvider):
    def __init__(self,client:CommonCrawlClientProtocol):
        self.client=client
        self._info=OpenWebProviderInfo(name="common_crawl",display_name="Common Crawl",supported_targets=frozenset({OsintTargetType.DOMAIN,OsintTargetType.URL}),passive=True,public_data_only=True,requires_credentials=False,default_enabled=True,priority=10)
    @property
    def info(self): return self._info
    def search(self,query):
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
    def _discover(self,*,query,cdx_api,crawl_id,probes):
        records=[]
        for probe in probes:
            remaining=query.limit-len(records)
            if remaining<=0: break
            records.extend(self.client.query(cdx_api=cdx_api,url_pattern=probe,limit=remaining,timeout=query.timeout))
        records.sort(key=lambda x:str(x.get('timestamp','')),reverse=True); seen=set(); docs=[]
        for rec in records:
            url=str(rec.get('url','')).strip(); status=str(rec.get('status','')).strip()
            if not url or (status and not status.startswith('2')): continue
            key=url.casefold()
            if key in seen: continue
            seen.add(key)
            docs.append(OpenWebDocument(url=url,provider=self.info.name,captured_at=self._timestamp(rec.get('timestamp')),content_type=str(rec.get('mime-detected') or rec.get('mime') or '').strip() or None,confidence=0.85,reliability=0.90,metadata={"crawl_id":crawl_id,"timestamp":rec.get('timestamp'),"status":rec.get('status'),"digest":rec.get('digest'),"languages":rec.get('languages'),"encoding":rec.get('encoding'),"warc_filename":rec.get('filename'),"warc_offset":rec.get('offset'),"warc_length":rec.get('length'),"public_index_only":True,"warc_body_fetched":False}))
            if len(docs)>=query.limit: break
        return docs
    @staticmethod
    def _probes(query):
        value = query.value.strip()

        if query.target_type is OsintTargetType.URL:
            return CommonCrawlOpenWebProvider._url_variants(value)

        domain = (
            value.lower()
            .removeprefix("http://")
            .removeprefix("https://")
            .split("/", 1)[0]
            .rstrip(".")
        )
        if domain.startswith("www."):
            domain = domain[4:]

        return [
            f"https://{domain}/",
            f"http://{domain}/",
            f"https://www.{domain}/",
            f"http://www.{domain}/",
        ]

    @staticmethod
    def _url_variants(value: str) -> list[str]:
        from urllib.parse import quote, unquote, urlsplit, urlunsplit

        raw = value.strip()
        if not raw:
            return []

        if "://" not in raw:
            raw = "https://" + raw

        try:
            parsed = urlsplit(raw)
        except ValueError:
            return [value.strip()]

        host = (parsed.hostname or "").strip().rstrip(".").casefold()
        if not host:
            return [value.strip()]

        port = parsed.port
        host_with_port = f"{host}:{port}" if port is not None else host

        path = parsed.path or "/"

        try:
            path = quote(
                unquote(path),
                safe="/:@!$&'()*+,;=-._~",
            )
        except Exception:
            pass

        query_string = parsed.query or ""

        hosts = [host_with_port]
        if host.startswith("www."):
            bare = host[4:]
            hosts.append(
                f"{bare}:{port}" if port is not None else bare
            )
        else:
            www = f"www.{host}"
            hosts.append(
                f"{www}:{port}" if port is not None else www
            )

        schemes = []
        scheme = parsed.scheme.casefold()
        if scheme in {"http", "https"}:
            schemes.append(scheme)
            schemes.append("http" if scheme == "https" else "https")
        else:
            schemes.extend(("https", "http"))

        paths = [path]
        if path == "/":
            paths.append("")
        elif path.endswith("/"):
            paths.append(path.rstrip("/"))
        else:
            paths.append(path + "/")

        variants: list[str] = []
        seen: set[str] = set()

        for scheme_name in schemes:
            for host_name in hosts:
                for path_name in paths:
                    candidate = urlunsplit(
                        (
                            scheme_name,
                            host_name,
                            path_name,
                            query_string,
                            "",
                        )
                    )
                    key = candidate.casefold()
                    if key in seen:
                        continue
                    seen.add(key)
                    variants.append(candidate)

        original = value.strip()
        if original:
            key = original.casefold()
            if key not in seen:
                variants.insert(0, original)

        return variants[:8]
    @staticmethod
    def _timestamp(value):
        text=str(value or '').strip()
        if len(text)!=14 or not text.isdigit(): return None
        try: dt=datetime.strptime(text,'%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
        except ValueError: return None
        return dt.isoformat().replace('+00:00','Z')
