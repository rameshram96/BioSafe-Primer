"""
database.py — BioSafe Primer v2 database layer
New in v2: users table; all projects are user-scoped.
DB file: database/biosafe_primer.db  (fresh — do NOT copy old pcr_tracker.db)
"""

import sqlite3
import os
import json
from datetime import datetime

# ── New DB file (v2 clean start) ──────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'database', 'biosafe_primer.db')


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables if they do not already exist."""
    conn = get_connection()
    c = conn.cursor()

    # ── Users ─────────────────────────────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            email         TEXT    UNIQUE NOT NULL,
            password_hash TEXT,
            auth_provider TEXT    DEFAULT 'email',
            created_at    TEXT    DEFAULT CURRENT_TIMESTAMP,
            is_active     INTEGER DEFAULT 1
        )
    ''')

    # ── Projects (owned by a user) ─────────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            name            TEXT    NOT NULL,
            vector_name     TEXT,
            vector_length   INTEGER,
            vector_sequence TEXT    DEFAULT '',
            vector_features TEXT    DEFAULT '[]',
            created_at      TEXT    DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # ── Primers ────────────────────────────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS primers (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id        INTEGER,
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
            status            TEXT DEFAULT 'Pending',
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
    ''')

    # ── PCR Runs ───────────────────────────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS pcr_runs (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id     INTEGER,
            primer_id      INTEGER,
            run_date       TEXT,
            result         TEXT,
            gel_image_path TEXT,
            lane_number    INTEGER,
            notes          TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY(primer_id)  REFERENCES primers(id)  ON DELETE CASCADE
        )
    ''')

    # ── Redesign History ───────────────────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS redesign_history (
            id                        INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id                INTEGER,
            amplicon_num              INTEGER,
            old_primer_id             INTEGER,
            new_primer_id             INTEGER,
            extension_left            INTEGER,
            extension_right           INTEGER,
            failure_type              TEXT    DEFAULT '',
            attempt_num               INTEGER DEFAULT 1,
            upstream_overlap_result   INTEGER,
            downstream_overlap_result INTEGER,
            redesign_date             TEXT    DEFAULT CURRENT_TIMESTAMP,
            reason                    TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
    ''')

    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# User CRUD
# ══════════════════════════════════════════════════════════════════════════════

def create_user(name, email, password_hash, auth_provider='email'):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO users (name, email, password_hash, auth_provider) "
        "VALUES (?, ?, ?, ?)",
        (name, email.strip().lower(), password_hash, auth_provider)
    )
    uid = c.lastrowid
    conn.commit()
    conn.close()
    return uid


def get_user_by_email(email):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


# ══════════════════════════════════════════════════════════════════════════════
# Project CRUD  (always scoped to user_id)
# ══════════════════════════════════════════════════════════════════════════════

def save_project(name, vector_name, vector_length, user_id,
                  vector_sequence='', vector_features='[]'):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO projects "
        "(user_id, name, vector_name, vector_length, vector_sequence, vector_features) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, name, vector_name, vector_length, vector_sequence, vector_features)
    )
    pid = c.lastrowid
    conn.commit()
    conn.close()
    return pid


def get_project(project_id, user_id):
    """Return project only if it belongs to user_id (ownership check)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id)
    )
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_projects(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM projects WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    )
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_project(project_id, user_id):
    """Delete project and all child records. Returns False if not owned by user."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, user_id)
    )
    if not c.fetchone():
        conn.close()
        return False
    c.execute("DELETE FROM redesign_history WHERE project_id = ?", (project_id,))
    c.execute("DELETE FROM pcr_runs        WHERE project_id = ?", (project_id,))
    c.execute("DELETE FROM primers         WHERE project_id = ?", (project_id,))
    c.execute("DELETE FROM projects        WHERE id = ?",         (project_id,))
    conn.commit()
    conn.close()
    return True


def get_project_stats(project_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT amplicon_num, status FROM primers "
        "WHERE project_id = ? ORDER BY amplicon_num, version DESC",
        (project_id,)
    )
    rows = c.fetchall()
    conn.close()
    seen = {}
    for row in rows:
        an = row[0]
        if an not in seen:
            seen[an] = row[1]
    total = len(seen)
    done  = sum(1 for s in seen.values() if s == 'Done')
    return {'total': total, 'done': done}


# ══════════════════════════════════════════════════════════════════════════════
# Primer CRUD
# ══════════════════════════════════════════════════════════════════════════════

def save_primers(project_id, primers_list):
    conn = get_connection()
    c = conn.cursor()
    for p in primers_list:
        c.execute('''
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
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
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
    conn.commit()
    conn.close()


def update_amplicon_name(primer_id, name):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE primers SET amplicon_name = ? WHERE id = ?", (name, primer_id))
    conn.commit()
    conn.close()


def get_primers_by_project(project_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM primers WHERE project_id = ? "
        "ORDER BY amplicon_num, version DESC",
        (project_id,)
    )
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_primer_status(primer_id, status):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE primers SET status = ? WHERE id = ?", (status, primer_id))
    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# PCR Run CRUD
# ══════════════════════════════════════════════════════════════════════════════

def save_pcr_run(project_id, primer_id, result, gel_image_path, lane_number, notes):
    conn = get_connection()
    c = conn.cursor()
    run_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    c.execute(
        "INSERT INTO pcr_runs "
        "(project_id, primer_id, run_date, result, gel_image_path, lane_number, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (project_id, primer_id, run_date, result, gel_image_path, lane_number, notes)
    )
    conn.commit()
    conn.close()


def get_pcr_runs_by_project(project_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT r.*, p.amplicon_num, p.fp_sequence, p.rp_sequence, p.version
        FROM pcr_runs r
        JOIN primers p ON r.primer_id = p.id
        WHERE r.project_id = ?
        ORDER BY r.run_date DESC
    ''', (project_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════════════════
# Redesign History
# ══════════════════════════════════════════════════════════════════════════════

def save_redesign_history(project_id, amplicon_num, old_primer_id,
                           new_primer_id, extension_left, extension_right,
                           reason, failure_type='', attempt_num=1,
                           upstream_overlap=None, downstream_overlap=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO redesign_history (
            project_id, amplicon_num, old_primer_id, new_primer_id,
            extension_left, extension_right, reason,
            failure_type, attempt_num,
            upstream_overlap_result, downstream_overlap_result
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (project_id, amplicon_num, old_primer_id, new_primer_id,
          extension_left, extension_right, reason,
          failure_type, attempt_num, upstream_overlap, downstream_overlap))
    conn.commit()
    conn.close()


def get_redesign_history(project_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM redesign_history WHERE project_id = ? "
        "ORDER BY redesign_date DESC",
        (project_id,)
    )
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]
