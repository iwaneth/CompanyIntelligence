import os
import sqlite3
from pathlib import Path
import httpx
import asyncio
from dotenv import load_dotenv

load_dotenv()

NOCODB_BASE = os.getenv("NOCODB_BASE_URL", "http://localhost:8080")
NOCODB_API_KEY = os.getenv("NOCODB_API_KEY")
NOCODB_SQLITE_PATH = os.getenv("NOCODB_SQLITE_PATH", "nocodb_data/noco.db")


def _build_headers() -> dict[str, str]:
    headers = {}
    if NOCODB_API_KEY:
        headers["xc-token"] = NOCODB_API_KEY
    return headers


async def fetch_table(project: str, table: str, limit: int = 100):
    url = f"{NOCODB_BASE}/api/v1/db/data/{project}/{table}?limit={limit}"
    headers = _build_headers()

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, timeout=20.0)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        # If the NocoDB REST data endpoint is not available for this install,
        # fall back to reading directly from the local NocoDB sqlite file.
        if exc.response.status_code == 404:
            return await asyncio.to_thread(_fetch_table_from_sqlite, project, table, limit)
        raise
    except httpx.RequestError:
        # Network / connection issues: try local sqlite fallback
        return await asyncio.to_thread(_fetch_table_from_sqlite, project, table, limit)


def _fetch_table_from_sqlite(project: str, table: str, limit: int = 100):
    db_file = Path(NOCODB_SQLITE_PATH)
    if not db_file.exists():
        raise FileNotFoundError(f"NocoDB sqlite file not found: {db_file}")

    conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        # If `table` looks like a model id, resolve to the internal table_name
        cur = conn.execute("SELECT table_name FROM nc_models_v2 WHERE id = ?", (table,))
        row = cur.fetchone()
        if row and row[0]:
            internal_table = row[0]
        else:
            # assume `table` is already the internal table name
            internal_table = table

        # Ensure the internal table exists
        check = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (internal_table,)).fetchone()
        if not check:
            raise FileNotFoundError(f"Table not found in sqlite: {internal_table}")

        cursor = conn.execute(f"SELECT * FROM \"{internal_table}\" LIMIT ?", (limit,))
        rows = cursor.fetchall()
    finally:
        conn.close()

    # convert rows to list[dict]
    out = []
    for r in rows:
        out.append({k: r[k] for k in r.keys()})
    return {"list": out, "pageInfo": {"totalRows": len(out), "pageSize": limit, "page": 1}}


async def list_projects():
    url = f"{NOCODB_BASE}/api/v1/db/meta/projects"
    headers = _build_headers()

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, timeout=20.0)
        resp.raise_for_status()
        return resp.json()


def list_project_tables(project: str) -> list[dict[str, str]]:
    db_file = Path(NOCODB_SQLITE_PATH)
    if not db_file.exists():
        raise FileNotFoundError(f"NocoDB sqlite file not found: {db_file}")

    conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            "SELECT id, table_name, title FROM nc_models_v2 "
            "WHERE base_id = ? AND type = 'table' "
            "AND (deleted = 0 OR deleted IS NULL) "
            "ORDER BY \"order\"",
            (project,),
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    return [
        {
            "id": row["id"],
            "table_name": row["table_name"],
            "title": row["title"] or row["table_name"],
        }
        for row in rows
    ]
