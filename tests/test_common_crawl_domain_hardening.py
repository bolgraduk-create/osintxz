import httpx
from app.infrastructure.open_web.common_crawl_client import CommonCrawlHttpClient
from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import OpenWebQuery, OpenWebStatus
from app.osint.open_web.providers.common_crawl import CommonCrawlOpenWebProvider

class Stub:
    def __init__(self,by_probe=None): self.by_probe=dict(by_probe or {}); self.calls=[]
    def latest_index(self,**kwargs): return {'id':'CC-MAIN-X','cdx-api':'https://index.test/x'}
    def recent_indexes(self, **kwargs): return [self.latest_index()]
    def query(self,**kwargs): self.calls.append(kwargs); return list(self.by_probe.get(kwargs['url_pattern'],[]))[:kwargs['limit']]
def rec(url,ts='20260820120000'): return {'url':url,'timestamp':ts,'status':'200','mime':'text/html','mime-detected':'text/html'}
def test_domain_uses_only_four_exact_homepage_probes():
    s=Stub(); r=CommonCrawlOpenWebProvider(s).search(OpenWebQuery(OsintTargetType.DOMAIN,'example.com',limit=10))
    assert r.status is OpenWebStatus.SUCCESS
    assert [c['url_pattern'] for c in s.calls]==['https://example.com/','http://example.com/','https://www.example.com/','http://www.example.com/']
    assert all('*' not in c['url_pattern'] for c in s.calls)
def test_domain_returns_capture():
    s=Stub({'https://example.com/':[rec('https://example.com/')]}); r=CommonCrawlOpenWebProvider(s).search(OpenWebQuery(OsintTargetType.DOMAIN,'example.com',limit=5)); assert r.documents[0].url=='https://example.com/'
def test_client_forces_exact_match_type():
    seen=[]
    c=CommonCrawlHttpClient(transport=httpx.MockTransport(lambda request:(seen.append(request) or httpx.Response(404))),max_attempts=1)
    c.query(cdx_api='https://index.test/x',url_pattern='https://example.com/',limit=5,timeout=5); assert seen[0].url.params['matchType']=='exact'
def test_503_retries_once_then_succeeds():
    calls={'n':0}
    def h(req): calls['n']+=1; return httpx.Response(503 if calls['n']==1 else 404)
    c=CommonCrawlHttpClient(transport=httpx.MockTransport(h),max_attempts=2,backoff_seconds=0); assert c.query(cdx_api='https://index.test/x',url_pattern='https://example.com/',limit=5,timeout=5)==[]; assert calls['n']==2
