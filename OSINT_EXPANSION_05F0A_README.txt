OSINT Intelligence Platform
OSINT Expansion 05F0A — Chat Participant Identity Contract Probe

05E status:
- PostgreSQL transactional persistence/pivot gate: PASS
- first persistence:
    sources_created=5
    evidences_created=5
    entities_created=6
    links_created=9
- pivot types:
    domain
    ip
    url
- identical second persistence:
    zero duplicates
- rollback verification:
    zero surviving test rows

New intermediate stage requested by the user:
05F0 — Chat Participant Identity Resolution

Goal:
The application should determine which chat-visible identities belong to the
same real participant.

Examples of evidence that may exist:
- Telegram/user numeric ID
- @username
- first name / last name / display name
- sender/author label in an exported chat
- local nickname/contact label
- message authorship
- previously extracted identifiers

Important:
05F0 must NOT merge people solely because names look similar.

Resolution strength should follow roughly:
1. stable platform/user ID
2. exact or historically linked username
3. strong account/message provenance
4. normalized full name + corroborating context
5. weak nickname similarity only as a hypothesis

Ambiguous matches should remain separate with confidence and provenance.

05F0A changes NO production code.
It inspects the current Telegram importer, Message/Account/Entity models,
entity-resolution infrastructure and relevant tests, then creates a bundle for
the 05F0B implementation.

Run:

    cd C:\osintxz

    & .\.venv\Scripts\python.exe .\tools\chat_identity_contract_probe_05f0a.py

Upload BOTH:
    storage\cache\osint_expansion_05f0a\chat_identity_contract.json
    storage\cache\osint_expansion_05f0a\osint_05f0a_chat_identity_bundle.zip
