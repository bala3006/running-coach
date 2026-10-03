import os
import re
import sqlite3
import sys
from array import array
from contextlib import closing
from math import sqrt
from pathlib import Path


def _database_path() -> Path:
    configured = os.getenv("RUNNING_COACH_DB")
    return Path(configured).expanduser() if configured else Path.home() / ".running-coach" / "coach.sqlite3"


def _connect() -> sqlite3.Connection:
    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    connection.execute("CREATE INDEX IF NOT EXISTS messages_session_id ON messages(session_id, id)")
    connection.execute(
        """CREATE TABLE IF NOT EXISTS run_activities (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            sport_type TEXT,
            distance_km REAL NOT NULL,
            moving_time_minutes REAL NOT NULL,
            start_date_local TEXT,
            average_heartrate REAL,
            elevation_gain_m REAL,
            descent_m REAL,
            temperature_c REAL,
            humidity_pct REAL,
            feeling TEXT NOT NULL DEFAULT '',
            perceived_effort INTEGER,
            notes TEXT NOT NULL DEFAULT '',
            synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS race_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            event_date TEXT NOT NULL,
            distance_km REAL NOT NULL,
            target_time_seconds INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    connection.execute(
        """CREATE VIRTUAL TABLE IF NOT EXISTS training_memory USING fts5(
            source_type UNINDEXED,
            source_id UNINDEXED,
            title,
            content
        )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS training_embeddings (
            source_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            model TEXT NOT NULL,
            dimensions INTEGER NOT NULL,
            vector BLOB NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (source_type, source_id, model)
        )"""
    )
    return connection


def _index_memory(
    connection: sqlite3.Connection, source_type: str, source_id: str, title: str, content: str
) -> None:
    existing = connection.execute(
        "SELECT title, content FROM training_memory WHERE source_type = ? AND source_id = ?",
        (source_type, source_id),
    ).fetchone()
    if existing and existing["title"] == title and existing["content"] == content:
        return
    connection.execute(
        "DELETE FROM training_memory WHERE source_type = ? AND source_id = ?",
        (source_type, source_id),
    )
    connection.execute(
        "DELETE FROM training_embeddings WHERE source_type = ? AND source_id = ?",
        (source_type, source_id),
    )
    connection.execute(
        "INSERT INTO training_memory (source_type, source_id, title, content) VALUES (?, ?, ?, ?)",
        (source_type, source_id, title, content),
    )


def _run_memory_text(run: dict) -> str:
    distance = float(run["distance_km"])
    duration = float(run["moving_time_minutes"])
    details = [
        f"Date: {run.get('start_date_local') or 'unknown'}",
        f"Distance: {distance:.2f} km",
        f"Moving time: {duration:.1f} minutes",
    ]
    if distance > 0:
        details.append(f"Average pace: {duration / distance:.2f} minutes per km")
    for key, label, unit in (
        ("average_heartrate", "Average heart rate", "bpm"),
        ("elevation_gain_m", "Elevation gain", "m"),
        ("descent_m", "Descent", "m"),
        ("temperature_c", "Temperature", "C"),
        ("humidity_pct", "Humidity", "%"),
        ("perceived_effort", "Perceived effort", "/10"),
    ):
        value = run.get(key)
        if value is not None:
            details.append(f"{label}: {value} {unit}")
    for key, label in (("feeling", "How the run felt"), ("notes", "Runner notes")):
        value = run.get(key)
        if value:
            details.append(f"{label}: {value}")
    return "; ".join(details)


def upsert_runs(activities: list[dict]) -> int:
    with closing(_connect()) as connection:
        with connection:
            for activity in activities:
                run = {
                    "id": str(activity["id"]),
                    "name": activity.get("name") or "Run",
                    "sport_type": activity.get("sport_type"),
                    "distance_km": float(activity.get("distance_km") or 0),
                    "moving_time_minutes": float(activity.get("moving_time_minutes") or 0),
                    "start_date_local": activity.get("start_date_local"),
                    "average_heartrate": activity.get("average_heartrate"),
                    "elevation_gain_m": activity.get("elevation_gain_m"),
                    "descent_m": activity.get("descent_m"),
                    "temperature_c": activity.get("temperature_c"),
                    "humidity_pct": activity.get("humidity_pct"),
                }
                connection.execute(
                    """INSERT INTO run_activities (
                        id, name, sport_type, distance_km, moving_time_minutes,
                        start_date_local, average_heartrate, elevation_gain_m,
                        descent_m, temperature_c, humidity_pct
                    ) VALUES (
                        :id, :name, :sport_type, :distance_km, :moving_time_minutes,
                        :start_date_local, :average_heartrate, :elevation_gain_m,
                        :descent_m, :temperature_c, :humidity_pct
                    ) ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        sport_type = excluded.sport_type,
                        distance_km = excluded.distance_km,
                        moving_time_minutes = excluded.moving_time_minutes,
                        start_date_local = excluded.start_date_local,
                        average_heartrate = excluded.average_heartrate,
                        elevation_gain_m = COALESCE(excluded.elevation_gain_m, run_activities.elevation_gain_m),
                        descent_m = COALESCE(excluded.descent_m, run_activities.descent_m),
                        temperature_c = COALESCE(excluded.temperature_c, run_activities.temperature_c),
                        humidity_pct = COALESCE(excluded.humidity_pct, run_activities.humidity_pct),
                        synced_at = CURRENT_TIMESTAMP""",
                    run,
                )
                saved = connection.execute(
                    "SELECT * FROM run_activities WHERE id = ?", (run["id"],)
                ).fetchone()
                _index_memory(
                    connection,
                    "run",
                    run["id"],
                    saved["name"],
                    _run_memory_text(dict(saved)),
                )
    return len(activities)


def list_runs(limit: int = 50) -> list[dict]:
    with closing(_connect()) as connection:
        rows = connection.execute(
            "SELECT * FROM run_activities ORDER BY start_date_local DESC, id DESC LIMIT ?",
            (max(1, min(limit, 100)),),
        ).fetchall()
    return [dict(row) for row in rows]


def save_run_reflection(
    activity_id: str,
    feeling: str,
    notes: str,
    perceived_effort: int | None,
    temperature_c: float | None,
    humidity_pct: float | None,
) -> None:
    with closing(_connect()) as connection:
        with connection:
            result = connection.execute(
                """UPDATE run_activities SET feeling = ?, notes = ?, perceived_effort = ?,
                    temperature_c = ?, humidity_pct = ? WHERE id = ?""",
                (feeling, notes, perceived_effort, temperature_c, humidity_pct, activity_id),
            )
            if not result.rowcount:
                raise ValueError("Run was not found in the local training log")
            run = dict(
                connection.execute(
                    "SELECT * FROM run_activities WHERE id = ?", (activity_id,)
                ).fetchone()
            )
            _index_memory(
                connection,
                "run",
                activity_id,
                run["name"],
                _run_memory_text(run),
            )


def save_race_goal(name: str, event_date: str, distance_km: float, target_time_seconds: int) -> int:
    with closing(_connect()) as connection:
        with connection:
            cursor = connection.execute(
                """INSERT INTO race_goals (name, event_date, distance_km, target_time_seconds)
                    VALUES (?, ?, ?, ?)""",
                (name, event_date, distance_km, target_time_seconds),
            )
            goal_id = int(cursor.lastrowid)
            _index_memory(
                connection,
                "race",
                str(goal_id),
                name,
                f"Event date: {event_date}; race distance: {distance_km} km; "
                f"target finish time: {target_time_seconds} seconds",
            )
    return goal_id


def list_race_goals() -> list[dict]:
    with closing(_connect()) as connection:
        rows = connection.execute(
            "SELECT * FROM race_goals ORDER BY event_date, id"
        ).fetchall()
    return [dict(row) for row in rows]


def list_unembedded_training_documents(model: str, limit: int = 256) -> list[dict[str, str]]:
    with closing(_connect()) as connection:
        rows = connection.execute(
            """SELECT memory.source_type, memory.source_id, memory.title, memory.content
                FROM training_memory AS memory
                LEFT JOIN training_embeddings AS embedding
                  ON embedding.source_type = memory.source_type
                  AND embedding.source_id = memory.source_id
                  AND embedding.model = ?
                WHERE embedding.source_id IS NULL
                ORDER BY memory.rowid
                LIMIT ?""",
            (model, max(1, min(limit, 1000))),
        ).fetchall()
    return [dict(row) for row in rows]


def save_training_embedding(
    source_type: str, source_id: str, model: str, vector: list[float]
) -> None:
    packed = array("f", vector)
    if not packed or any(not value == value or abs(value) == float("inf") for value in packed):
        raise ValueError("Embedding vectors must contain finite values")
    if sys.byteorder != "little":
        packed.byteswap()
    with closing(_connect()) as connection:
        with connection:
            connection.execute(
                """INSERT INTO training_embeddings
                    (source_type, source_id, model, dimensions, vector)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(source_type, source_id, model) DO UPDATE SET
                        dimensions = excluded.dimensions,
                        vector = excluded.vector,
                        created_at = CURRENT_TIMESTAMP""",
                (source_type, source_id, model, len(packed), packed.tobytes()),
            )


def training_memory_stats(model: str) -> dict[str, int]:
    with closing(_connect()) as connection:
        row = connection.execute(
            """SELECT COUNT(*) AS total,
                    SUM(CASE WHEN EXISTS (
                        SELECT 1 FROM training_embeddings AS embedding
                        WHERE embedding.source_type = memory.source_type
                          AND embedding.source_id = memory.source_id
                          AND embedding.model = ?
                    ) THEN 1 ELSE 0 END) AS embedded
                FROM training_memory AS memory""",
            (model,),
        ).fetchone()
    return {"total": row["total"], "embedded": row["embedded"] or 0}


def _vector_results(query_embedding: list[float], model: str, limit: int) -> list[dict]:
    query_vector = array("f", query_embedding)
    if not query_vector:
        return []
    query_norm = sqrt(sum(value * value for value in query_vector))
    if query_norm == 0:
        return []
    if sys.byteorder != "little":
        query_vector.byteswap()
    with closing(_connect()) as connection:
        rows = connection.execute(
            """SELECT memory.source_type, memory.source_id, memory.title, memory.content,
                    embedding.dimensions, embedding.vector
                FROM training_embeddings AS embedding
                JOIN training_memory AS memory
                  ON memory.source_type = embedding.source_type
                  AND memory.source_id = embedding.source_id
                WHERE embedding.model = ?""",
            (model,),
        ).fetchall()
    scored = []
    for row in rows:
        if row["dimensions"] != len(query_vector):
            continue
        stored = array("f")
        stored.frombytes(row["vector"])
        if sys.byteorder != "little":
            stored.byteswap()
        stored_norm = sqrt(sum(value * value for value in stored))
        if stored_norm == 0:
            continue
        similarity = sum(left * right for left, right in zip(query_vector, stored))
        similarity /= query_norm * stored_norm
        scored.append(
            (
                similarity,
                {
                    key: row[key]
                    for key in ("source_type", "source_id", "title", "content")
                },
            )
        )
    scored.sort(key=lambda item: item[0], reverse=True)
    return [record for _, record in scored[:limit]]


def search_training_memory(
    query: str,
    limit: int = 5,
    query_embedding: list[float] | None = None,
    embedding_model: str | None = None,
) -> list[dict[str, str]]:
    terms = list(dict.fromkeys(re.findall(r"[\w]+", query, flags=re.UNICODE)))
    result_limit = max(1, min(limit, 10))
    lexical = []
    if terms:
        match_query = " OR ".join(f'"{term}"' for term in terms)
        with closing(_connect()) as connection:
            rows = connection.execute(
                """SELECT source_type, source_id, title, content FROM training_memory
                    WHERE training_memory MATCH ? ORDER BY bm25(training_memory) LIMIT ?""",
                (match_query, result_limit),
            ).fetchall()
        lexical = [dict(row) for row in rows]
    semantic = (
        _vector_results(query_embedding, embedding_model, result_limit)
        if query_embedding and embedding_model
        else []
    )
    ranks: dict[tuple[str, str], tuple[float, dict]] = {}
    for result_set in (lexical, semantic):
        for rank, record in enumerate(result_set, 1):
            key = (record["source_type"], record["source_id"])
            score, existing = ranks.get(key, (0.0, record))
            ranks[key] = (score + 1 / (60 + rank), existing)
    ordered = sorted(ranks.values(), key=lambda item: item[0], reverse=True)
    return [record for _, record in ordered[:result_limit]]


def get_history(session_id: str, limit: int = 30) -> list[dict[str, str]]:
    with closing(_connect()) as connection:
        with connection:
            rows = connection.execute(
                "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
    return [{"role": role, "content": content} for role, content in reversed(rows)]


def save_exchange(session_id: str, user_message: str, assistant_message: str) -> None:
    with closing(_connect()) as connection:
        with connection:
            connection.executemany(
                "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
                [
                    (session_id, "user", user_message),
                    (session_id, "assistant", assistant_message),
                ],
            )
