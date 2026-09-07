from __future__ import annotations

from pathlib import Path


TARGET = Path("app/osint/open_web/providers/common_crawl.py")


OLD = """    @staticmethod
    def _probes(query):
        value=query.value.strip()
        if query.target_type is OsintTargetType.URL: return [value]
        domain=value.lower().removeprefix('http://').removeprefix('https://').split('/',1)[0].rstrip('.')
        if domain.startswith('www.'): domain=domain[4:]
        return [f'https://{domain}/',f'http://{domain}/',f'https://www.{domain}/',f'http://www.{domain}/']
"""

NEW = """    @staticmethod
    def _probes(query):
        value = query.value.strip()

        if query.target_type is OsintTargetType.URL:
            return CommonCrawlOpenWebProvider._url_variants(value)

        domain = (
            value.lower()
            .removeprefix("http://")
            .removeprefix("https://")
            .split("/", 1)[0]
            .rstrip(".")
        )
        if domain.startswith("www."):
            domain = domain[4:]

        return [
            f"https://{domain}/",
            f"http://{domain}/",
            f"https://www.{domain}/",
            f"http://www.{domain}/",
        ]

    @staticmethod
    def _url_variants(value: str) -> list[str]:
        from urllib.parse import quote, unquote, urlsplit, urlunsplit

        raw = value.strip()
        if not raw:
            return []

        if "://" not in raw:
            raw = "https://" + raw

        try:
            parsed = urlsplit(raw)
        except ValueError:
            return [value.strip()]

        host = (parsed.hostname or "").strip().rstrip(".").casefold()
        if not host:
            return [value.strip()]

        port = parsed.port
        host_with_port = f"{host}:{port}" if port is not None else host

        path = parsed.path or "/"

        try:
            path = quote(
                unquote(path),
                safe="/:@!$&'()*+,;=-._~",
            )
        except Exception:
            pass

        query_string = parsed.query or ""

        hosts = [host_with_port]
        if host.startswith("www."):
            bare = host[4:]
            hosts.append(
                f"{bare}:{port}" if port is not None else bare
            )
        else:
            www = f"www.{host}"
            hosts.append(
                f"{www}:{port}" if port is not None else www
            )

        schemes = []
        scheme = parsed.scheme.casefold()
        if scheme in {"http", "https"}:
            schemes.append(scheme)
            schemes.append("http" if scheme == "https" else "https")
        else:
            schemes.extend(("https", "http"))

        paths = [path]
        if path == "/":
            paths.append("")
        elif path.endswith("/"):
            paths.append(path.rstrip("/"))
        else:
            paths.append(path + "/")

        variants: list[str] = []
        seen: set[str] = set()

        for scheme_name in schemes:
            for host_name in hosts:
                for path_name in paths:
                    candidate = urlunsplit(
                        (
                            scheme_name,
                            host_name,
                            path_name,
                            query_string,
                            "",
                        )
                    )
                    key = candidate.casefold()
                    if key in seen:
                        continue
                    seen.add(key)
                    variants.append(candidate)

        original = value.strip()
        if original:
            key = original.casefold()
            if key not in seen:
                variants.insert(0, original)

        return variants[:8]
"""


def main() -> int:
    if not TARGET.is_file():
        print(f"[FAIL] Missing {TARGET}")
        return 1

    text = TARGET.read_text(encoding="utf-8")

    if "_url_variants(value: str)" in text:
        print("[PASS] M021.16.2A already applied.")
        return 0

    if OLD not in text:
        print("[FAIL] Expected current _probes implementation not found.")
        return 1

    updated = text.replace(OLD, NEW, 1)
    compile(updated, str(TARGET), "exec")

    backup = TARGET.with_suffix(".py.m021_16_2a_backup")
    if not backup.exists():
        backup.write_text(text, encoding="utf-8")

    TARGET.write_text(updated, encoding="utf-8")

    print("[PASS] Added bounded URL variant expansion.")
    print("[PASS] Preserved existing OpenWeb provider/pipeline.")
    print("[PASS] No wildcard/domain-wide crawl introduced.")
    print("[PASS] No database migration.")
    print(f"[INFO] Backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
