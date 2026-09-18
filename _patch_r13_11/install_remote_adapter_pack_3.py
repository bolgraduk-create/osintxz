from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import shutil, subprocess, sys

FILES=(
"app/intelligence_sources/adapters/france_enterprises.py",
"app/intelligence_sources/adapters/australia_abn.py",
"app/intelligence_sources/adapters/canada_corporations.py",
"app/intelligence_sources/adapters/charity_uk.py",
"app/intelligence_sources/adapters/poland_regon.py",
"tests/test_remote_adapter_pack_3.py",
)

IMPORTS='''from app.intelligence_sources.adapters.australia_abn import AustraliaAbnLookupAdapter
from app.intelligence_sources.adapters.canada_corporations import CanadaFederalCorporationsAdapter
from app.intelligence_sources.adapters.charity_uk import UkCharityCommissionAdapter
from app.intelligence_sources.adapters.france_enterprises import FranceEnterpriseSearchAdapter
from app.intelligence_sources.adapters.poland_regon import PolandRegonAdapter
'''
IMPORT_ANCHORS=(
"from app.intelligence_sources.adapters.ted import TedSearchAdapter\n",
"from app.intelligence_sources.adapters.openalex import OpenAlexAdapter\n",
)
REGISTRATION_ANCHOR='''        self.remote_source_adapter_service = RemoteSourceAdapterService(
            registry=self.remote_source_adapter_registry
        )
'''
REGISTRATION_BLOCK='''        self.remote_source_adapter_registry.register(FranceEnterpriseSearchAdapter())
        self.remote_source_adapter_registry.register(
            AustraliaAbnLookupAdapter(authentication_guid=settings.abn_lookup_guid)
        )
        self.remote_source_adapter_registry.register(
            CanadaFederalCorporationsAdapter(api_key=settings.canada_corporations_api_key)
        )
        self.remote_source_adapter_registry.register(
            UkCharityCommissionAdapter(api_key=settings.uk_charity_commission_api_key)
        )
        self.remote_source_adapter_registry.register(
            PolandRegonAdapter(user_key=settings.poland_regon_api_key)
        )

'''
CONFIG_FIELDS=(
"    abn_lookup_guid: str | None = None\n",
"    canada_corporations_api_key: str | None = None\n",
"    uk_charity_commission_api_key: str | None = None\n",
"    poland_regon_api_key: str | None = None\n",
)
CONFIG_ANCHORS=(
"    sec_edgar_user_agent: str | None = None\n",
"    openalex_api_key: str | None = None\n",
"    intelligencex_api_key: str | None = None\n",
)
ENV_BLOCK='''
# R13.11 Remote Adapter Pack 3
# Australia ABN Lookup authentication GUID (free registration)
ABN_LOOKUP_GUID=
# Corporations Canada ISED API catalogue user-key (Public Plan)
CANADA_CORPORATIONS_API_KEY=
# Charity Commission England & Wales subscription key
UK_CHARITY_COMMISSION_API_KEY=
# Statistics Poland REGON BIR1.1 production user key
POLAND_REGON_API_KEY=
'''
COVERAGE_REPLACEMENTS={
'SourceCoverageEntry("fr_sirene", Status.CATALOGED, stage="europe")':'SourceCoverageEntry("fr_sirene", Status.ACTIVE, "FranceEnterpriseSearchAdapter", "R13.11 open DINUM search / SIRENE+RNE")',
'SourceCoverageEntry("au_abn_lookup", Status.CATALOGED, stage="apac")':'SourceCoverageEntry("au_abn_lookup", Status.ACTIVE, "AustraliaAbnLookupAdapter", "R13.11 credential-gated")',
'SourceCoverageEntry("ca_federal_corporations", Status.CATALOGED, stage="americas")':'SourceCoverageEntry("ca_federal_corporations", Status.ACTIVE, "CanadaFederalCorporationsAdapter", "R13.11 exact identifiers; credential-gated")',
'SourceCoverageEntry("uk_charity_commission", Status.CATALOGED, stage="next-wave")':'SourceCoverageEntry("uk_charity_commission", Status.ACTIVE, "UkCharityCommissionAdapter", "R13.11 credential-gated")',
'SourceCoverageEntry("pl_regon", Status.CATALOGED, stage="europe")':'SourceCoverageEntry("pl_regon", Status.ACTIVE, "PolandRegonAdapter", "R13.11 exact REGON/NIP/KRS; credential-gated")',
}
FRANCE_OLD='_source("fr_sirene", "France SIRENE / API Entreprise", categories={Category.REGISTRY}, capabilities={"siren", "siret", "organization", "establishment"}, access=Access.FREE_ACCOUNT, origin=Origin.OFFICIAL_API, countries={"FR"}, requires_credentials=True, documentation_url="https://entreprise.api.gouv.fr/"),'
FRANCE_NEW='_source("fr_sirene", "France Recherche d’entreprises (SIRENE/RNE)", categories={Category.REGISTRY}, capabilities={"siren", "siret", "company_name", "organization"}, access=Access.NO_AUTH, origin=Origin.OFFICIAL_API, countries={"FR"}, default_enabled=True, documentation_url="https://recherche-entreprises.api.gouv.fr/docs/"),'

def backup(path,label):
    stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
    target=path.with_name(f"{path.name}.before_{label}_{stamp}.bak")
    shutil.copy2(path,target); return target

def copy_payload(patch,project):
    for rel in FILES:
        src=patch/'payload'/rel; dst=project/rel; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst); print(f"[OK] Installed {rel}")

def patch_config(path):
    original=path.read_text(encoding='utf-8'); updated=original
    missing=[f for f in CONFIG_FIELDS if f.strip().split(':',1)[0].strip() not in updated]
    if not missing: print(f"[OK] {path} already contains R13.11 settings"); return
    anchor=next((a for a in CONFIG_ANCHORS if a in updated),None)
    if anchor is None: raise RuntimeError("Safe API settings anchor not found in config.py")
    updated=updated.replace(anchor,anchor+''.join(missing),1)
    b=backup(path,'remote_adapter_pack_3'); path.write_text(updated,encoding='utf-8'); print(f"[OK] Patched {path}\n[OK] Backup: {b}")

def patch_env(path):
    original=path.read_text(encoding='utf-8')
    keys=("ABN_LOOKUP_GUID=","CANADA_CORPORATIONS_API_KEY=","UK_CHARITY_COMMISSION_API_KEY=","POLAND_REGON_API_KEY=")
    if all(k in original for k in keys): print(f"[OK] {path} already contains R13.11 env settings"); return
    b=backup(path,'remote_adapter_pack_3'); path.write_text(original.rstrip()+"\n"+ENV_BLOCK.lstrip(),encoding='utf-8'); print(f"[OK] Patched {path}\n[OK] Backup: {b}")

def patch_service(path):
    original=path.read_text(encoding='utf-8'); updated=original
    if 'FranceEnterpriseSearchAdapter' not in updated:
        anchor=next((a for a in IMPORT_ANCHORS if a in updated),None)
        if anchor is None: raise RuntimeError("R13.9/R13.10 adapter import anchor not found")
        updated=updated.replace(anchor,anchor+IMPORTS,1)
    if 'AustraliaAbnLookupAdapter(authentication_guid=settings.abn_lookup_guid)' not in updated:
        if updated.count(REGISTRATION_ANCHOR)!=1: raise RuntimeError("Remote adapter service anchor not found")
        updated=updated.replace(REGISTRATION_ANCHOR,REGISTRATION_BLOCK+REGISTRATION_ANCHOR,1)
    if updated==original: print(f"[OK] {path} already contains Adapter Pack 3"); return
    b=backup(path,'remote_adapter_pack_3'); path.write_text(updated,encoding='utf-8'); print(f"[OK] Patched {path}\n[OK] Backup: {b}")

def patch_catalog(path):
    original=path.read_text(encoding='utf-8'); updated=original; changed=False
    if FRANCE_NEW not in updated:
        if FRANCE_OLD not in updated: raise RuntimeError("Expected France source descriptor missing")
        updated=updated.replace(FRANCE_OLD,FRANCE_NEW,1); changed=True
    for old,new in COVERAGE_REPLACEMENTS.items():
        if new in updated: continue
        if old not in updated: raise RuntimeError(f"Expected coverage entry missing: {old}")
        updated=updated.replace(old,new,1); changed=True
    if not changed: print(f"[OK] {path} already marks Adapter Pack 3 active"); return
    b=backup(path,'remote_adapter_pack_3'); path.write_text(updated,encoding='utf-8'); print(f"[OK] Patched {path}\n[OK] Backup: {b}")

def main():
    ap=argparse.ArgumentParser(description='Install OSINTXZ R13.11 Remote Adapter Pack 3'); ap.add_argument('project_root',nargs='?',default=r'C:\\osintxz'); ap.add_argument('--run-tests',action='store_true'); args=ap.parse_args()
    patch=Path(__file__).resolve().parent; project=Path(args.project_root).resolve()
    required=[project/'app/intelligence_sources/adapters/service.py',project/'app/intelligence_sources/adapters/sec_edgar.py',project/'app/intelligence_sources/builtin_sources.py',project/'app/core/config.py',project/'app/core/service_container.py',project/'.env.example']
    missing=[str(p) for p in required if not p.exists()]
    if missing: print('[ERROR] R13.10 is required; missing: '+', '.join(missing),file=sys.stderr); return 2
    copy_payload(patch,project); patch_config(project/'app/core/config.py'); patch_env(project/'.env.example'); patch_catalog(project/'app/intelligence_sources/builtin_sources.py'); patch_service(project/'app/core/service_container.py')
    print('[OK] R13.11 Remote Adapter Pack 3 installed.')
    print('[INFO] ACTIVE: France company search, Australia ABN, Corporations Canada, UK Charity Commission, Poland REGON.')
    print('[INFO] France requires no key; AU/CA/UK/PL adapters are credential-gated.')
    print('[INFO] No database migration and no new dependency.')
    if args.run_tests:
        cmd=[sys.executable,'-m','pytest','tests/test_remote_adapter_pack_3.py','-q']; print('[RUN]',' '.join(cmd)); return subprocess.run(cmd,cwd=project,check=False).returncode
    return 0
if __name__=='__main__': raise SystemExit(main())
