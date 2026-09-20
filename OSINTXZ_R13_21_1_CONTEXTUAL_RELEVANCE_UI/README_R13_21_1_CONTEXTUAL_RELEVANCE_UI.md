# OSINTXZ R13.21.1 — Contextual Relevance + UI Layout Fix

Hotfix for the unified Investigation Search introduced in R13.20/R13.21.

## What changes

- adds a centralized contextual relevance layer before Clean-view display and remote pivot extraction;
- organization searches require meaningful organization-name agreement instead of a shared generic word such as `Foundation`;
- upstream `Match: False`/non-matching reconciliation candidates remain in Raw but are excluded from Clean and automatic pivots;
- exact identifier routes (username/email/domain/etc.) are checked against returned structured values before remote records can become pivots;
- `Keywords` become context/ranking signals by default instead of broad automatic Federation roots;
- organization Federation routing no longer automatically uses generic `name`, `archive_search`, or `keyword` capabilities;
- repeated identical provider errors are grouped into one Error row with an attempt count;
- Clean result limit is reduced from 300 to 220 after relevance filtering;
- restores/guarantees the R13.21 `Identity` tab and `Identity Leads` card;
- result/provider/pivot/error/identity rows now use adaptive height, two-line wrapping, reserved badge space, and bounded elision so text cannot overlap.

## Safety / architecture

- no database migration;
- no new source or API key;
- no bulk download;
- Raw results are preserved for analyst inspection;
- weak candidates are not silently converted into identity assertions;
- raw secret values remain forbidden;
- existing Classic OSINT, Open-Web, Federation and Registry services remain the execution boundaries.

## Install

```powershell
python .\OSINTXZ_R13_21_1_CONTEXTUAL_RELEVANCE_UI\install_r13_21_1_contextual_relevance_ui.py C:\osintxz --run-tests
```

A backup is created under `storage/patch_backups/r13_21_1_YYYYMMDD_HHMMSS`.
