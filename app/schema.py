from __future__ import annotations

from sqlalchemy import text


def ensure_sqlite_schema(db) -> None:
    """
    Lightweight SQLite schema upgrades for dev environments.

    `db.create_all()` does not add columns to existing tables, so older
    `taskmanager.db` files can crash after model changes.
    """
    engine = db.engine
    if not str(engine.url).startswith("sqlite:"):
        return

    # ---- Task table: add missing columns ----
    cols = db.session.execute(text("PRAGMA table_info(task)")).fetchall()
    existing = {row[1] for row in cols}  # (cid, name, type, notnull, dflt_value, pk)

    if "percent_complete" not in existing:
        db.session.execute(
            text(
                "ALTER TABLE task "
                "ADD COLUMN percent_complete INTEGER NOT NULL DEFAULT 0"
            )
        )

    if "is_milestone" not in existing:
        # SQLite doesn't have a strict BOOLEAN type; store as 0/1 integer.
        db.session.execute(
            text(
                "ALTER TABLE task "
                "ADD COLUMN is_milestone INTEGER NOT NULL DEFAULT 0"
            )
        )

    # ---- TaskDependency table ----
    dep_table = db.session.execute(
        text(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='task_dependency'"
        )
    ).fetchone()

    if not dep_table:
        db.session.execute(
            text(
                """
                CREATE TABLE task_dependency (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    predecessor_id INTEGER NOT NULL,
                    successor_id INTEGER NOT NULL,
                    dependency_type VARCHAR(2) NOT NULL DEFAULT 'FS',
                    FOREIGN KEY(predecessor_id) REFERENCES task(id),
                    FOREIGN KEY(successor_id) REFERENCES task(id)
                )
                """
            )
        )
        db.session.execute(
            text(
                "CREATE INDEX idx_task_dependency_pred "
                "ON task_dependency(predecessor_id)"
            )
        )
        db.session.execute(
            text(
                "CREATE INDEX idx_task_dependency_succ "
                "ON task_dependency(successor_id)"
            )
        )

    db.session.commit()

