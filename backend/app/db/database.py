"""SQLite persistence layer for prediction history and alerts."""
import sqlite3
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.app.core.config import settings


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(settings.DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    with _connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS prediction_history (
            id          TEXT PRIMARY KEY,
            timestamp   TEXT NOT NULL,
            source_type TEXT NOT NULL,
            batch_id    TEXT,
            model_ver   TEXT,
            record_count INTEGER DEFAULT 1,
            attack_count INTEGER DEFAULT 0,
            benign_count INTEGER DEFAULT 0,
            summary     TEXT
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id             TEXT PRIMARY KEY,
            timestamp      TEXT NOT NULL,
            predicted_class TEXT NOT NULL,
            score          REAL,
            model_ver      TEXT,
            source_type    TEXT,
            batch_id       TEXT,
            flow_meta      TEXT,
            severity       TEXT DEFAULT 'HIGH',
            acknowledged   INTEGER DEFAULT 0,
            resolved       INTEGER DEFAULT 0
        );
        """)


def insert_prediction_batch(
    source_type: str,
    batch_id: str,
    model_ver: str,
    record_count: int,
    attack_count: int,
    benign_count: int,
    summary: Optional[dict] = None,
) -> str:
    row_id = str(uuid.uuid4())
    ts = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO prediction_history
               (id, timestamp, source_type, batch_id, model_ver,
                record_count, attack_count, benign_count, summary)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (row_id, ts, source_type, batch_id, model_ver,
             record_count, attack_count, benign_count,
             json.dumps(summary) if summary else None),
        )
    return row_id


def insert_alert(
    predicted_class: str,
    score: Optional[float],
    model_ver: str,
    source_type: str,
    batch_id: str,
    flow_meta: Optional[dict] = None,
    severity: str = "HIGH",
) -> str:
    row_id = str(uuid.uuid4())
    ts = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO alerts
               (id, timestamp, predicted_class, score, model_ver,
                source_type, batch_id, flow_meta, severity)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (row_id, ts, predicted_class, score, model_ver,
             source_type, batch_id,
             json.dumps(flow_meta) if flow_meta else None,
             severity),
        )
    return row_id


def get_history(limit: int = 100, offset: int = 0) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM prediction_history ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [dict(r) for r in rows]


def get_alerts(
    limit: int = 100,
    offset: int = 0,
    unack_only: bool = False,
    batch_id: Optional[str] = None,
) -> list[dict]:
    with _connect() as conn:
        query = "SELECT * FROM alerts"
        conditions = []
        params: list = []
        if unack_only:
            conditions.append("acknowledged=0")
        if batch_id:
            conditions.append("batch_id=?")
            params.append(batch_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params += [limit, offset]
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def insert_alerts_batch(alerts: list[dict]) -> int:
    """Insert multiple alerts in a single SQLite transaction."""
    if not alerts:
        return 0
    rows = []
    ts = datetime.now(timezone.utc).isoformat()
    for a in alerts:
        row_id = str(uuid.uuid4())
        flow_meta = a.get("flow_meta")
        rows.append((
            row_id,
            a.get("timestamp", ts),
            a["predicted_class"],
            a.get("score"),
            a.get("model_ver", ""),
            a.get("source_type", "csv_upload"),
            a.get("batch_id", ""),
            json.dumps(flow_meta) if flow_meta else None,
            a.get("severity", "HIGH"),
        ))
    with _connect() as conn:
        conn.executemany(
            """INSERT INTO alerts
               (id, timestamp, predicted_class, score, model_ver,
                source_type, batch_id, flow_meta, severity)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            rows,
        )
    return len(rows)


def get_alerts_count(unack_only: bool = False, batch_id: Optional[str] = None) -> int:
    with _connect() as conn:
        query = "SELECT COUNT(*) FROM alerts"
        conditions = []
        params: list = []
        if unack_only:
            conditions.append("acknowledged=0")
        if batch_id:
            conditions.append("batch_id=?")
            params.append(batch_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        return conn.execute(query, params).fetchone()[0]


def get_alerts_summary() -> dict:
    with _connect() as conn:
        row = conn.execute(
            """SELECT
                COUNT(*) AS total_alerts,
                COALESCE(SUM(CASE WHEN acknowledged = 0 THEN 1 ELSE 0 END), 0) AS unack_alerts,
                COALESCE(SUM(CASE WHEN resolved = 1 THEN 1 ELSE 0 END), 0) AS resolved_alerts,
                COALESCE(SUM(CASE WHEN UPPER(predicted_class) LIKE '%ATTACK%' OR predicted_class = '1' THEN 1 ELSE 0 END), 0) AS attack_alerts
               FROM alerts"""
        ).fetchone()
    return {
        "total_alerts": int(row[0] or 0),
        "unack_alerts": int(row[1] or 0),
        "resolved_alerts": int(row[2] or 0),
        "attack_alerts": int(row[3] or 0),
    }


def clear_alerts_and_history() -> dict:
    with _connect() as conn:
        conn.execute("DELETE FROM alerts")
        conn.execute("DELETE FROM prediction_history")
    return {"status": "ok", "message": "All alerts and ingestion history cleared successfully."}


def get_overview_stats() -> dict:
    """Return aggregated live telemetry from prediction history and alerts."""
    with _connect() as conn:
        hist_stats = conn.execute(
            """SELECT
                COALESCE(SUM(record_count), 0) AS total_flows,
                COALESCE(SUM(attack_count), 0) AS total_attacks,
                COALESCE(SUM(benign_count), 0) AS total_benign,
                COUNT(*) AS total_batches
               FROM prediction_history"""
        ).fetchone()

        alerts_stats = conn.execute(
            """SELECT
                COUNT(*) AS total_alerts,
                SUM(CASE WHEN acknowledged = 0 THEN 1 ELSE 0 END) AS unack_alerts,
                SUM(CASE WHEN resolved = 1 THEN 1 ELSE 0 END) AS resolved_alerts
               FROM alerts"""
        ).fetchone()

        latest_batch = conn.execute(
            "SELECT * FROM prediction_history ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()

    total_flows = hist_stats[0]
    total_attacks = hist_stats[1]
    attack_rate = round(total_attacks / total_flows, 4) if total_flows > 0 else 0.0

    latest_dict = None
    if latest_batch:
        d = dict(latest_batch)
        try:
            if d.get("summary"):
                d["summary"] = json.loads(d["summary"])
        except Exception:
            pass
        latest_dict = d

    return {
        "total_flows_analyzed": int(total_flows),
        "total_attacks_detected": int(total_attacks),
        "total_benign_flows": int(hist_stats[2]),
        "total_batches": int(hist_stats[3]),
        "overall_attack_rate": attack_rate,
        "total_alerts": int(alerts_stats[0] or 0),
        "unack_alerts": int(alerts_stats[1] or 0),
        "resolved_alerts": int(alerts_stats[2] or 0),
        "latest_batch": latest_dict,
    }


def acknowledge_alert(alert_id: str) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alerts SET acknowledged=1 WHERE id=?", (alert_id,)
        )
    return cur.rowcount > 0


def resolve_alert(alert_id: str) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alerts SET resolved=1, acknowledged=1 WHERE id=?", (alert_id,)
        )
    return cur.rowcount > 0

