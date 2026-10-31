import sqlite3, json
from pathlib import Path
from datetime import datetime

DB_PATH = Path(".datasentinel/incidents.sqlite3")

def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with _connect() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, dataset_name TEXT NOT NULL,
            summary TEXT, finding_count INTEGER NOT NULL, verified INTEGER NOT NULL, report_json TEXT NOT NULL)""")

def save_incident(dataset_name, result):
    with _connect() as con:
        con.execute("INSERT INTO incidents(created_at,dataset_name,summary,finding_count,verified,report_json) VALUES(?,?,?,?,?,?)",
                    (datetime.now().isoformat(timespec="seconds"), dataset_name, result.get("summary",""),
                     len(result.get("findings", [])), int(bool(result.get("verification", {}).get("passed"))),
                     json.dumps(result, default=str)))

def list_incidents():
    with _connect() as con:
        rows = con.execute("SELECT id, created_at, dataset_name, summary, finding_count, verified FROM incidents ORDER BY id DESC LIMIT 100").fetchall()
    return [dict(row) for row in rows]
