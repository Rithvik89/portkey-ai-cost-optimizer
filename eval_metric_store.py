import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any


class EvalMetricStore:
    def __init__(self, db_path: str = "metrics.db"):
        self.db_path = Path(db_path)
        self._init_db()

    # ---------- INIT ----------

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    trace_id TEXT NOT NULL,
                    agent TEXT NOT NULL,
                    model TEXT NOT NULL,

                    response_time_ms REAL,
                    cost REAL,
                    quality_score REAL,

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    UNIQUE(trace_id, agent, model)
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_eval_agent
                ON evaluations(agent)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_eval_model
                ON evaluations(model)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_eval_trace
                ON evaluations(trace_id)
            """)

    # ---------- INSERT ----------

    def upsert_evaluation(
        self,
        trace_id: str,
        agent: str,
        model: str,
        response_time_ms: Optional[float] = None,
        cost: Optional[float] = None,
        quality_score: Optional[float] = None,
    ) -> None:
        """
        Insert or update evaluation metrics.
        Idempotent per (trace_id, agent, model).
        """

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO evaluations (
                    trace_id,
                    agent,
                    model,
                    response_time_ms,
                    cost,
                    quality_score
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(trace_id, agent, model)
                DO UPDATE SET
                    response_time_ms = excluded.response_time_ms,
                    cost = excluded.cost,
                    quality_score = excluded.quality_score,
                    created_at = CURRENT_TIMESTAMP
            """, (
                trace_id,
                agent,
                model,
                response_time_ms,
                cost,
                quality_score
            ))

    def _fetch(self, query: str, params=()):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        
    # ---------- ADMIN ----------

    def drop_evaluations_table(self) -> None:
        """
        Drop the evaluations table if it exists.
        Use with caution. This is destructive.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM evaluations")


    # ---------- AGGREGATES ----------

    def aggregate_model_metrics(self):
        return self._fetch("""
            SELECT
                model,
                COUNT(*) AS traces,
                AVG(quality_score) AS avg_quality,
                AVG(cost) AS avg_cost,
                AVG(response_time_ms) AS avg_latency
            FROM evaluations
            GROUP BY model
        """)

