OSINT Intelligence Platform
OSINT Expansion 04A2 — startup/progress fix

04A looked frozen because it collected all six live command results before
printing anything. A slow network-facing tool could therefore leave the
console blank.

04A2:
- prints immediately before every tool
- flushes output immediately
- caps every live tool at 8 seconds
- continues after timeout/error
- fixes dnsx probe input to stdin
- preserves safe target example.com
- performs no DB writes and no vulnerability scanning

Run:

    cd C:\osintxz
    $env:Path = "C:\osintxz\tools\osint\bin;$env:Path"
    & .\.venv\Scripts\python.exe .\tools\osint_discovery_connector_probe_04a2.py

Output:
    storage\cache\osint_expansion_04a2\probe.json
