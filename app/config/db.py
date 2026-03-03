import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


@contextmanager
def get_db_connection():
    """Context manager — auto-commits on success, rolls back on error."""
    conn = None
    try:
        conn = psycopg2.connect(
            settings.database_url,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        yield conn
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def run_migrations() -> None:
    """Idempotent schema setup — safe to run on every startup."""
    sql = """
        CREATE EXTENSION IF NOT EXISTS vector;

        CREATE TABLE IF NOT EXISTS posts (
            id                  VARCHAR PRIMARY KEY,
            posted_at           TIMESTAMP WITH TIME ZONE NOT NULL,
            post_type           VARCHAR NOT NULL,
            raw_content         TEXT,
            analysis_text       TEXT,
            shared_article      JSONB,
            likes               INT DEFAULT 0,
            reposts             INT DEFAULT 0,
            replies             INT DEFAULT 0,
            caps_ratio          FLOAT DEFAULT 0,
            exclamation_count   INT DEFAULT 0,
            question_mark_count INT DEFAULT 0,
            has_nickname        BOOLEAN DEFAULT FALSE,
            has_superlative     BOOLEAN DEFAULT FALSE,
            has_grievance       BOOLEAN DEFAULT FALSE,
            has_aggression      BOOLEAN DEFAULT FALSE,
            has_rally           BOOLEAN DEFAULT FALSE,
            word_count          INT DEFAULT 0,
            signal_strength     VARCHAR,
            created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS local_analyses (
            id              SERIAL PRIMARY KEY,
            post_id         VARCHAR UNIQUE REFERENCES posts(id) ON DELETE CASCADE,
            sentiment       JSONB,
            top_emotions    JSONB,
            entities        JSONB,
            zeroshot_mood   JSONB,
            analyzed_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS daily_mood_state (
            date                DATE PRIMARY KEY,
            last_updated        TIMESTAMP WITH TIME ZONE,
            last_fetch_cursor   VARCHAR,
            current_mood        VARCHAR,
            current_intensity   VARCHAR,
            current_confidence  FLOAT,
            accumulated_stats   JSONB,
            context_summaries   JSONB,
            mood_timeline       JSONB,
            raw_state           JSONB
        );

        CREATE TABLE IF NOT EXISTS mood_cycle_log (
            id                  SERIAL PRIMARY KEY,
            date                DATE NOT NULL,
            ran_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            new_tweets_count    INT,
            mood_before         VARCHAR,
            mood_after          VARCHAR,
            shift_detected      BOOLEAN DEFAULT FALSE,
            cycle_output        JSONB
        );

        -- Mood snapshots with outcome data for self-learning RAG
        CREATE TABLE IF NOT EXISTS mood_snapshots (
            id                  SERIAL PRIMARY KEY,
            snapshot_date       DATE NOT NULL,
            snapshot_time       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            mood                VARCHAR NOT NULL,
            intensity           VARCHAR,
            confidence          FLOAT,
            key_themes          JSONB,
            likely_trigger      TEXT,
            analyst_note        TEXT,
            signal_agreement    VARCHAR,
            -- Outcome data — filled in 2 hours after snapshot
            outcome_enriched    BOOLEAN DEFAULT FALSE,
            outcome_post_count  INT,
            outcome_avg_caps    FLOAT,
            outcome_aggression  INT,
            outcome_grievance   INT,
            outcome_duration_mins INT,
            outcome_summary     TEXT,
            -- Embedding stored separately in langchain tables
            embedding_id        UUID
        );

        CREATE TABLE IF NOT EXISTS langchain_pg_collection (
            uuid        UUID PRIMARY KEY,
            name        VARCHAR UNIQUE NOT NULL,
            cmetadata   JSONB
        );

        CREATE TABLE IF NOT EXISTS langchain_pg_embedding (
            uuid            UUID PRIMARY KEY,
            collection_id   UUID REFERENCES langchain_pg_collection(uuid) ON DELETE CASCADE,
            embedding       vector(384),
            document        TEXT,
            cmetadata       JSONB,
            custom_id       VARCHAR
        );

        -- Indexes
        CREATE INDEX IF NOT EXISTS idx_posts_posted_at
            ON posts(posted_at);

        CREATE INDEX IF NOT EXISTS idx_posts_post_type
            ON posts(post_type);

        CREATE INDEX IF NOT EXISTS idx_posts_signal_strength
            ON posts(signal_strength);

        CREATE INDEX IF NOT EXISTS idx_cycle_log_date
            ON mood_cycle_log(date);

        CREATE INDEX IF NOT EXISTS idx_cycle_log_shift
            ON mood_cycle_log(shift_detected);

        CREATE INDEX IF NOT EXISTS idx_mood_snapshots_date
            ON mood_snapshots(snapshot_date);

        CREATE INDEX IF NOT EXISTS idx_mood_snapshots_enriched
            ON mood_snapshots(outcome_enriched);

        CREATE INDEX IF NOT EXISTS idx_local_analyses_post_id
            ON local_analyses(post_id);

        -- Column additions for existing deployments (idempotent)
        ALTER TABLE posts ADD COLUMN IF NOT EXISTS question_mark_count INT DEFAULT 0;
        ALTER TABLE posts ADD COLUMN IF NOT EXISTS has_aggression BOOLEAN DEFAULT FALSE;
        ALTER TABLE local_analyses ADD COLUMN IF NOT EXISTS analyzed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
    logger.info("Migrations complete")