# M021.0.1 — OSINT Capability Catalog

## Goal

Stop treating every connector that accepts the same `OsintTargetType` as
equivalent.

The catalog records what a connector actually contributes to an investigation
before automatic OSINT enrichment is enabled.

## Product dispositions

- **CORE** — primary discovery source that can produce useful new pivots.
- **SUPPORT** — enriches/validates known objects or adds secondary signals.
- **CONDITIONAL** — useful only when the user explicitly configures credentials
  or another non-default prerequisite.
- **SEPARATE** — security/network assessment capability; not part of automatic
  identity/open-web enrichment.
- **REPLACE** — repository implementation is retained temporarily but should be
  replaced by a new adapter before routing.

## Important decisions

- Maigret and Sherlock are CORE username account-discovery sources.
- PhoneInfoga is SUPPORT/phone enrichment, not the primary account finder.
- GHunt is conditional because authenticated setup is required.
- WhatsMyName is marked REPLACE; the legacy CLI assumption should not drive the
  new architecture.
- Nmap/Naabu/Nuclei/Nikto/FFUF/Feroxbuster are explicitly separated from
  automatic Investigation Engine enrichment.
- API-key services remain available as optional connectors but are not default
  dependencies.
- Common Crawl, crt.sh, historical URL sources and keyless domain discovery are
  high-value recursive discovery capabilities.
- theHarvester is retained, but automatic routing must replace `-b all` with an
  explicit keyless/passive provider policy.

## Next block

M021.1 will use this catalog to implement:

`Entity -> Discovery Goal -> Pivot Policy -> Capability Router`

It will not select connectors merely because they share a target type.
