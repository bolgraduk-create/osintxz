M022 Registry Intelligence foundation + first global provider (GLEIF).

Included:
- registry contracts and safe provider routing
- RegistryIntelligenceService
- httpx isolated in Infrastructure
- GLEIF Global LEI Index provider for BUSINESS name/LEI/registration-id queries
- ServiceContainer wiring script
- unit tests and live probe

No persistence/UI yet. No DB migration. No CAPTCHA/login/paywall bypass.
GLEIF is global and public, but only covers legal entities that have LEIs; it is not a substitute for every country's official company/FOP registry.
