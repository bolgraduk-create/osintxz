# OSINTXZ — R13.11 Remote Adapter Pack 3

Five remote sources become real adapters:

- France Recherche d’entreprises (open DINUM API using SIRENE/RNE and other public sources)
- Australia ABN Lookup (free registration GUID)
- Corporations Canada Federal Corporation API (Public Plan `user-key`)
- Charity Commission for England and Wales (subscription key)
- Poland REGON BIR1.1 (production user key)

The pack does not download national datasets. Every adapter performs bounded remote lookups.

## Access

France is keyless. The others stay installed but return `NOT_CONFIGURED` until their keys are set in `.env`:

```text
ABN_LOOKUP_GUID=
CANADA_CORPORATIONS_API_KEY=
UK_CHARITY_COMMISSION_API_KEY=
POLAND_REGON_API_KEY=
```

No database migration and no new Python dependency.
