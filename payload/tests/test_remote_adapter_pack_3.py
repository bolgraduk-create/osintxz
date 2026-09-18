from __future__ import annotations

import httpx

from app.intelligence_sources.adapters.australia_abn import AustraliaAbnLookupAdapter
from app.intelligence_sources.adapters.canada_corporations import CanadaFederalCorporationsAdapter
from app.intelligence_sources.adapters.common import JsonHttpClient
from app.intelligence_sources.adapters.contracts import RemoteAdapterStatus, RemoteSourceQuery
from app.intelligence_sources.adapters.france_enterprises import FranceEnterpriseSearchAdapter
from app.intelligence_sources.adapters.poland_regon import PolandRegonBirAdapter
from app.intelligence_sources.adapters.registry import RemoteSourceAdapterRegistry
from app.intelligence_sources.adapters.service import RemoteSourceAdapterService
from app.intelligence_sources.adapters.uk_charity import UkCharityCommissionAdapter


def test_france_name_is_candidate():
    def handler(request):
        return httpx.Response(200, json={"results":[{"siren":"351240049","nom_complet":"API","siege":{"siret":"35124004900012"}}]}, request=request)
    a=FranceEnterpriseSearchAdapter(client=JsonHttpClient(transport=httpx.MockTransport(handler)))
    r=a.search(RemoteSourceQuery("company_name","API",country="FR"))
    assert r.status is RemoteAdapterStatus.SUCCESS
    assert r.records[0].attributes["candidate_only"] is True


def test_france_exact_siren_filters_and_confirms():
    def handler(request):
        return httpx.Response(200, json={"results":[{"siren":"999999999","nom_complet":"Wrong"},{"siren":"351240049","nom_complet":"API","siege":{"siret":"35124004900012"}}]}, request=request)
    a=FranceEnterpriseSearchAdapter(client=JsonHttpClient(transport=httpx.MockTransport(handler)))
    r=a.search(RemoteSourceQuery("siren","351 240 049",country="FR"))
    assert len(r.records)==1 and r.records[0].record_id=="351240049"
    assert r.records[0].attributes["identity_confirmed"] is True


def test_abn_without_guid_not_configured_via_service():
    reg=RemoteSourceAdapterRegistry(); reg.register(AustraliaAbnLookupAdapter())
    r=RemoteSourceAdapterService(registry=reg).search(RemoteSourceQuery("abn","51824753556",country="AU"))
    assert r.provider_results[0].status is RemoteAdapterStatus.NOT_CONFIGURED


def test_abn_exact_jsonp_and_guid_not_in_result():
    def handler(request):
        assert request.url.params["guid"]=="secret-guid"
        return httpx.Response(200, text='callback({"Abn":"51824753556","EntityName":"EXAMPLE PTY LTD","Acn":"123456789","AbnStatus":"Active"})', request=request)
    a=AustraliaAbnLookupAdapter(guid="secret-guid",transport=httpx.MockTransport(handler))
    r=a.search(RemoteSourceQuery("abn","51 824 753 556",country="AU"))
    assert r.records[0].display_name=="EXAMPLE PTY LTD"
    assert "secret-guid" not in repr(r)


def test_abn_name_is_candidate():
    def handler(request):
        return httpx.Response(200, text='callback({"Names":[{"Abn":"51824753556","Name":"EXAMPLE","Score":"99"}]})', request=request)
    a=AustraliaAbnLookupAdapter(guid="g",transport=httpx.MockTransport(handler))
    r=a.search(RemoteSourceQuery("company_name","Example",country="AU"))
    assert r.records[0].attributes["candidate_only"] is True


def test_canada_without_key_not_configured():
    reg=RemoteSourceAdapterRegistry(); reg.register(CanadaFederalCorporationsAdapter())
    r=RemoteSourceAdapterService(registry=reg).search(RemoteSourceQuery("corporation_id","1007",country="CA"))
    assert r.provider_results[0].status is RemoteAdapterStatus.NOT_CONFIGURED


def test_canada_exact_maps_and_sends_user_key():
    def handler(request):
        assert request.headers["user-key"]=="key"
        return httpx.Response(200,json=[{"corporationId":"1007","status":"Active","corporationNames":[{"CorporationName":{"name":"Abbotsford Chamber","current":True}}],"businessNumbers":{"businessNumber":"106679285"}},None],request=request)
    a=CanadaFederalCorporationsAdapter(api_key="key",client=JsonHttpClient(transport=httpx.MockTransport(handler)))
    r=a.search(RemoteSourceQuery("corporation_id","1007",country="CA"))
    assert r.records[0].identifiers["BUSINESS_NUMBER"]=="106679285"


def test_uk_charity_name_candidate_and_header():
    def handler(request):
        assert request.headers["Ocp-Apim-Subscription-Key"]=="key"
        return httpx.Response(200,json=[{"organisation_number":1,"reg_charity_number":123,"charity_name":"Example Charity","reg_status":"R"}],request=request)
    a=UkCharityCommissionAdapter(api_key="key",client=JsonHttpClient(transport=httpx.MockTransport(handler)))
    r=a.search(RemoteSourceQuery("charity_name","Example",country="GB"))
    assert r.records[0].attributes["candidate_only"] is True


def test_uk_charity_number_exact_confirmed():
    def handler(request):
        assert request.url.path.endswith("/charityRegNumber/123/0")
        return httpx.Response(200,json={"organisation_number":1,"reg_charity_number":123,"charity_name":"Example Charity"},request=request)
    a=UkCharityCommissionAdapter(api_key="key",client=JsonHttpClient(transport=httpx.MockTransport(handler)))
    r=a.search(RemoteSourceQuery("charity_number","123",country="GB"))
    assert r.records[0].attributes["identity_confirmed"] is True


def test_regon_without_key_not_configured():
    reg=RemoteSourceAdapterRegistry(); reg.register(PolandRegonBirAdapter())
    r=RemoteSourceAdapterService(registry=reg).search(RemoteSourceQuery("regon","123456785",country="PL"))
    assert r.provider_results[0].status is RemoteAdapterStatus.NOT_CONFIGURED


def test_regon_login_search_and_sid_header():
    calls=[]
    def handler(request):
        calls.append(request)
        text=request.content.decode()
        if "Zaloguj" in text:
            return httpx.Response(200,text='<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"><s:Body><ZalogujResponse xmlns="http://CIS/BIR/PUBL/2014/07"><ZalogujResult>SID123</ZalogujResult></ZalogujResponse></s:Body></s:Envelope>',request=request)
        assert request.headers["sid"]=="SID123"
        inner='&lt;root&gt;&lt;dane&gt;&lt;Regon&gt;123456785&lt;/Regon&gt;&lt;Nip&gt;1234567890&lt;/Nip&gt;&lt;Nazwa&gt;EXAMPLE SP ZOO&lt;/Nazwa&gt;&lt;Miejscowosc&gt;Warszawa&lt;/Miejscowosc&gt;&lt;/dane&gt;&lt;/root&gt;'
        return httpx.Response(200,text=f'<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"><s:Body><DaneSzukajPodmiotyResponse xmlns="http://CIS/BIR/PUBL/2014/07"><DaneSzukajPodmiotyResult>{inner}</DaneSzukajPodmiotyResult></DaneSzukajPodmiotyResponse></s:Body></s:Envelope>',request=request)
    a=PolandRegonBirAdapter(user_key="key",transport=httpx.MockTransport(handler))
    r=a.search(RemoteSourceQuery("regon","123456785",country="PL"))
    assert len(calls)==2
    assert r.records[0].display_name=="EXAMPLE SP ZOO"


def test_regon_invalid_identifier_no_network():
    called=False
    def handler(request):
        nonlocal called; called=True; return httpx.Response(500,request=request)
    a=PolandRegonBirAdapter(user_key="key",transport=httpx.MockTransport(handler))
    r=a.search(RemoteSourceQuery("nip","123",country="PL"))
    assert r.status is RemoteAdapterStatus.NOT_SUPPORTED
    assert called is False
