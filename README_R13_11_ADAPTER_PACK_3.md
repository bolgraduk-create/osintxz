# OSINTXZ — R13.11 Remote Adapter Pack 3

Five more remote sources become real adapters:

- France Recherche d'entreprises (open DINUM API; SIRENE/RNE-backed)
- Australia ABN Lookup (free GUID required)
- Corporations Canada (subscription key required)
- UK Charity Commission Register (subscription key required)
- Poland REGON BIR (production user key required)

## Safety / identity rules

Name searches in France, Australia and UK Charity Commission are candidates only.
Exact identifiers (SIREN/SIRET, ABN/ACN, Canadian corporation ID/BN, charity number,
REGON/NIP/KRS) may be marked identity-confirmed for that registry record only.
They do not infer ownership or person identity.

## Configuration

```env
ABN_LOOKUP_GUID=
CANADA_CORPORATIONS_API_KEY=
CHARITY_COMMISSION_API_KEY=
REGON_BIR_USER_KEY=
```

France requires no key. No database migration and no new Python dependency.
