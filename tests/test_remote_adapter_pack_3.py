from __future__ import annotations

import html
import httpx

from app.intelligence_sources.adapters.australia_abn import AustraliaAbnLookupAdapter
from app.intelligence_sources.adapters.canada_corporations import CanadaFederalCorporationsAdapter
from app.intelligence_sources.adapters.charity_uk import UkCharityCommissionAdapter
from app.intelligence_sources.adapters.common import JsonHttpClient
from app.intelligence_sources.adapters.contracts import RemoteAdapterStatus, RemoteSourceQuery
from app.intelligence_sources.adapters.france_enterprises import FranceEnterpriseSearchAdapter
from app.intelligence_sources.adapters.poland_regon import PolandRegonAdapter


def test_france_open_name_search():
    def handler(request):
        assert request.url.params["q"]=="Airbus"
        return httpx.Response(200,json={"results":[{"siren":"383474814","nom_complet":"AIRBUS SAS","siege":{"siret":"38347481400011","code_postal":"31700","libelle_commune":"BLAGNAC"}}]},request=request)
    a=FranceEnterpriseSearchAdapter(client=JsonHttpClient(transport=httpx.MockTransport(handler)))
    r=a.search(RemoteSourceQuery("company_name","Airbus",country="FR"))
    assert r.status is RemoteAdapterStatus.SUCCESS
    assert r.records[0].identifiers["SIREN"]=="383474814"


def test_france_exact_siret_filters_false_candidates():
    def handler(request):
        return httpx.Response(200,json={"results":[
            {"siren":"111111111","nom_complet":"Wrong","siege":{"siret":"11111111100011"}},
            {"siren":"222222222","nom_complet":"Right","siege":{"siret":"22222222200022"}},
        ]},request=request)
    a=FranceEnterpriseSearchAdapter(client=JsonHttpClient(transport=httpx.MockTransport(handler)))
    r=a.search(RemoteSourceQuery("siret","22222222200022",country="FR"))
    assert [x.display_name for x in r.records]==["Right"]


def test_abn_requires_guid():
    a=AustraliaAbnLookupAdapter(authentication_guid=None)
    r=a.search(RemoteSourceQuery("abn","51824753556",country="AU"))
    assert r.status is RemoteAdapterStatus.NOT_CONFIGURED


def test_abn_exact_xml_lookup():
    xml='''<?xml version="1.0"?><ABRPayloadSearchResults><response><businessEntity202001><ABN><identifierValue>51824753556</identifierValue></ABN><entityStatus><entityStatusCode>Active</entityStatusCode></entityStatus><mainName><organisationName>EXAMPLE PTY LTD</organisationName></mainName><mainBusinessPhysicalAddress><stateCode>NSW</stateCode><postcode>2000</postcode></mainBusinessPhysicalAddress></businessEntity202001></response></ABRPayloadSearchResults>'''
    def handler(request):
        assert request.url.params["authenticationGuid"]=="guid"
        return httpx.Response(200,text=xml,headers={"content-type":"text/xml"},request=request)
    a=AustraliaAbnLookupAdapter(authentication_guid="guid",transport=httpx.MockTransport(handler))
    r=a.search(RemoteSourceQuery("abn","51824753556",country="AU"))
    assert r.records[0].display_name=="EXAMPLE PTY LTD"


def test_canada_uses_user_key_and_maps_exact_corporation():
    def handler(request):
        assert request.headers["user-key"]=="can-key"
        assert request.url.path.endswith("/1007.json")
        return httpx.Response(200,json=[{"corporationId":"1007","status":"Active","act":"CBCA","corporationNames":[{"CorporationName":{"name":"Example Canada Inc.","current":True}}],"businessNumbers":{"businessNumber":"123456789"}}],request=request)
    a=CanadaFederalCorporationsAdapter(api_key="can-key",client=JsonHttpClient(transport=httpx.MockTransport(handler)))
    r=a.search(RemoteSourceQuery("corporation_id","1007",country="CA"))
    assert r.status is RemoteAdapterStatus.SUCCESS
    assert r.records[0].identifiers["BUSINESS_NUMBER"]=="123456789"


def test_canada_requires_key():
    a=CanadaFederalCorporationsAdapter(api_key=None)
    assert a.search(RemoteSourceQuery("corporation_id","1007",country="CA")).status is RemoteAdapterStatus.NOT_CONFIGURED


def test_charity_name_search_uses_subscription_header():
    def handler(request):
        assert request.headers["ocp-apim-subscription-key"]=="uk-key"
        assert "searchCharityName" in request.url.path
        return httpx.Response(200,json=[{"reg_charity_number":1234567,"charity_name":"Example Foundation","status":"Registered"}],request=request)
    a=UkCharityCommissionAdapter(api_key="uk-key",client=JsonHttpClient(transport=httpx.MockTransport(handler)))
    r=a.search(RemoteSourceQuery("charity_name","Example Foundation",country="GB"))
    assert r.records[0].record_id=="1234567"


def test_charity_requires_key():
    a=UkCharityCommissionAdapter(api_key=None)
    assert a.search(RemoteSourceQuery("charity_number","123",country="GB")).status is RemoteAdapterStatus.NOT_CONFIGURED


def test_regon_requires_key():
    a=PolandRegonAdapter(user_key=None)
    assert a.search(RemoteSourceQuery("nip","1234567890",country="PL")).status is RemoteAdapterStatus.NOT_CONFIGURED


def test_regon_login_and_nip_search():
    calls=[]
    inner='<root><dane><Regon>123456789</Regon><Nip>1234567890</Nip><Krs>0000123456</Krs><Nazwa>EXAMPLE SP Z O O</Nazwa><Wojewodztwo>Mazowieckie</Wojewodztwo></dane></root>'
    login=f'''<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"><s:Body><ZalogujResponse><ZalogujResult>SID123</ZalogujResult></ZalogujResponse></s:Body></s:Envelope>'''
    search=f'''<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"><s:Body><DaneSzukajPodmiotyResponse><DaneSzukajPodmiotyResult>{html.escape(inner)}</DaneSzukajPodmiotyResult></DaneSzukajPodmiotyResponse></s:Body></s:Envelope>'''
    def handler(request):
        body=request.content.decode()
        calls.append(body)
        if "Zaloguj" in body: return httpx.Response(200,text=login,headers={"content-type":"application/soap+xml"},request=request)
        assert "SID123" in body and "<dc:Nip>1234567890</dc:Nip>" in body
        return httpx.Response(200,text=search,headers={"content-type":"application/soap+xml"},request=request)
    a=PolandRegonAdapter(user_key="key",transport=httpx.MockTransport(handler))
    r=a.search(RemoteSourceQuery("nip","123-456-78-90",country="PL"))
    assert r.status is RemoteAdapterStatus.SUCCESS
    assert r.records[0].identifiers["REGON"]=="123456789"
    assert len(calls)==2
