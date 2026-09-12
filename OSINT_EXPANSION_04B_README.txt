OSINT Intelligence Platform
OSINT Expansion 04B — Connector Wrapper Execution Gate

04A2 confirmed the raw CLIs can run and all connector modules import.

04B now executes the *actual project wrappers*:
    connector.execute(ConnectorRequest(...))

Target:
    example.com

Each connector is run in a separate child process with a 30-second hard
timeout, so a slow wrapper cannot freeze the whole gate.

The gate records:
- actual connector class and constructor signature
- actual execute() signature
- supports() result when available
- OsintTarget and ConnectorRequest signatures
- returned result type
- returned status
- findings count
- serialized OsintResult/OsintFinding structure
- exact traceback for wrapper failures

No:
- database writes
- persistence
- vulnerability scanners

Run:

    cd C:\osintxz
    $env:Path = "C:\osintxz\tools\osint\bin;$env:Path"
    & .\.venv\Scripts\python.exe .\tools\osint_wrapper_execution_gate_04b.py

Output:
    storage\cache\osint_expansion_04b\wrapper_gate.json

Send the console output and wrapper_gate.json back to ChatGPT.
The next step will patch only wrappers that actually fail or mis-parse.
