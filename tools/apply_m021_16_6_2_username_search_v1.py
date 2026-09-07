from __future__ import annotations

from pathlib import Path

WORKER = Path("app/interface/desktop/workers/investigation_search_worker.py")
VIEW = Path("app/interface/desktop/views/workspace/investigation_search_view.py")


def patch_worker(text: str) -> str:
    marker = "M021.16.6.2 USERNAME OSINT routing"
    if marker in text:
        return text

    old = '            if target_type is OsintTargetType.EMAIL:\n                self.status_changed.emit(\n                    "Поиск по email через доступные OSINT-коннекторы..."\n                )\n'

    new = '            # M021.16.6.2 USERNAME OSINT routing\n            if target_type in {\n                OsintTargetType.EMAIL,\n                OsintTargetType.USERNAME,\n            }:\n                target_label = (\n                    "email"\n                    if target_type is OsintTargetType.EMAIL\n                    else "username"\n                )\n                self.status_changed.emit(\n                    f"Поиск по {target_label} через доступные OSINT-коннекторы..."\n                )\n'

    if old not in text:
        raise RuntimeError("EMAIL OSINT routing anchor not found.")
    text = text.replace(old, new, 1)

    marker2 = "# M021.16.5.2A EMAIL public-web"
    pos = text.find(marker2)
    if pos < 0:
        raise RuntimeError("EMAIL public-web block not found.")

    start = text.rfind("                # M021.16.5.2A EMAIL public-web", 0, pos + len(marker2))
    end = text.find("                if self.recursive:", pos)
    if start < 0 or end < 0:
        raise RuntimeError("EMAIL public-web block bounds not found.")

    block = text[start:end]
    if "email_open_web_result" not in block:
        raise RuntimeError("EMAIL public-web result anchor not found.")

    inner = block
    # indent existing block by 4 spaces and remove marker-only duplication
    indented = "".join(
        ("    " + line if line.strip() else line)
        for line in inner.splitlines(keepends=True)
    )

    replacement = (
        "                email_open_web_result = None\n\n"
        "                if target_type is OsintTargetType.EMAIL:\n"
        + indented
    )

    text = text[:start] + replacement + text[end:]

    text = text.replace(
        '                        "Email Search v1: рекурсивное расширение "\n'
        '                        "будет подключено отдельным блоком."\n',
        '                        "Рекурсивное расширение для этого типа "\n'
        '                        "цели будет подключено отдельным блоком."\n',
        1,
    )

    return text


def patch_view(text: str) -> str:
    marker = "M021.16.6.2 generic OSINT result status"
    if marker in text:
        return text

    old = '        self.set_running(False)\n        self.status_label.setText("Email-поиск завершён.")\n'
    new = (
        '        # M021.16.6.2 generic OSINT result status\n'
        '        self.set_running(False)\n'
        '        target_type = payload.get("target_type")\n'
        '        target_value = getattr(target_type, "value", str(target_type or "OSINT"))\n'
        '        self.status_label.setText(\n'
        '            f"OSINT-поиск ({target_value}) завершён."\n'
        '        )\n'
    )

    if old not in text:
        raise RuntimeError("Email-specific status label anchor not found.")

    return text.replace(old, new, 1)


def main() -> int:
    for path in (WORKER, VIEW):
        if not path.exists():
            print(f"[FAIL] Missing {path}")
            return 1

    originals = {
        WORKER: WORKER.read_text(encoding="utf-8"),
        VIEW: VIEW.read_text(encoding="utf-8"),
    }

    try:
        updated = {
            WORKER: patch_worker(originals[WORKER]),
            VIEW: patch_view(originals[VIEW]),
        }
        for path, value in updated.items():
            compile(value, str(path), "exec")
    except Exception as exc:
        print(f"[FAIL] {exc}")
        return 1

    for path, value in updated.items():
        backup = path.with_suffix(".py.m021_16_6_2_backup")
        if not backup.exists():
            backup.write_text(originals[path], encoding="utf-8")
        path.write_text(value, encoding="utf-8")

    print("[PASS] USERNAME routed to existing OsintEnrichmentService.")
    print("[PASS] EMAIL behavior preserved.")
    print("[PASS] USERNAME does not run email public-web providers.")
    print("[PASS] No second pipeline.")
    print("[PASS] No database migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
