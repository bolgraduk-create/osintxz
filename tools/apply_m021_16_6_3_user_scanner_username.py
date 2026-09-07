from __future__ import annotations

from pathlib import Path

CONNECTOR = Path("app/osint/connectors/user_scanner_connector.py")
CAPABILITIES = Path("app/osint/capabilities.py")


def patch_connector(text: str) -> str:
    marker = "M021.16.6.3 USERNAME mode"
    if marker in text:
        return text

    old_supported = '    supported_targets = {OsintTargetType.EMAIL}\n'
    new_supported = (
        '    # M021.16.6.3 USERNAME mode\n'
        '    supported_targets = {\n'
        '        OsintTargetType.EMAIL,\n'
        '        OsintTargetType.USERNAME,\n'
        '    }\n'
    )

    if old_supported not in text:
        raise RuntimeError("supported_targets anchor not found.")
    text = text.replace(old_supported, new_supported, 1)

    old_sig = (
        '    def _build_command(\n'
        '        cls,\n'
        '        *,\n'
        '        executable: str,\n'
        '        email: str,\n'
        '        output: Path,\n'
        '        timeout: int,\n'
        '    ) -> list[str]:\n'
        '        # M021.16.5.2C1.1 force child UTF-8\n'
        '        return [\n'
        '            sys.executable,\n'
        '            "-X",\n'
        '            "utf8",\n'
        '            "-m",\n'
        '            "user_scanner",\n'
        '            "-e",\n'
        '            email,\n'
        '            "--no-nsfw",\n'
        '            "-f",\n'
        '            "json",\n'
        '            "-o",\n'
        '            str(output),\n'
        '            "-t",\n'
        '            str(max(3, min(int(timeout), 60))),\n'
        '        ]\n'
    )

    new_sig = (
        '    def _build_command(\n'
        '        cls,\n'
        '        *,\n'
        '        executable: str,\n'
        '        target_type: OsintTargetType,\n'
        '        value: str,\n'
        '        output: Path,\n'
        '        timeout: int,\n'
        '    ) -> list[str]:\n'
        '        # M021.16.5.2C1.1 force child UTF-8\n'
        '        mode_flag = (\n'
        '            "-e"\n'
        '            if target_type is OsintTargetType.EMAIL\n'
        '            else "-u"\n'
        '        )\n'
        '\n'
        '        return [\n'
        '            sys.executable,\n'
        '            "-X",\n'
        '            "utf8",\n'
        '            "-m",\n'
        '            "user_scanner",\n'
        '            mode_flag,\n'
        '            value,\n'
        '            "--no-nsfw",\n'
        '            "-f",\n'
        '            "json",\n'
        '            "-o",\n'
        '            str(output),\n'
        '            "-t",\n'
        '            str(max(3, min(int(timeout), 60))),\n'
        '        ]\n'
    )

    if old_sig not in text:
        raise RuntimeError("_build_command anchor not found.")
    text = text.replace(old_sig, new_sig, 1)

    old_target = (
        '        email = request.target.value.strip()\n'
        '\n'
        '        with tempfile.TemporaryDirectory() as tmp:\n'
        '            output = Path(tmp) / "user_scanner_email.json"\n'
        '            command = self._build_command(\n'
        '                executable=executable,\n'
        '                email=email,\n'
        '                output=output,\n'
        '                timeout=request.timeout,\n'
        '            )\n'
    )

    new_target = (
        '        value = request.target.value.strip()\n'
        '        target_type = request.target.target_type\n'
        '\n'
        '        with tempfile.TemporaryDirectory() as tmp:\n'
        '            suffix = (\n'
        '                "email"\n'
        '                if target_type is OsintTargetType.EMAIL\n'
        '                else "username"\n'
        '            )\n'
        '            output = Path(tmp) / f"user_scanner_{suffix}.json"\n'
        '            command = self._build_command(\n'
        '                executable=executable,\n'
        '                target_type=target_type,\n'
        '                value=value,\n'
        '                output=output,\n'
        '                timeout=request.timeout,\n'
        '            )\n'
    )

    if old_target not in text:
        raise RuntimeError("target execution anchor not found.")
    text = text.replace(old_target, new_target, 1)

    text = text.replace("value=email,", "value=value,", 1)

    old_meta = (
        '        result.metadata = {\n'
        '            "registered_records": registered_records,\n'
        '            "records_found": result.total_findings,\n'
        '            "safe_mode": True,\n'
        '            "loud_modules_allowed": False,\n'
        '            "hudson_enabled": False,\n'
        '            "proxy_mode": False,\n'
        '            "public_data_only": True,\n'
        '        }\n'
    )

    new_meta = (
        '        result.metadata = {\n'
        '            "matched_records": registered_records,\n'
        '            "registered_records": (\n'
        '                registered_records\n'
        '                if target_type is OsintTargetType.EMAIL\n'
        '                else 0\n'
        '            ),\n'
        '            "username_accounts_found": (\n'
        '                registered_records\n'
        '                if target_type is OsintTargetType.USERNAME\n'
        '                else 0\n'
        '            ),\n'
        '            "records_found": result.total_findings,\n'
        '            "target_type": target_type.value,\n'
        '            "safe_mode": True,\n'
        '            "loud_modules_allowed": False,\n'
        '            "hudson_enabled": False,\n'
        '            "proxy_mode": False,\n'
        '            "public_data_only": True,\n'
        '        }\n'
    )

    if old_meta not in text:
        raise RuntimeError("result metadata anchor not found.")
    text = text.replace(old_meta, new_meta, 1)

    return text


def patch_capabilities(text: str) -> str:
    old = (
        '        "user_scanner_connector", "UserScannerConnector", "User Scanner",\n'
        '        (OsintTargetType.EMAIL,),\n'
        '        (DiscoveryGoal.EMAIL_REGISTRATION,),\n'
    )

    new = (
        '        "user_scanner_connector", "UserScannerConnector", "User Scanner",\n'
        '        (OsintTargetType.EMAIL, OsintTargetType.USERNAME),\n'
        '        (\n'
        '            DiscoveryGoal.EMAIL_REGISTRATION,\n'
        '            DiscoveryGoal.ACCOUNT_DISCOVERY,\n'
        '        ),\n'
    )

    if new in text:
        return text

    if old not in text:
        raise RuntimeError("User Scanner capability anchor not found.")

    return text.replace(old, new, 1)


def main() -> int:
    for path in (CONNECTOR, CAPABILITIES):
        if not path.exists():
            print(f"[FAIL] Missing {path}")
            return 1

    originals = {
        CONNECTOR: CONNECTOR.read_text(encoding="utf-8"),
        CAPABILITIES: CAPABILITIES.read_text(encoding="utf-8"),
    }

    try:
        updated = {
            CONNECTOR: patch_connector(originals[CONNECTOR]),
            CAPABILITIES: patch_capabilities(originals[CAPABILITIES]),
        }
        for path, value in updated.items():
            compile(value, str(path), "exec")
    except Exception as exc:
        print(f"[FAIL] {exc}")
        return 1

    for path, value in updated.items():
        backup = path.with_suffix(".py.m021_16_6_3_backup")
        if not backup.exists():
            backup.write_text(originals[path], encoding="utf-8")
        path.write_text(value, encoding="utf-8")

    print("[PASS] User Scanner USERNAME mode added.")
    print("[PASS] ACCOUNT_DISCOVERY capability added.")
    print("[PASS] Existing UTF-8 runtime fix preserved.")
    print("[PASS] No loud/Hudson/proxy mode enabled.")
    print("[PASS] No second pipeline.")
    print("[PASS] No database migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
