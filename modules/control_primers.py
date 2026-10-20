"""
Control primers = endogenous plant gene primer PAIRS (positive PCR controls).
One record per pair: name, target gene, forward, reverse, expected size, notes.
Length, GC% and Tm are auto-calculated (same salt / DNA conc as the design step).
"""
import io
import re
import math

import primer3

EDITOR_COLS = ['id', 'name', 'target', 'fp_sequence', 'rp_sequence',
               'expected_size', 'notes']

# Same conditions as DEFAULT/design params in the app
MV_CONC, DNA_CONC = 50.0, 50.0
TM_DIFF_WARN = 3.0      # °C between FP and RP
MIN_LEN, MAX_LEN = 15, 40

_ALIASES = {
    'name': 'name', 'control name': 'name', 'control': 'name', 'pair': 'name',
    'target': 'target', 'gene': 'target', 'gene/target': 'target',
    'target gene': 'target',
    'fp_sequence': 'fp_sequence', 'forward': 'fp_sequence', 'fp': 'fp_sequence',
    'forward primer': 'fp_sequence', 'forward sequence': 'fp_sequence',
    'rp_sequence': 'rp_sequence', 'reverse': 'rp_sequence', 'rp': 'rp_sequence',
    'reverse primer': 'rp_sequence', 'reverse sequence': 'rp_sequence',
    'expected_size': 'expected_size', 'expected size': 'expected_size',
    'expected product size': 'expected_size', 'product size': 'expected_size',
    'size': 'expected_size', 'expected size (bp)': 'expected_size',
    'notes': 'notes', 'note': 'notes',
}


def _s(v):
    """Cell -> clean string ('' for None / NaN)."""
    if v is None:
        return ''
    if isinstance(v, float) and math.isnan(v):
        return ''
    return str(v).strip()


def clean_sequence(seq):
    """Upper-case, drop whitespace/digits/punctuation, U -> T."""
    seq = re.sub(r'[^A-Za-z]', '', _s(seq)).upper()
    return seq.replace('U', 'T')


def _gc(seq):
    return round((seq.count('G') + seq.count('C')) / len(seq) * 100, 1) if seq else 0.0


def _tm(seq):
    return round(primer3.calc_tm(seq, mv_conc=MV_CONC, dv_conc=0.0,
                                  dntp_conc=0.0, dna_conc=DNA_CONC), 2)


def _check_primer(label, seq, row_label, errors, warnings):
    if not seq:
        errors.append(f"{row_label}: {label} sequence is empty.")
        return False
    bad = sorted(set(seq) - set('ACGT'))
    if bad:
        errors.append(f"{row_label}: {label} contains invalid characters "
                      f"({', '.join(bad)}). Only A, C, G, T allowed.")
        return False
    if not (MIN_LEN <= len(seq) <= MAX_LEN):
        warnings.append(f"{row_label}: {label} length {len(seq)} bp is outside "
                        f"{MIN_LEN}-{MAX_LEN} bp.")
    return True


def controls_from_rows(rows, existing=None):
    """
    rows: list of dicts from the editor / import (keys in EDITOR_COLS, all optional).
    existing: current project['control_primers'] (used to keep stable ids).
    Returns (controls, errors, warnings). Entirely blank rows are skipped.
    Ids are stable strings 'C1', 'C2', ... — runs reference them.
    """
    existing = existing or []
    used_ids = {c['id'] for c in existing}
    next_n = 1 + max([int(c['id'][1:]) for c in existing
                      if re.fullmatch(r'C\d+', c['id'])] + [0])

    controls, errors, warnings, seen_ids = [], [], [], set()
    for i, r in enumerate(rows, 1):
        name, target = _s(r.get('name')), _s(r.get('target'))
        fp, rp = clean_sequence(r.get('fp_sequence')), clean_sequence(r.get('rp_sequence'))
        if not any([name, target, fp, rp]):
            continue
        row_label = f"Row {i}" + (f" ({name})" if name else "")
        if not name:
            errors.append(f"{row_label}: name is required.")

        ok_f = _check_primer('Forward', fp, row_label, errors, warnings)
        ok_r = _check_primer('Reverse', rp, row_label, errors, warnings)

        exp_raw = _s(r.get('expected_size'))
        exp = None
        if exp_raw:
            try:
                exp = int(float(exp_raw))
                if exp <= 0:
                    raise ValueError
            except ValueError:
                errors.append(f"{row_label}: expected size must be a positive number.")

        cid = _s(r.get('id'))
        if not cid or cid in seen_ids:
            while f"C{next_n}" in used_ids or f"C{next_n}" in seen_ids:
                next_n += 1
            cid = f"C{next_n}"
        seen_ids.add(cid)

        rec = {'id': cid, 'name': name, 'target': target,
               'fp_sequence': fp, 'rp_sequence': rp,
               'expected_size': exp, 'notes': _s(r.get('notes'))}
        if ok_f:
            rec.update(fp_length=len(fp), fp_tm=_tm(fp), fp_gc=_gc(fp))
        if ok_r:
            rec.update(rp_length=len(rp), rp_tm=_tm(rp), rp_gc=_gc(rp))
        if ok_f and ok_r and abs(rec['fp_tm'] - rec['rp_tm']) > TM_DIFF_WARN:
            warnings.append(f"{row_label}: FP/RP Tm differ by "
                            f"{abs(rec['fp_tm'] - rec['rp_tm']):.1f}°C (> {TM_DIFF_WARN}°C).")
        controls.append(rec)

    names = [c['name'].lower() for c in controls if c['name']]
    for n in sorted({n for n in names if names.count(n) > 1}):
        errors.append(f"Duplicate control name: '{n}'.")
    return controls, errors, warnings


def controls_to_editor_rows(controls):
    return [{k: c.get(k) for k in EDITOR_COLS} for c in controls]


def rows_from_upload(file_bytes, filename):
    """Parse a CSV/XLSX upload into editor-style row dicts (header names are
    matched case-insensitively against common aliases)."""
    import pandas as pd
    fn = filename.lower()
    if fn.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)
    else:
        df = pd.read_csv(io.BytesIO(file_bytes), dtype=str, sep=None,
                         engine='python', encoding_errors='ignore')
    rename = {}
    for col in df.columns:
        key = _ALIASES.get(str(col).strip().lower())
        if key and key not in rename.values():
            rename[col] = key
    df = df.rename(columns=rename)
    missing = [c for c in ('name', 'fp_sequence', 'rp_sequence') if c not in df.columns]
    if missing:
        raise ValueError(
            "Missing column(s): " + ", ".join(missing) +
            ". Expected headers such as: Name, Target, Forward, Reverse, "
            "Expected size, Notes.")
    return [{k: r.get(k) for k in EDITOR_COLS if k != 'id'}
            for r in df.to_dict('records')]
