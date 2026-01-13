import argparse
import os
import sys
import ssl
import subprocess
from glob import glob
from urllib.parse import urlparse, unquote
from urllib.request import urlopen, Request


def _read_dotenv(path: str) -> dict:
    env: dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    except FileNotFoundError:
        return {}
    return env


def get_setting(key: str) -> str | None:
    if os.environ.get(key):
        return os.environ.get(key)
    dotenv = _read_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    return dotenv.get(key)


def check_db(database_url: str) -> tuple[bool, str]:
    parsed = urlparse(database_url)
    if parsed.scheme not in {"postgresql", "postgres"}:
        return False, f"Unsupported DB scheme: {parsed.scheme}"

    host = parsed.hostname or "127.0.0.1"
    port = str(parsed.port or 5432)
    user = unquote(parsed.username or "postgres")
    password = unquote(parsed.password or "")
    dbname = (parsed.path or "").lstrip("/")
    if not dbname:
        return False, "DATABASE_URL missing database name"

    # 1) Preferred: psycopg2 (installed via psycopg2-binary)
    try:
        import psycopg2  # type: ignore

        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        conn.close()
        return True, "OK"
    except ModuleNotFoundError:
        pass
    except Exception as e:
        return False, str(e)

    # 2) Fallback: use psql.exe if available (common on Windows)
    def find_psql() -> str | None:
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        candidates = []
        for root in (program_files, program_files_x86):
            candidates.extend(glob(os.path.join(root, "PostgreSQL", "*", "bin", "psql.exe")))

        def version_key(path: str) -> tuple:
            # ...\PostgreSQL\18\bin\psql.exe -> (18,)
            parts = path.split(os.sep)
            try:
                idx = parts.index("PostgreSQL")
                ver = parts[idx + 1]
                return tuple(int(x) for x in ver.split("."))
            except Exception:
                return (0,)

        if not candidates:
            return None
        candidates.sort(key=version_key, reverse=True)
        return candidates[0]

    psql = find_psql()
    if not psql:
        return False, "psycopg2 not available and psql.exe not found"

    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password

    try:
        proc = subprocess.run(
            [
                psql,
                "-h",
                host,
                "-p",
                port,
                "-U",
                user,
                "-d",
                dbname,
                "-c",
                "SELECT 1;",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as e:
        return False, f"psql invocation failed: {e}"

    if proc.returncode == 0:
        return True, "OK"

    err = (proc.stderr or proc.stdout or "").strip()
    return False, err or f"psql failed with code {proc.returncode}"


def check_api(api_base: str) -> tuple[bool, str]:
    base = api_base.rstrip("/")

    def _add(candidates: list[str], url: str) -> None:
        if url and url not in candidates:
            candidates.append(url)

    candidates: list[str] = []

    # 1) Preferred: lightweight readiness endpoint (no DB)
    # Caller may pass:
    # - http://127.0.0.1:8001
    # - http://127.0.0.1:8001/api
    # - http://127.0.0.1:8001/api/public
    _add(candidates, base + "/health")

    # 2) Public API health (router-prefixed)
    _add(candidates, base + "/api/public/health")
    _add(candidates, base + "/public/health")
    _add(candidates, base + "/health")

    # 3) Legacy: election list endpoint (DB-backed)
    _add(candidates, base + "/api/elections")
    _add(candidates, base + "/elections")

    # If user passed .../api, also try stripping it for root health.
    if base.endswith("/api"):
        root = base[: -len("/api")]
        _add(candidates, root + "/health")
        _add(candidates, root + "/api/public/health")
        _add(candidates, root + "/api/elections")

    last_error = "Unknown error"
    for url in candidates:
        try:
            # avoid SSL issues if user ever points to https with a local proxy
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = Request(url, headers={"Accept": "application/json"})
            with urlopen(req, timeout=5, context=ctx) as resp:
                if 200 <= resp.status < 300:
                    return True, f"OK ({url}) HTTP {resp.status}"
                last_error = f"{url}: HTTP {resp.status}"
        except Exception as e:
            last_error = f"{url}: {e}"

    return False, last_error


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db", action="store_true", help="Check DATABASE_URL connectivity")
    p.add_argument("--api", metavar="API_BASE", help="Check API is reachable (expects /elections)")
    args = p.parse_args()

    if not args.db and not args.api:
        print("Nothing to check. Use --db and/or --api")
        return 2

    failed = False

    if args.db:
        database_url = get_setting("DATABASE_URL")
        if not database_url:
            print("[DB] FAIL: DATABASE_URL is not set (env or .env)")
            failed = True
        else:
            ok, msg = check_db(database_url)
            if ok:
                print("[DB] OK")
            else:
                print("[DB] FAIL:")
                print(msg)
                failed = True

    if args.api:
        ok, msg = check_api(args.api)
        if ok:
            print(f"[API] OK ({msg})")
        else:
            print("[API] FAIL:")
            print(msg)
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
