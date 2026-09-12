OSINT Intelligence Platform
OSINT Expansion 04A — Discovery Connector Contract + Safe Live Probe

This is a diagnostic gate before modifying production connector wrappers.

It checks:
- actual local execution of the 6 newly enabled tools
- exact connector class/method signatures by Python introspection
- whether wrappers use ToolRuntime/subprocess
- parser/run method names
- presence of downstream findings/evidence/pivot/provenance components

Safe live target:
    example.com

No:
- database writes
- vulnerability scanning
- destructive actions

Run:

    cd C:\osintxz
    $env:Path = "C:\osintxz\tools\osint\bin;$env:Path"
    & .\.venv\Scripts\python.exe .\tools\osint_discovery_connector_probe.py

Outputs:

    storage\cache\osint_expansion_04a\probe.txt
    storage\cache\osint_expansion_04a\probe.json

Send the full console output plus probe.json back to ChatGPT.
The next patch (04B) will use the exact observed contracts rather than guessing.
