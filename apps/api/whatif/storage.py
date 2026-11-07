from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .beliefs import initial_beliefs
from .config import Business, demo_business


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    """Small transactional persistence adapter. SQLite is the zero-config demo default."""
    def __init__(self, path: str | None = None):
        self.path = Path(path or os.getenv("DATABASE_PATH", "whatif.db"))
        self.lock = threading.RLock()

    def connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, check_same_thread=False, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL;")
        connection.execute("PRAGMA busy_timeout=30000;")
        return connection

    def initialize(self) -> None:
        with self.lock, self.connection() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS decisions (
              id TEXT PRIMARY KEY, title TEXT NOT NULL, payload TEXT NOT NULL, prediction TEXT NOT NULL,
              memory_on INTEGER NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
              review_date TEXT NOT NULL, outcome TEXT, reviewed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS promises (
              id TEXT PRIMARY KEY, partner_key TEXT NOT NULL, item TEXT NOT NULL, quote TEXT NOT NULL,
              promised_days REAL NOT NULL, hedged INTEGER NOT NULL, created_at TEXT NOT NULL,
              delivered_days REAL, delivered_at TEXT
            );
            CREATE TABLE IF NOT EXISTS memory_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, document_id TEXT NOT NULL,
              content TEXT NOT NULL, tags TEXT NOT NULL, created_at TEXT NOT NULL, remote_state TEXT NOT NULL
            );
            """)
            if not db.execute("SELECT 1 FROM settings WHERE key='business'").fetchone():
                business = demo_business(); db.execute("INSERT INTO settings VALUES (?,?)", ("business", json.dumps(business.to_dict())))
                db.execute("INSERT INTO settings VALUES (?,?)", ("beliefs", json.dumps(initial_beliefs(business))))
                db.execute("INSERT INTO settings VALUES (?,?)", ("week", "18"))

    def get_setting(self, key: str, default: Any = None) -> Any:
        with self.connection() as db:
            row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    def put_setting(self, key: str, value: Any) -> None:
        with self.lock, self.connection() as db:
            db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value)))

    def business(self) -> Business:
        return Business.from_dict(self.get_setting("business"))

    def set_business(self, business: Business) -> None:
        self.put_setting("business", business.to_dict())

    def beliefs(self) -> dict[str, dict[str, Any]]:
        return self.get_setting("beliefs")

    def set_beliefs(self, beliefs: dict[str, dict[str, Any]]) -> None:
        self.put_setting("beliefs", beliefs)

    def week(self) -> int:
        return int(self.get_setting("week", 18))

    def set_week(self, week: int) -> None:
        self.put_setting("week", max(0, min(51, week)))

    def add_decision(self, item: dict[str, Any]) -> None:
        with self.lock, self.connection() as db:
            db.execute("INSERT INTO decisions(id,title,payload,prediction,memory_on,status,created_at,review_date) VALUES(?,?,?,?,?,?,?,?)", (
                item["id"], item["title"], json.dumps(item["payload"]), json.dumps(item["prediction"]), int(item["memory_on"]), item["status"], item["created_at"], item["review_date"],
            ))

    def list_decisions(self) -> list[dict[str, Any]]:
        with self.connection() as db:
            rows = db.execute("SELECT * FROM decisions ORDER BY created_at DESC").fetchall()
        return [self._decision(row) for row in rows]

    def get_decision(self, decision_id: str) -> dict[str, Any] | None:
        with self.connection() as db:
            row = db.execute("SELECT * FROM decisions WHERE id=?", (decision_id,)).fetchone()
        return self._decision(row) if row else None

    def _decision(self, row: sqlite3.Row) -> dict[str, Any]:
        return {"id": row["id"], "title": row["title"], "payload": json.loads(row["payload"]), "prediction": json.loads(row["prediction"]), "memory_on": bool(row["memory_on"]), "status": row["status"], "created_at": row["created_at"], "review_date": row["review_date"], "outcome": json.loads(row["outcome"]) if row["outcome"] else None, "reviewed_at": row["reviewed_at"]}

    def review_decision(self, decision_id: str, outcome: dict[str, Any]) -> None:
        with self.lock, self.connection() as db:
            db.execute("UPDATE decisions SET status='reviewed', outcome=?, reviewed_at=? WHERE id=?", (json.dumps(outcome), utcnow(), decision_id))

    def add_promise(self, item: dict[str, Any]) -> None:
        with self.lock, self.connection() as db:
            db.execute("INSERT INTO promises(id,partner_key,item,quote,promised_days,hedged,created_at) VALUES(?,?,?,?,?,?,?)", (item["id"], item["partner_key"], item["item"], item["quote"], item["promised_days"], int(item["hedged"]), item["created_at"]))

    def list_promises(self) -> list[dict[str, Any]]:
        with self.connection() as db:
            rows = db.execute("SELECT * FROM promises ORDER BY created_at DESC").fetchall()
        return [{**dict(row), "hedged": bool(row["hedged"])} for row in rows]

    def get_promise(self, promise_id: str) -> dict[str, Any] | None:
        with self.connection() as db:
            row = db.execute("SELECT * FROM promises WHERE id=?", (promise_id,)).fetchone()
        return ({**dict(row), "hedged": bool(row["hedged"])} if row else None)

    def deliver_promise(self, promise_id: str, days: float) -> None:
        with self.lock, self.connection() as db:
            db.execute("UPDATE promises SET delivered_days=?, delivered_at=? WHERE id=?", (days, utcnow(), promise_id))

    def deliver_promises(self, deliveries: list[tuple[str, float]]) -> None:
        with self.lock, self.connection() as db:
            for promise_id, days in deliveries:
                db.execute("UPDATE promises SET delivered_days=?, delivered_at=? WHERE id=?", (days, utcnow(), promise_id))

    def add_memory_event(self, kind: str, document_id: str, content: str, tags: list[str], remote_state: str) -> None:
        with self.lock, self.connection() as db:
            db.execute("INSERT INTO memory_events(kind,document_id,content,tags,created_at,remote_state) VALUES(?,?,?,?,?,?)", (kind, document_id, content, json.dumps(tags), utcnow(), remote_state))

    def local_recall(self, query: str, limit: int = 4) -> list[dict[str, Any]]:
        tokens = {x.lower() for x in query.split() if len(x) > 3}
        with self.connection() as db:
            rows = db.execute("SELECT * FROM memory_events ORDER BY id DESC LIMIT 80").fetchall()
        ranked = []
        for row in rows:
            content = row["content"]; score = sum(token in content.lower() for token in tokens)
            if score: ranked.append((score, row))
        ranked.sort(key=lambda item: (item[0], item[1]["id"]), reverse=True)
        return [{"id": str(row["id"]), "text": row["content"], "tags": json.loads(row["tags"]), "source": "local"} for _, row in ranked[:limit]]

    def scorecard(self) -> dict[str, Any]:
        decisions = [item for item in self.list_decisions() if item["outcome"]]
        records = []
        for item in decisions:
            prediction = item["prediction"]["plan"]["profit_delta"]; outcome = item["outcome"]
            if outcome.get("gradable") and outcome.get("actual_effect") is not None:
                actual = outcome["actual_effect"]
                records.append({"id": item["id"], "title": item["title"], "actual": actual, "p10": prediction["p10"], "p50": prediction["p50"], "p90": prediction["p90"], "error": abs(actual - prediction["p50"]), "covered": prediction["p10"] <= actual <= prediction["p90"], "pinball": ((.1 if actual >= prediction["p10"] else -.9) * (actual - prediction["p10"]) + (.5 if actual >= prediction["p50"] else -.5) * (actual - prediction["p50"]) + (.9 if actual >= prediction["p90"] else -.1) * (actual - prediction["p90"])) / 3})
        return {"reviews": len(decisions), "gradable_reviews": len(records), "coverage": sum(x["covered"] for x in records) / len(records) if records else None, "median_absolute_error": sorted([x["error"] for x in records])[len(records)//2] if records else None, "records": records}
