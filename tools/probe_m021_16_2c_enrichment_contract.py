from pathlib import Path

path=Path("app/application/open_web_enrichment_service.py")

print("="*88)
print("M021.16.2C ENRICHMENT/HYDRATION CONTRACT PROBE")
print("="*88)

for number,line in enumerate(
    path.read_text(encoding="utf-8",errors="replace").splitlines(),
    start=1,
):
    print(f"{number:04d}: {line}")

print()
print("PROBE COMPLETE")
