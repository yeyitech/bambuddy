"""Private household records. Separate SQLite store, never part of source control."""
from contextlib import contextmanager
import json
import sqlite3
from pathlib import Path

class ConflictError(Exception):
    pass

@contextmanager
def connect(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.execute("CREATE TABLE IF NOT EXISTS ledger (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL, body TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS ledger_audit (revision INTEGER PRIMARY KEY, changed_at TEXT DEFAULT CURRENT_TIMESTAMP, actor TEXT, body TEXT)")
    try:
        with db:
            yield db
    finally:
        db.close()

def read(path: Path, seed: Path):
    with connect(path) as db:
        row = db.execute("SELECT revision, body FROM ledger WHERE id=1").fetchone()
        if row is None:
            body = json.loads(seed.read_text()) if seed.exists() else {"orders": [], "filament_units": [], "history": [], "quality": []}
            ids = [o["id"] for o in body.get("orders", [])]
            if len(ids) != len(set(ids)):
                raise ValueError("Duplicate purchase IDs")
            db.execute("INSERT OR IGNORE INTO ledger VALUES (1,1,?)", (json.dumps(body, ensure_ascii=False),))
            row = db.execute("SELECT revision, body FROM ledger WHERE id=1").fetchone()
        return {"revision": row[0], "data": json.loads(row[1])}

def update_order(path: Path, order_id: str, changes: dict, revision: int, actor: str):
    with connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT revision, body FROM ledger WHERE id=1").fetchone()
        if row is None or row[0] != revision:
            raise ConflictError("记录已更新，请刷新后重试")
        body = json.loads(row[1])
        order = next((o for o in body["orders"] if o["id"] == order_id), None)
        if order is None:
            raise KeyError(order_id)
        db.execute("INSERT INTO ledger_audit(revision,actor,body) VALUES (?,?,?)", (revision, actor, row[1]))
        order.update(changes)
        db.execute("UPDATE ledger SET revision=?,body=? WHERE id=1", (revision+1, json.dumps(body, ensure_ascii=False)))
        return {"revision": revision+1, "data": body}
