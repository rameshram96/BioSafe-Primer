"""
database.py — BioSafe Primer v2  (Supabase / PostgreSQL backend)
All function signatures are identical to the SQLite version —
app.py and auth.py require NO changes.
"""

import os
import json
from datetime import datetime
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
import streamlit as st
from supabase import create_client

# ── Connection string from Streamlit secrets ──────────────────────────────────
def init_db():
    # Looks for these keys in the Streamlit Cloud dashboard
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

@contextmanager
def _conn():
    """Context manager — opens a connection, yields cursor, commits, closes."""
    dsn  = _get_dsn()
    conn = psycopg2.connect(dsn)
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                yield cur
    finally:
        conn.close()


# ── Schema ────────────────────────────────────────────────────────────────────
def init_db():
    """Create all tables if they do not already exist."""
    with _conn() as c:

        # Users
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            SERIAL PRIMARY KEY,
                name          TEXT    NOT NULL,
                email         TEXT    UNIQUE NOT NULL,
                password_hash TEXT,
                auth_provider TEXT    DEFAULT 'email',
                created_at    TIMESTAMPTZ DEFAULT NOW(),
                is_active     INTEGER DEFAULT 1
            )
        """)

        # Projects
        c.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id              SERIAL PRIMARY KEY,
                user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name            TEXT    NOT NULL,
                vector_name     TEXT,
                vector_length   INTEGER,
                vector_sequence TEXT    DEFAULT '',
                vector_features TEXT    DEFAULT '[]',
                created_at      TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Primers
        c.execute("""
            CREATE TABLE IF NOT EXISTS primers (
                id                SERIAL PRIMARY KEY,
                project_id        INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                amplicon_num      INTEGER,
                fp_sequence       TEXT,
                rp_sequence       TEXT,
                fp_length         INTEGER,
                rp_length         INTEGER,
                fp_tm             REAL,
                rp_tm             REAL,
                fp_gc             REAL,
                rp_gc             REAL,
                fp_hairpin_tm     REAL DEFAULT 0,
                rp_hairpin_tm     REAL DEFAULT 0,
                fp_end_stability  REAL DEFAULT 0,
                rp_end_stability  REAL DEFAULT 0,
                fp_penalty        REAL DEFAULT 0,
                rp_penalty        REAL DEFAULT 0,
                pair_penalty      REAL DEFAULT 0,
                fp_self_any       REAL DEFAULT 0,
                fp_self_end       REAL DEFAULT 0,
                rp_self_any       REAL DEFAULT 0,
                rp_self_end       REAL DEFAULT 0,
                amplicon_start    INTEGER,
                amplicon_end      INTEGER,
                amplicon_length   INTEGER,
                overlap_next      INTEGER,
                overlap_prev      INTEGER,
                amplicon_name     TEXT DEFAULT '',
                version           INTEGER DEFAULT 1,
                status            TEXT DEFAULT 'Pending'
            )
        """)

        # PCR Runs
        c.execute("""
            CREATE TABLE IF NOT EXISTS pcr_runs (
                id             SERIAL PRIMARY KEY,
                project_id     INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                primer_id      INTEGER REFERENCES primers(id)  ON DELETE CASCADE,
                run_date       TEXT,
                result         TEXT,
                gel_image_path TEXT,
                lane_number    INTEGER,
                notes          TEXT
            )
        """)

        # Redesign History
        c.execute("""
            CREATE TABLE IF NOT EXISTS redesign_history (
                id                        SERIAL PRIMARY KEY,
                project_id                INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                amplicon_num              INTEGER,
                old_primer_id             INTEGER,
                new_primer_id             INTEGER,
                extension_left            INTEGER,
                extension_right           INTEGER,
                failure_type              TEXT    DEFAULT '',
                attempt_num               INTEGER DEFAULT 1,
                upstream_overlap_result   INTEGER,
                downstream_overlap_result INTEGER,
                redesign_date             TIMESTAMPTZ DEFAULT NOW(),
                reason                    TEXT
            )
        """)


# ══════════════════════════════════════════════════════════════════════════════
# User CRUD
# ══════════════════════════════════════════════════════════════════════════════

def create_user(name, email, password_hash, auth_provider='email'):
    with _conn() as c:
        c.execute(
            "INSERT INTO users (name, email, password_hash, auth_provider) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (name, email.strip().lower(), password_hash, auth_provider)
        )
        return c.fetchone()["id"]


def get_user_by_email(email):
    with _conn() as c:
        c.execute("SELECT * FROM users WHERE email = %s",
                  (email.strip().lower(),))
        row = c.fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id):
    with _conn() as c:
        c.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        row = c.fetchone()
        return dict(row) if row else None


# ══════════════════════════════════════════════════════════════════════════════
# Project CRUD  (user-scoped)
# ══════════════════════════════════════════════════════════════════════════════

def save_project(name, vector_name, vector_length, user_id,
                  vector_sequence='', vector_features='[]'):
    with _conn() as c:
        c.execute(
            "INSERT INTO projects "
            "(user_id, name, vector_name, vector_length, "
            " vector_sequence, vector_features) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (user_id, name, vector_name, vector_length,
             vector_sequence, vector_features)
        )
        return c.fetchone()["id"]


def get_project(project_id, user_id):
    with _conn() as c:
        c.execute(
            "SELECT * FROM projects WHERE id = %s AND user_id = %s",
            (project_id, user_id)
        )
        row = c.fetchone()
        return dict(row) if row else None


def get_all_projects(user_id):
    with _conn() as c:
        c.execute(
            "SELECT * FROM projects WHERE user_id = %s "
            "ORDER BY created_at DESC",
            (user_id,)
        )
        return [dict(r) for r in c.fetchall()]


def delete_project(project_id, user_id):
    with _conn() as c:
        c.execute(
            "SELECT id FROM projects WHERE id = %s AND user_id = %s",
            (project_id, user_id)
        )
        if not c.fetchone():
            return False
        # Child rows deleted by ON DELETE CASCADE
        c.execute("DELETE FROM projects WHERE id = %s", (project_id,))
        return True


def get_project_stats(project_id):
    with _conn() as c:
        c.execute(
            "SELECT amplicon_num, status FROM primers "
            "WHERE project_id = %s ORDER BY amplicon_num, version DESC",
            (project_id,)
        )
        rows = c.fetchall()
    seen = {}
    for row in rows:
        an = row["amplicon_num"]
        if an not in seen:
            seen[an] = row["status"]
    total = len(seen)
    done  = sum(1 for s in seen.values() if s == 'Done')
    return {'total': total, 'done': done}


# ══════════════════════════════════════════════════════════════════════════════
# Primer CRUD
# ══════════════════════════════════════════════════════════════════════════════

def save_primers(project_id, primers_list):
    with _conn() as c:
        for p in primers_list:
            c.execute("""
                INSERT INTO primers (
                    project_id, amplicon_num, amplicon_name,
                    fp_sequence, rp_sequence,
                    fp_length, rp_length, fp_tm, rp_tm, fp_gc, rp_gc,
                    fp_hairpin_tm, rp_hairpin_tm,
                    fp_end_stability, rp_end_stability,
                    fp_penalty, rp_penalty, pair_penalty,
                    fp_self_any, fp_self_end, rp_self_any, rp_self_end,
                    amplicon_start, amplicon_end, amplicon_length,
                    overlap_next, overlap_prev, version
                ) VALUES (
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,%s
                )
            """, (
                project_id,
                p['amplicon_num'],
                p.get('amplicon_name', f"Amplicon_{p['amplicon_num']}"),
                p['fp_sequence'], p['rp_sequence'],
                p['fp_length'],   p['rp_length'],
                p['fp_tm'],       p['rp_tm'],
                p['fp_gc'],       p['rp_gc'],
                p.get('fp_hairpin_tm', 0),    p.get('rp_hairpin_tm', 0),
                p.get('fp_end_stability', 0), p.get('rp_end_stability', 0),
                p.get('fp_penalty', 0),       p.get('rp_penalty', 0),
                p.get('pair_penalty', 0),
                p.get('fp_self_any', 0), p.get('fp_self_end', 0),
                p.get('rp_self_any', 0), p.get('rp_self_end', 0),
                p['amplicon_start'], p['amplicon_end'], p['amplicon_length'],
                p.get('overlap_next') or 0,
                p.get('overlap_prev') or 0,
                p.get('version', 1)
            ))


def update_amplicon_name(primer_id, name):
    with _conn() as c:
        c.execute("UPDATE primers SET amplicon_name = %s WHERE id = %s",
                  (name, primer_id))


def get_primers_by_project(project_id):
    with _conn() as c:
        c.execute(
            "SELECT * FROM primers WHERE project_id = %s "
            "ORDER BY amplicon_num, version DESC",
            (project_id,)
        )
        return [dict(r) for r in c.fetchall()]


def update_primer_status(primer_id, status):
    with _conn() as c:
        c.execute("UPDATE primers SET status = %s WHERE id = %s",
                  (status, primer_id))


# ══════════════════════════════════════════════════════════════════════════════
# PCR Run CRUD
# ══════════════════════════════════════════════════════════════════════════════

def save_pcr_run(project_id, primer_id, result, gel_image_path,
                  lane_number, notes):
    run_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    with _conn() as c:
        c.execute(
            "INSERT INTO pcr_runs "
            "(project_id, primer_id, run_date, result, "
            " gel_image_path, lane_number, notes) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (project_id, primer_id, run_date, result,
             gel_image_path, lane_number, notes)
        )


def get_pcr_runs_by_project(project_id):
    with _conn() as c:
        c.execute("""
            SELECT r.*, p.amplicon_num, p.fp_sequence,
                   p.rp_sequence, p.version
            FROM pcr_runs r
            JOIN primers p ON r.primer_id = p.id
            WHERE r.project_id = %s
            ORDER BY r.run_date DESC
        """, (project_id,))
        return [dict(r) for r in c.fetchall()]


# ══════════════════════════════════════════════════════════════════════════════
# Redesign History
# ══════════════════════════════════════════════════════════════════════════════

def save_redesign_history(project_id, amplicon_num, old_primer_id,
                           new_primer_id, extension_left, extension_right,
                           reason, failure_type='', attempt_num=1,
                           upstream_overlap=None, downstream_overlap=None):
    with _conn() as c:
        c.execute("""
            INSERT INTO redesign_history (
                project_id, amplicon_num, old_primer_id, new_primer_id,
                extension_left, extension_right, reason,
                failure_type, attempt_num,
                upstream_overlap_result, downstream_overlap_result
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (project_id, amplicon_num, old_primer_id, new_primer_id,
              extension_left, extension_right, reason,
              failure_type, attempt_num, upstream_overlap, downstream_overlap))


def get_redesign_history(project_id):
    with _conn() as c:
        c.execute(
            "SELECT * FROM redesign_history WHERE project_id = %s "
            "ORDER BY redesign_date DESC",
            (project_id,)
        )
        return [dict(r) for r in c.fetchall()]
