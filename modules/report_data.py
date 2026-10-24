"""
Single source of truth for report content. Both the Word and PDF renderers
consume build_report_data() so the two outputs cannot drift apart.
"""
import hashlib
from datetime import datetime

from .project_file import get_best_primers
from .coords import primer_footprints
from .primer_design import MIN_AMPLICON, MAX_AMPLICON, MIN_PRIMER_LEN, MAX_PRIMER_LEN

DEFAULT_DESIGN_PARAMS = {
    'max_amplicon': MAX_AMPLICON, 'min_amplicon': MIN_AMPLICON,
    'min_overlap': 50,
    'primer_len_min': MIN_PRIMER_LEN, 'primer_len_max': MAX_PRIMER_LEN,
    'opt_tm': None, 'min_tm': None, 'max_tm': None,
    'min_gc': 40.0, 'max_gc': 60.0,
    'salt_monovalent': 50.0, 'dna_conc': 50.0,
}

DEFAULT_OPTIONS = {
    'include_sequence': True, 'include_gels': True,
    'include_history': True, 'include_controls': True,
    'include_comments': True,           # Word only
    'author': '', 'lab': '', 'report_date': None,
}


def sequence_fingerprints(sequence):
    b = sequence.encode('ascii', errors='ignore')
    return {'md5': hashlib.md5(b).hexdigest(),
            'sha256': hashlib.sha256(b).hexdigest()}


def check_rules(best, seq_len, params):
    """
    Rule verification summary (Rules 1-5) on the current best primer set.
    Returns list of {'rule', 'text', 'status': 'Pass'|'Fail'|'N/A', 'detail'}.
    """
    mn_ov = params.get('min_overlap', 50)
    mx_amp = params.get('max_amplicon', MAX_AMPLICON)
    valid = [p for p in best if p.get('fp_sequence') != 'DESIGN_FAILED']
    failed = [p for p in best if p.get('fp_sequence') == 'DESIGN_FAILED']
    res = []

    def add(rule, text, ok, detail=''):
        res.append({'rule': rule, 'text': text,
                    'status': 'N/A' if ok is None else ('Pass' if ok else 'Fail'),
                    'detail': detail})

    if not valid:
        add('All', 'Primers designed', False, 'No valid primers.')
        return res

    add('1', 'Amplicon 1 forward primer starts at base 1',
        valid[0]['amplicon_start'] <= 1,
        f"Starts at position {valid[0]['amplicon_start'] + 1}.")

    bad = [f"A{p['amplicon_num']} ({p['amplicon_length']} bp)" for p in valid
           if not (MIN_AMPLICON <= p['amplicon_length'] <= mx_amp)]
    add('2', f'Every amplicon {MIN_AMPLICON}-{mx_amp} bp', not bad and not failed,
        ('Out of range: ' + ', '.join(bad) + '. ' if bad else '') +
        (f"{len(failed)} amplicon(s) failed design." if failed else ''))

    gaps, lows = [], []
    for a, b in zip(valid, valid[1:]):
        ov = a['amplicon_end'] - b['amplicon_start']
        if ov < 0:
            gaps.append(f"A{a['amplicon_num']}-A{b['amplicon_num']} ({-ov} bp gap)")
        elif ov < mn_ov:
            lows.append(f"A{a['amplicon_num']}-A{b['amplicon_num']} ({ov} bp)")
    add('3', f'Consecutive overlap >= {mn_ov} bp', not lows and not gaps,
        'Below minimum: ' + ', '.join(lows) if lows else '')
    add('4', 'Full vector coverage, no gaps', not gaps and not failed,
        'Gaps: ' + ', '.join(gaps) if gaps else '')

    last, first = valid[-1], valid[0]
    if last is first:
        add('5', 'Circular closure (last <-> Amplicon 1)', False,
            'A single amplicon cannot overlap itself across the origin.')
    else:
        co = last.get('circular_overlap', 0)
        add('5', f'Circular closure: last amplicon overlaps Amplicon 1 by >= {mn_ov} bp',
            bool(last.get('wraps_origin')) and co >= mn_ov,
            f"Amplicon {last['amplicon_num']} overlaps Amplicon {first['amplicon_num']} "
            f"by {co} bp across the origin.")
    return res


def _resolve_controls(run, controls_by_id):
    out = []
    for cid in run.get('control_ids') or []:
        if cid in controls_by_id:
            out.append(controls_by_id[cid])
    if not out:  # control was later deleted: fall back to the name snapshot
        out = [{'id': None, 'name': n} for n in run.get('control_names') or []]
    return out


def build_report_data(project, seq_info=None, options=None):
    opts = {**DEFAULT_OPTIONS, **(options or {})}
    params = {**DEFAULT_DESIGN_PARAMS, **(project.get('design_params') or {})}
    sequence = project.get('vector_sequence', '')
    seq_len = len(sequence)
    best = get_best_primers(project)
    controls = project.get('control_primers') or []
    by_id = {c['id']: c for c in controls}

    runs = []
    for r in project.get('pcr_runs', []):
        rr = dict(r)
        rr['controls'] = _resolve_controls(r, by_id)
        runs.append(rr)

    footprints = []
    for p in best:
        footprints.extend(primer_footprints(p, seq_len))

    return {
        'meta': {
            'project_name': project.get('project_name', ''),
            'vector_name': project.get('vector_name', ''),
            'vector_length': project.get('vector_length', seq_len),
            'created_at': project.get('created_at'),
            'report_date': opts['report_date'] or datetime.now().strftime('%Y-%m-%d'),
            'author': opts['author'], 'lab': opts['lab'],
            'format_version': project.get('format_version'),
            'fingerprints': sequence_fingerprints(sequence),
        },
        'design_params': params,
        'params_recorded': bool(project.get('design_params')),
        'rules': check_rules(best, seq_len, params),
        'primers': best,
        'all_primers': project.get('primers', []),
        'controls': controls,
        'runs': runs,
        'history': project.get('redesign_history', []),
        'sequence': sequence,
        'footprints': footprints,
        'seq_info': seq_info,
        'options': opts,
    }
