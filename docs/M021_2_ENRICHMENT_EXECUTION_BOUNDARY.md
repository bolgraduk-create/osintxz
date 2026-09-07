# M021.2 — Enrichment Execution Boundary

Production flow:

`Target -> Pivot Policy -> Capability Router -> OsintPipeline.run_connector()`

The boundary calls only connectors selected by M021.1. It does not call
`OsintPipeline.run()`, because that method executes every connector compatible
with a target type.

Runtime connector resolution is by connector class, avoiding display-name
differences such as `crt.sh` vs `crtsh`.

Aggregate status:
- SUCCESS: every selected connector succeeded.
- PARTIAL: at least one usable SUCCESS/PARTIAL result exists and another
  connector was partial/failed/unavailable.
- FAILED: selected connectors produced no usable result.
- SKIPPED: policy denied the pivot or there is no eligible route.

Missing tools/registrations and connector failures are returned as data; they
do not raise through the Investigation Engine.

An allowed pivot is marked visited before execution to prevent immediate retry
loops if tools are unavailable.

Not included yet:
- persistence
- Source/Evidence/Entity/Relationship creation
- recursive pivots from findings
- open-web phone discovery
- background scheduling / UI
