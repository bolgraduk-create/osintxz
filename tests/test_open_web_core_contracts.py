from __future__ import annotations

import pytest

from app.osint.models import OsintTargetType
from app.osint.open_web.contracts import (
    OpenWebDocument, OpenWebProviderInfo, OpenWebQuery, OpenWebResult, OpenWebStatus,
)
from app.osint.open_web.provider import OpenWebProvider
from app.osint.open_web.registry import OpenWebProviderRegistry
from app.osint.open_web.service import OpenWebDiscoveryService


class StubProvider(OpenWebProvider):
    def __init__(self, info, result=None, raises=None):
        self._info = info
        self.result = result
        self.raises = raises
        self.calls = 0

    @property
    def info(self):
        return self._info

    def search(self, query):
        self.calls += 1
        if self.raises:
            raise self.raises
        return self.result or OpenWebResult(provider=self.info.name, status=OpenWebStatus.SUCCESS)


def info(name='public', **kwargs):
    defaults = dict(
        name=name, display_name=name.title(),
        supported_targets=frozenset({OsintTargetType.USERNAME, OsintTargetType.EMAIL, OsintTargetType.PHONE, OsintTargetType.DOMAIN, OsintTargetType.URL}),
        passive=True, public_data_only=True, requires_credentials=False, default_enabled=True, priority=100,
    )
    defaults.update(kwargs)
    return OpenWebProviderInfo(**defaults)


def test_query_validation():
    with pytest.raises(ValueError): OpenWebQuery(OsintTargetType.USERNAME, '   ')
    with pytest.raises(ValueError): OpenWebQuery(OsintTargetType.USERNAME, 'x', limit=0)
    with pytest.raises(ValueError): OpenWebQuery(OsintTargetType.USERNAME, 'x', timeout=0)

def test_document_extraction_text_combines_available_text_fields():
    doc = OpenWebDocument(url='https://e.test/a', provider='p', title='Title', snippet='Snippet', text='Body')
    assert doc.extraction_text == 'Title\nSnippet\nBody'

def test_automatic_provider_must_be_passive_public_keyless_and_enabled():
    query = OpenWebQuery(OsintTargetType.USERNAME, 'alice')
    registry = OpenWebProviderRegistry()
    eligible = StubProvider(info('eligible'))
    active = StubProvider(info('active', passive=False))
    credentialed = StubProvider(info('credentialed', requires_credentials=True))
    private = StubProvider(info('private', public_data_only=False))
    disabled = StubProvider(info('disabled', default_enabled=False))
    for provider in (eligible, active, credentialed, private, disabled): registry.register(provider)
    assert registry.automatic_for(query) == (eligible,)

def test_unsupported_target_provider_is_not_selected():
    provider = StubProvider(info('domain', supported_targets=frozenset({OsintTargetType.DOMAIN})))
    registry = OpenWebProviderRegistry(); registry.register(provider)
    assert registry.automatic_for(OpenWebQuery(OsintTargetType.PHONE, '+380671234567')) == ()

def test_provider_failure_is_isolated_and_other_provider_continues():
    registry = OpenWebProviderRegistry()
    bad = StubProvider(info('bad', priority=10), raises=RuntimeError('boom'))
    good = StubProvider(info('good', priority=20), OpenWebResult(provider='good', status=OpenWebStatus.SUCCESS, documents=[OpenWebDocument(url='https://e.test/a', provider='good')]))
    registry.register(bad); registry.register(good)
    response = OpenWebDiscoveryService(registry).discover(OpenWebQuery(OsintTargetType.USERNAME, 'alice'))
    assert len(response.results) == 2
    assert response.results[0].status is OpenWebStatus.FAILED
    assert response.results[0].metadata['failure_isolated'] is True
    assert [d.url for d in response.documents] == ['https://e.test/a']

def test_duplicate_documents_from_same_provider_are_collapsed():
    docs = [OpenWebDocument(url='https://e.test/a', provider='p'), OpenWebDocument(url='https://e.test/a', provider='p')]
    provider = StubProvider(info('p'), OpenWebResult(provider='p', status=OpenWebStatus.SUCCESS, documents=docs))
    registry = OpenWebProviderRegistry(); registry.register(provider)
    response = OpenWebDiscoveryService(registry).discover(OpenWebQuery(OsintTargetType.URL, 'https://seed.test'))
    assert len(response.documents) == 1

def test_same_url_from_different_providers_preserves_independent_provenance():
    registry = OpenWebProviderRegistry()
    for name in ('one', 'two'):
        registry.register(StubProvider(info(name), OpenWebResult(provider=name, status=OpenWebStatus.SUCCESS, documents=[OpenWebDocument(url='https://e.test/a', provider=name)])))
    response = OpenWebDiscoveryService(registry).discover(OpenWebQuery(OsintTargetType.USERNAME, 'alice'))
    assert len(response.documents) == 2
    assert {d.provider for d in response.documents} == {'one', 'two'}

def test_partial_result_documents_remain_usable():
    provider = StubProvider(info('p'), OpenWebResult(provider='p', status=OpenWebStatus.PARTIAL, error='some pages unavailable', documents=[OpenWebDocument(url='https://e.test/a', provider='p')]))
    registry = OpenWebProviderRegistry(); registry.register(provider)
    response = OpenWebDiscoveryService(registry).discover(OpenWebQuery(OsintTargetType.EMAIL, 'a@example.com'))
    assert len(response.documents) == 1

def test_registry_duplicate_name_requires_explicit_replace():
    registry = OpenWebProviderRegistry(); registry.register(StubProvider(info('p')))
    with pytest.raises(ValueError): registry.register(StubProvider(info('p')))
