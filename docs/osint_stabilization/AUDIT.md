# OSINT stabilization audit — 2026-09-05

Initial working tree already contains extensive tracked/untracked changes and deleted legacy tests. No reset or migration performed. Baseline status and diff statistics are recorded alongside this report; source backups are in `backups/osint_stabilization_20260905`.

## Evidence and scope

Project interpreter: `.venv/Scripts/python.exe`. Sandbox initially denied access to its WindowsApps base interpreter; approved execution succeeded. Full existing suite ran twice before edits: **336 passed, 38 failed (374 collected)**. Machine-readable baseline: `baseline_tests.xml`. Passing offline tests do not establish availability of live upstreams or desktop readiness.

| Component | Status | Working / existing | Broken / partial / missing | Risk | Next action |
|---|---|---|---|---|---|
| Composition | PARTIAL | ServiceContainer wires manager, pipeline, enrichment, persistence, Open-Web, registry | End-to-end runtime not yet verified | High integration surface | Preserve existing layers |
| Username | PARTIAL | Quality canonicalization, fusion, four passive default providers and tests | Legacy routing expectations conflict; CLI command tests fail | Incorrect confidence/noise admission | Resolve test contracts and runtime availability |
| Email | BROKEN | Gravatar and exact-page providers exist | Router excludes SUPPORT for registration goal, omitting Holehe/SocialScan | Silent empty registration route | Include safe SUPPORT for this goal |
| Phone | PARTIAL | phonenumbers service, LocalPhone, PhoneInfoga, three Open-Web providers | Parenthesized national input rejected; country context not wired from UI | Ambiguous national identifiers | Fix detection, retain explicit region policy |
| Caller-ID tags | MISSING | No provider contract found in inspected OSINT tree | Lawful manual/conditional foundation required | Labels mistaken for identity | Add only provenance-bearing possible aliases |
| Domain/URL | PARTIAL | Safe default goals and historical providers exist | Common Crawl legacy stubs lack recent_indexes; robustness not fully verified | Active modes / SSRF | Audit all default route modes and fetch boundaries |
| IP | BROKEN UI | OsintTargetType.IP and NETWORK_ENRICHMENT already exist | UI detector has no ipaddress branch | IPv4 misclassified as username | Add detection before username/phone |
| Open-Web | PARTIAL | Provider isolation, selection, document dedup; generic UI goal already present | Extraction/e2e baseline failures; aggregate provenance review pending | Candidate/evidence boundary | Diagnose failures individually |
| Common Crawl WARC | BROKEN | Bounded gzip extraction exists | client.get buffers response before cap; accepts ignored Range/200; no Content-Range validation | Unbounded memory/network | Stream, require 206, validate range, cap before append |
| Public documents | PARTIAL | Streaming, public URL validation, redirect limit, document extraction exist | iter_bytes decoding and ZIP/XML bounds need deeper review | Memory/decompression | Adversarial tests |
| Registry | PARTIAL | Separate domain/query contracts, GLEIF provider, composition wiring | RegistryIntelligenceService only aggregates records; no persistence/fusion in this path | Records absent from graph/case | Reuse Source/Evidence/Entity services |
| Court/business catalog | MISSING/PARTIAL | GLEIF foundation | Expanded official-access catalog absent in inspected provider tree | Unsupported access claims | Add verified catalog without private APIs |
| Persistence | PARTIAL | Existing provenance, entity/link dedup and profile fusion | Stub original_path mismatch; literal backslash-n in URL guard comments accidentally changes control flow | Missing URL links / inconsistent semantics | Restore guard, test metadata-only and lead findings |
| Resolution | PARTIAL | Existing entity services and extraction integration | Registry not connected; cross-source identity quality needs verification | False identity assertions | Preserve identifier-based evidence |
| Recursion | PARTIAL | Depth, visited, entity and pivot budgets exist | Golden baseline fails at source stub contract | Regression hidden by fixture failures | Repair contract before changing traversal |
| UI | PARTIAL | Overview/entities/sources and open_web_discovery goal exist | Missing IP; runtime desktop unverified | Misleading readiness | Offline worker/view smoke then desktop |
| Regression | BROKEN | 336 existing tests pass | 38 pre-existing failures | No stable release claim possible | Retain baseline, classify/fix failures |

## Order

1. Minimal detection/registration routing corrections with targeted tests.
2. Restore persistence URL admission guard without promoting leads.
3. Bound WARC streaming and update HTTP fixtures to real partial-response contracts.
4. Resolve remaining baseline contract failures; continue phone context, registry persistence and golden coverage.
5. Full regression and runtime validation. No production readiness claim until remaining criteria are verified.

## Completed stabilization blocks

Final current-suite result: **415 passed**, Python **3.13.14**, pytest **9.1.1**, project venv. Command: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --tb=short --junitxml=docs/osint_stabilization/final_tests.xml`.

### WHAT CHANGED / WHY

- UI detection now recognizes IPv4/IPv6 through ipaddress and parenthesized national phones. Existing IP enrichment routing is reused.
- EMAIL_REGISTRATION and HISTORICAL_WEB admit safe SUPPORT providers; passive-mode filtering applies to these routes. This restores Holehe/SocialScan/User Scanner registration and Archive.today history routing without credentials or active scanners.
- Capability manager-registration flags for Gravatar/User Scanner now describe reality: these are registered by ServiceContainer, not the manager's default list.
- Persistence search_query admission returns no entities. Restored URL guard that a literal backslash-n comment had accidentally swallowed. A provenance URL with lead_only is not independently promoted; identifiers extracted from document text retain existing lead semantics.
- PhoneIntelligence keeps national input without country ambiguous, exposes a possible international candidate without asserting it as canonical, and supplies local_only metadata. LocalPhone returns PARTIAL for ambiguity and accepts explicit default_region. Six Ukrainian forms with UA and a UK example with GB are tested; no global Ukraine assumption.
- WARC streaming requires HTTP 206, exact valid Content-Range, matching declared/actual lengths, identity transfer encoding, and a hard cap before appending. Ignored Range is rejected before reading body. Redirects are rejected. Existing decompression/text bounds remain.
- DOCX extraction bounds selected XML members and their aggregate uncompressed bytes, rejects encryption and DTD/entity declarations (including UTF-16/32 representations). Public document byte accumulation checks the bound before appending.

### FILES CHANGED

Production (8 files):

- `app/interface/desktop/workers/investigation_search_worker.py`
- `app/osint/pivot_router.py`
- `app/osint/capabilities.py`
- `app/osint/finding_persistence.py`
- `app/osint/phone_intelligence.py`
- `app/osint/connectors/local_phone_connector.py`
- `app/infrastructure/open_web/common_crawl_warc_client.py`
- `app/osint/open_web/public_document_fetcher.py`

New tests: `test_osint_stabilization_routing.py`, `test_common_crawl_stream_bounds.py`, `test_phone_normalization_context.py`, `test_public_document_zip_bounds.py`, `test_osint_desktop_runtime_smoke.py`. Existing regression fixtures/contracts were updated in place; evidence-only search-query tests gained additional cases. Per-production-file diffs are in `diffs/` because these source files were initially untracked and ordinary git diff does not capture them.

### TESTS RUN / TEST RESULTS

- Baseline twice: 336 passed / 38 failed, before production edits.
- Routing / lead / username quality block: 41 passed.
- WARC bounds / hydration block: 18 passed.
- PHONE context / provider regression block: 27 passed.
- DOCX bounds / document verification block: 14 passed.
- Qt runtime and changed-source compile checks: 7 passed.
- Final complete collected suite: 415 passed, zero failures or skips.

Root causes of baseline failures: email SUPPORT routing exclusion; historical SUPPORT routing exclusion; source stubs using path instead of actual original_path; Common Crawl stubs lacking recent_indexes; test-only WARC length 999; old UserScanner email argument; removed worker variable/comment assertions; stale two-provider username and one-provider phone expectations; extracting provenance URL as page content; stale ACCOUNT creation golden expectation; incorrect manager-registration catalog flags. Golden expected counts changed from 4 entities / 6 links to 3 entities / 5 links because the existing username quality layer suppresses unsupported ACCOUNT identity. No random snapshot regeneration, test deletion, skip or xfail was used.

### RUNTIME PROBE

Real QApplication, InvestigationSearchView controls/signals and InvestigationSearchWorker executed offscreen for all six target types. Application-service boundaries were stubbed, so this proves UI dispatch, not external provider availability or production DB startup. Real phonenumbers normalization executed. MockTransport streams prove rejection before body reads and response closure. Compile checks cover the eight changed production files and assert project sys.executable.

### KNOWN LIMITATIONS / NEXT BLOCK

The first stable release is **not yet established**. The initial component matrix describes initial observations, not a completed exhaustive security/runtime audit.

1. Registry Persistence + identifier-aware Entity Fusion still missing. Avoid merging distinct same-name companies; inspect existing resolver metadata before implementation. No registry UI entry added.
2. Caller-ID/community tag contract and official court/business source catalog remain unimplemented. No private API or paid access introduced.
3. UI still has no explicit country-context input; unknown national numbers remain ambiguous. Open-Web ambiguity presentation needs consistent provider-level status handling.
4. Full desktop bootstrap with production ServiceContainer, database/search/graph/case integration, CLI availability and live source probes not run. No external target scanning performed.
5. PDF page/content decompression can still consume resources before final text truncation. HTTP content-decoding resource bounds and DNS-rebinding protection need further audit; DOCX/WARC fixes do not establish a blanket SSRF/memory guarantee.
6. Existing recursive golden passes, but no new complete eight-category golden dataset was added for all requested capabilities. Registry/name/LEI UI detection and unified quality labels remain open.
7. Full suite means the 415 currently collected tests; legacy tests already deleted in the initial working tree were not restored or silently counted as passing.

Next implementation block: Registry Persistence + identifier-aware fusion after reviewing Source/Evidence/Entity repositories and transaction semantics, then caller-ID/catalog and full desktop runtime. No DB model changes or migrations were made in this pass.
