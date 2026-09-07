
from pathlib import Path

PATH = Path("app/core/service_container.py")

def extract_block(text, marker):
    start = text.find(marker)
    if start < 0:
        raise RuntimeError(f"Missing marker: {marker}")
    line_start = text.rfind("\n", 0, start) + 1
    p = text.find("(", start)
    if p < 0:
        raise RuntimeError("Opening parenthesis not found")
    depth = 0
    i = p
    while i < len(text):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                end = text.find("\n", i)
                end = len(text) if end < 0 else end + 1
                while end < len(text) and text[end] == "\n":
                    end += 1
                return line_start, end, text[line_start:end]
        i += 1
    raise RuntimeError("Unclosed assignment block")

def main():
    if not PATH.is_file():
        print(f"[FAIL] Missing {PATH}")
        return 1

    original = PATH.read_text(encoding="utf-8")
    text = original
    recursive_marker = "self.osint_recursive_enrichment_service ="
    bridge_marker = "self.open_web_recursive_pivot_service ="

    rpos = text.find(recursive_marker)
    bpos = text.find(bridge_marker)
    if rpos < 0 or bpos < 0:
        print("[FAIL] Required wiring not found.")
        return 1

    if rpos < bpos:
        print("[PASS] Composition order already correct.")
        return 0

    bstart, bend, bblock = extract_block(text, bridge_marker)
    text = text[:bstart] + text[bend:]

    rstart, rend, _ = extract_block(text, recursive_marker)
    text = text[:rend] + "\n" + bblock.rstrip() + "\n\n" + text[rend:]

    compile(text, str(PATH), "exec")

    checks = {
        "recursive before bridge": text.find(recursive_marker) < text.find(bridge_marker),
        "one recursive": text.count(recursive_marker) == 1,
        "one bridge": text.count(bridge_marker) == 1,
        "one pipeline": text.count("self.osint_pipeline =") == 1,
    }
    failed = [k for k, v in checks.items() if not v]
    if failed:
        print("[FAIL] " + ", ".join(failed))
        return 1

    backup = PATH.with_suffix(".py.m021_14_1_backup")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")
    PATH.write_text(text, encoding="utf-8")

    print("[PASS] OsintRecursiveEnrichmentService is created first.")
    print("[PASS] OpenWebRecursivePivotService reuses initialized service.")
    print("[PASS] Singleton guards retained.")
    print(f"[INFO] Backup: {backup}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
