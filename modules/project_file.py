"""
project_file.py — BioSafe Primer (.bsp) file handler.

A .bsp file is a JSON file containing the complete project state:
  - project metadata
  - vector sequence and features
  - all primers (all versions)
  - PCR run log
  - redesign history
  - gel images (base64 encoded)

No database required. One file per project.
"""
import json
import base64
import os
from datetime import datetime

BSP_VERSION = "1.0"


def new_project(name, vector_name, vector_length,
                vector_sequence, vector_features):
    """Create a fresh project state dict."""
    return {
        "bsp_version":      BSP_VERSION,
        "project_name":     name,
        "vector_name":      vector_name,
        "vector_length":    vector_length,
        "vector_sequence":  vector_sequence,
        "vector_features":  vector_features,
        "created_at":       datetime.now().strftime("%Y-%m-%d %H:%M"),
        "last_saved":       None,
        "primers":          [],
        "pcr_runs":         [],
        "redesign_history": [],
    }


def save_project_bytes(state):
    """
    Serialise project state to JSON bytes for download.
    Gel image paths on disk are read and stored as base64.
    Returns bytes.
    """
    export_state = json.loads(json.dumps(state))   # deep copy

    for run in export_state.get("pcr_runs", []):
        path = run.get("gel_image_path")
        if path and os.path.exists(path):
            with open(path, "rb") as f:
                run["gel_image_b64"] = base64.b64encode(f.read()).decode()
            run["gel_image_path"] = os.path.basename(path)
        else:
            run["gel_image_b64"] = None

    export_state["last_saved"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    return json.dumps(export_state, indent=2, ensure_ascii=False).encode("utf-8")


def load_project_bytes(file_bytes, gel_dir):
    """
    Load project state from .bsp file bytes.
    Extracts base64 gel images to gel_dir on disk.
    Returns state dict.
    """
    state = json.loads(file_bytes.decode("utf-8"))

    # Validate
    if "project_name" not in state:
        raise ValueError("Not a valid BioSafe Primer (.bsp) file.")

    os.makedirs(gel_dir, exist_ok=True)

    for run in state.get("pcr_runs", []):
        b64 = run.pop("gel_image_b64", None)
        fname = run.get("gel_image_path")
        if b64 and fname:
            full_path = os.path.join(gel_dir, os.path.basename(fname))
            with open(full_path, "wb") as f:
                f.write(base64.b64decode(b64))
            run["gel_image_path"] = full_path

    return state


# ── Primer helpers ────────────────────────────────────────────────────────────

def get_best_primers(state):
    """Return latest version per amplicon from state."""
    seen = {}
    for p in state.get("primers", []):
        an = p["amplicon_num"]
        if an not in seen or p.get("version", 1) > seen[an].get("version", 1):
            seen[an] = p
    return sorted(seen.values(), key=lambda x: x["amplicon_num"])


def add_primers(state, primers):
    """Append newly designed primers to state."""
    state["primers"].extend(primers)


def update_primer_status(state, primer_id, new_status):
    """Update status of a primer by its id (index-based)."""
    for p in state["primers"]:
        if p.get("_id") == primer_id:
            p["status"] = new_status
            return


def update_amplicon_name(state, primer_id, new_name):
    """Rename an amplicon across all its versions."""
    amp_num = None
    for p in state["primers"]:
        if p.get("_id") == primer_id:
            amp_num = p["amplicon_num"]
            break
    if amp_num is not None:
        for p in state["primers"]:
            if p["amplicon_num"] == amp_num:
                p["amplicon_name"] = new_name


def add_pcr_run(state, primer_id, result, gel_path, lane_number, notes,
                amplicon_num, fp_sequence, rp_sequence):
    """Log a PCR run."""
    state["pcr_runs"].append({
        "id":             len(state["pcr_runs"]) + 1,
        "primer_id":      primer_id,
        "amplicon_num":   amplicon_num,
        "fp_sequence":    fp_sequence,
        "rp_sequence":    rp_sequence,
        "result":         result,
        "gel_image_path": gel_path,
        "lane_number":    lane_number,
        "notes":          notes,
        "run_date":       datetime.now().strftime("%Y-%m-%d %H:%M"),
    })


def add_redesign_history(state, amplicon_num, old_primer_id,
                          ext_left, ext_right, reason,
                          failure_type, attempt_num,
                          upstream_overlap, downstream_overlap):
    """Record a redesign event."""
    state["redesign_history"].append({
        "amplicon_num":               amplicon_num,
        "old_primer_id":              old_primer_id,
        "extension_left":             ext_left,
        "extension_right":            ext_right,
        "failure_type":               failure_type,
        "attempt_num":                attempt_num,
        "upstream_overlap_result":    upstream_overlap,
        "downstream_overlap_result":  downstream_overlap,
        "reason":                     reason,
        "redesign_date":              datetime.now().strftime("%Y-%m-%d %H:%M"),
    })


def assign_ids(primers):
    """Assign unique _id to each primer dict (index-based)."""
    for i, p in enumerate(primers):
        p["_id"] = i
    return primers


def get_project_stats(state):
    """Return done/total counts."""
    best  = get_best_primers(state)
    total = len(best)
    done  = sum(1 for p in best if p.get("status") == "Done")
    return {"total": total, "done": done}
