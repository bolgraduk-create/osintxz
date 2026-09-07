# M021.7 — Open-Web Discovery Core Contracts

Production direction:

`Entity/Pivot -> OpenWebQuery -> Provider Registry -> Provider -> OpenWebDocument -> extraction (M021.8) -> OsintFinding/Entity`

M021.7 introduces no concrete network provider. It establishes a framework-independent provider boundary and safe automatic-provider policy.

Automatic providers must be passive, public-data-only, credential-free, and explicitly default-enabled. A provider result is a public-web lead/document, not proof that an account, page, phone, email, or other identifier belongs to a person.

No CAPTCHA/login/paywall/protection bypass belongs in this layer. Provider exceptions are isolated so one failed source does not abort other sources.

No database migration is required.
