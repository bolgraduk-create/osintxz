# OSINTXZ — R13.13 Leak / Paste / Exposure Source Pack

## Что добавляет пакет

R13.13 расширяет `Exposure Federation Core` из R13.12 реальными источниками утечек и защитными источниками экспозиции, не меняя схему БД.

Добавлено:

- **HIBP Paste Metadata** — поиск упоминания email в paste-источниках через официальный `pasteAccount` API. Сохраняется только метаинформация paste (`Source`, `Id`, `Title`, `Date`, `EmailCount`); содержимое paste не скачивается.
- **HIBP Verified Domain Exposure** — поиск скомпрометированных адресов только для доменов, которые HIBP подтверждает как `subscribed/verified` для текущего API key.
- **HIBP Stealer Logs by Email** — для email внутри подтверждённого домена; возвращаются домены сервисов, где HIBP видел stealer-log exposure. Пароли не возвращаются.
- **HIBP Stealer Logs by Email Domain** — агрегированная проверка подтверждённого email-домена.
- **HIBP Stealer Logs by Website Domain** — проверка подтверждённого website-domain; используется только при явном `verified_scope=True`.
- **GitHub Secret Scanning** — чтение alert metadata только из репозитория, к которому токен имеет доступ. Запрос всегда содержит `hide_secret=true`, а поле `secret` дополнительно вообще не переносится в OSINTXZ record.
- `ExposureFederationService.search_email()` теперь включает HIBP paste metadata вместе с R13.12 HIBP breach + Intelligence X metadata.
- Добавлены отдельные методы verified-scope поиска для domain/stealer/GitHub workflows.
- `ExposureSummary` теперь считает `paste_records`, `stealer_log_records`, `secret_alert_records` и `verified_scope_records`.
- В `RemoteSourceQuery` добавлен совместимый флаг `verified_scope=False`.

## Защитные ограничения

- raw passwords / tokens / cookies / private keys не сохраняются;
- HIBP paste body не скачивается;
- HIBP stealer-log API используется только через verified-domain workflow;
- GitHub Secret Scanning требует `verified_scope=True` и авторизованный token;
- generic Remote Federation сам эти источники не запускает (`automatic_enabled=False`);
- R13.13 не создаёт новые таблицы и не требует Alembic migration.

## Какие файлы меняются

Точечно изменяются:

- `app/intelligence_sources/adapters/contracts.py`
- `app/intelligence_sources/builtin_sources.py`
- `app/core/config.py`
- `app/core/service_container.py`
- `app/exposure_intelligence/contracts.py`
- `app/exposure_intelligence/service.py`
- `.env.example`

Новые файлы:

- `app/intelligence_sources/adapters/hibp_extended.py`
- `app/intelligence_sources/adapters/github_secret_scanning.py`
- `tests/test_r13_13_leak_paste_source_pack.py`

Перед изменением существующих файлов установщик создаёт backup в `storage/patch_backups/r13_13_<timestamp>`.

## Настройки

Используется уже существующий:

```env
HAVEIBEENPWNED_API_KEY=
```

Для GitHub Secret Scanning добавляется:

```env
GITHUB_SECRET_SCANNING_TOKEN=
```

Токен GitHub не нужен для установки или тестов. Для реального вызова ему нужен read-доступ к Secret Scanning alerts конкретного репозитория.

## Установка

Из активированного `.venv` в `C:\osintxz`:

```powershell
python .\OSINTXZ_R13_13_LEAK_PASTE_SOURCE_PACK\install_r13_13_leak_paste_source_pack.py C:\osintxz --run-tests
```

Regression gate включает R13.13 + тесты R13.12/R13.6/R13.7/Federation/Adapter Packs 1–3.

На baseline, где R13.12 дал `67 passed`, ожидаемый итог после добавления 12 новых тестов — `79 passed`.
