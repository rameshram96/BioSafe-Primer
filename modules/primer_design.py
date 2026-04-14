import primer3

DEFAULT_PARAMS = {
    'PRIMER_OPT_SIZE': 20,
    'PRIMER_MIN_SIZE': 18,
    'PRIMER_MAX_SIZE': 25,
    'PRIMER_OPT_TM': 60.0,
    'PRIMER_MIN_TM': 55.0,
    'PRIMER_MAX_TM': 65.0,
    'PRIMER_MIN_GC': 30.0,
    'PRIMER_MAX_GC': 70.0,
    'PRIMER_MAX_POLY_X': 4,
    'PRIMER_SALT_MONOVALENT': 50.0,
    'PRIMER_DNA_CONC': 50.0,
    'PRIMER_MAX_NS_ACCEPTED': 0,
    'PRIMER_MAX_SELF_ANY': 12,
    'PRIMER_MAX_SELF_END': 8,
    'PRIMER_PAIR_MAX_COMPL_ANY': 12,
    'PRIMER_PAIR_MAX_COMPL_END': 8,
    'PRIMER_NUM_RETURN': 5,
}

FP_ZONE_WIDTH  = 60   # FP must bind within first 60 bp of segment
RP_ZONE_WIDTH  = 80   # RP must bind within last 80 bp of segment
MIN_AMPLICON   = 150  # minimum allowed amplicon size (bp)
MAX_AMPLICON   = 500  # maximum allowed amplicon size (bp)
MIN_PRIMER_LEN = 18
MAX_PRIMER_LEN = 25


def gc_percent(seq):
    seq = seq.upper()
    gc = seq.count('G') + seq.count('C')
    return round((gc / len(seq)) * 100, 1) if seq else 0


def _call_primer3(seg_seq, product_min, product_max, params,
                  fp_zone=None, rp_zone=None):
    product_min = max(product_min, 1)
    product_max = max(product_min + 1, product_max)
    seq_args = {'SEQUENCE_ID': 'amp', 'SEQUENCE_TEMPLATE': seg_seq}
    if fp_zone and rp_zone:
        fp_s, fp_l, rp_s, rp_l = fp_zone[0], fp_zone[1], rp_zone[0], rp_zone[1]
        if fp_l >= 1 and rp_l >= 1:
            seq_args['SEQUENCE_PRIMER_PAIR_OK_REGION_LIST'] = [
                [fp_s, fp_l, rp_s, rp_l]
            ]
    global_args = params.copy()
    global_args['PRIMER_PRODUCT_SIZE_RANGE'] = [[product_min, product_max]]
    try:
        r = primer3.design_primers(seq_args, global_args)
        if r.get('PRIMER_PAIR_NUM_RETURNED', 0) > 0:
            return r
    except Exception:
        pass
    # Fallback: no zone restriction
    seq_args_fb = {'SEQUENCE_ID': 'amp_fb', 'SEQUENCE_TEMPLATE': seg_seq}
    global_args_fb = params.copy()
    global_args_fb['PRIMER_PRODUCT_SIZE_RANGE'] = [[product_min, product_max]]
    try:
        return primer3.design_primers(seq_args_fb, global_args_fb)
    except Exception:
        return None


def _design_segment(sequence, seg_start, seg_end, params, force_first=False):
    seg_seq = sequence[seg_start:seg_end]
    seg_len = len(seg_seq)
    if seg_len < MIN_AMPLICON:
        return None, seg_start

    prod_min = MIN_AMPLICON
    prod_max = min(MAX_AMPLICON, seg_len)
    if prod_min >= prod_max:
        prod_max = min(seg_len, prod_min + 50)

    # Rule 1: force Amplicon 1 FP to position 0
    if force_first:
        try:
            r = primer3.design_primers(
                {'SEQUENCE_ID': 'amp_first', 'SEQUENCE_TEMPLATE': seg_seq,
                 'SEQUENCE_FORCE_LEFT_START': 0},
                {**params, 'PRIMER_PRODUCT_SIZE_RANGE': [[prod_min, prod_max]]}
            )
            if r.get('PRIMER_PAIR_NUM_RETURNED', 0) > 0:
                return r, seg_start
        except Exception:
            pass

    if seg_len >= 150:
        rp_zone_start = max(FP_ZONE_WIDTH + 100, seg_len - RP_ZONE_WIDTH)
        rp_zone_len   = max(1, seg_len - rp_zone_start)
        r = _call_primer3(seg_seq, prod_min, prod_max, params,
                          fp_zone=(0, FP_ZONE_WIDTH),
                          rp_zone=(rp_zone_start, rp_zone_len))
    else:
        r = _call_primer3(seg_seq, prod_min, prod_max, params)

    return r, seg_start


def _extract_best(result, offset, amplicon_num, version, max_amplicon=MAX_AMPLICON):
    """
    Extract best primer pair. Pulls all Primer3 output fields including:
    hairpin Tm, 3' end stability, penalty scores.
    """
    if not result:
        return None
    for i in range(result.get('PRIMER_PAIR_NUM_RETURNED', 0)):
        product = result.get(f'PRIMER_PAIR_{i}_PRODUCT_SIZE', 0)
        if product > max_amplicon or product < MIN_AMPLICON:
            continue
        fp_seq  = result.get(f'PRIMER_LEFT_{i}_SEQUENCE', '')
        rp_seq  = result.get(f'PRIMER_RIGHT_{i}_SEQUENCE', '')
        fp_pos  = result.get(f'PRIMER_LEFT_{i}',  [0, 0])
        rp_pos  = result.get(f'PRIMER_RIGHT_{i}', [0, 0])

        # Validate primer lengths
        if not (MIN_PRIMER_LEN <= len(fp_seq) <= MAX_PRIMER_LEN):
            continue
        if not (MIN_PRIMER_LEN <= len(rp_seq) <= MAX_PRIMER_LEN):
            continue

        return {
            'amplicon_num':       amplicon_num,
            # Sequences
            'fp_sequence':        fp_seq,
            'rp_sequence':        rp_seq,
            # Lengths
            'fp_length':          len(fp_seq),
            'rp_length':          len(rp_seq),
            # Tm
            'fp_tm':              round(result.get(f'PRIMER_LEFT_{i}_TM', 0), 2),
            'rp_tm':              round(result.get(f'PRIMER_RIGHT_{i}_TM', 0), 2),
            # GC% (from Primer3 directly)
            'fp_gc':              round(result.get(f'PRIMER_LEFT_{i}_GC_PERCENT', 0), 1),
            'rp_gc':              round(result.get(f'PRIMER_RIGHT_{i}_GC_PERCENT', 0), 1),
            # Hairpin Tm
            'fp_hairpin_tm':      round(result.get(f'PRIMER_LEFT_{i}_HAIRPIN_TH', 0), 2),
            'rp_hairpin_tm':      round(result.get(f'PRIMER_RIGHT_{i}_HAIRPIN_TH', 0), 2),
            # 3' End Stability (deltaG of last 5 bases)
            'fp_end_stability':   round(result.get(f'PRIMER_LEFT_{i}_END_STABILITY', 0), 2),
            'rp_end_stability':   round(result.get(f'PRIMER_RIGHT_{i}_END_STABILITY', 0), 2),
            # Penalty scores (lower = better)
            'fp_penalty':         round(result.get(f'PRIMER_LEFT_{i}_PENALTY', 0), 4),
            'rp_penalty':         round(result.get(f'PRIMER_RIGHT_{i}_PENALTY', 0), 4),
            'pair_penalty':       round(result.get(f'PRIMER_PAIR_{i}_PENALTY', 0), 4),
            # Self-complementarity
            'fp_self_any':        round(result.get(f'PRIMER_LEFT_{i}_SELF_ANY_TH', 0), 2),
            'fp_self_end':        round(result.get(f'PRIMER_LEFT_{i}_SELF_END_TH', 0), 2),
            'rp_self_any':        round(result.get(f'PRIMER_RIGHT_{i}_SELF_ANY_TH', 0), 2),
            'rp_self_end':        round(result.get(f'PRIMER_RIGHT_{i}_SELF_END_TH', 0), 2),
            # Amplicon position
            'amplicon_start':     offset + fp_pos[0],
            'amplicon_end':       offset + rp_pos[0] + 1,
            'amplicon_length':    product,
            # Overlap (filled after all amplicons designed)
            'overlap_next':       0,
            'overlap_prev':       0,
            # Metadata
            'amplicon_name':      f'Amplicon_{amplicon_num}',
            'version':            version,
            'status':             'Pending',
            'violations':         [],
        }
    return None


def _failed_placeholder(amplicon_num, seg_start, seg_end):
    return {
        'amplicon_num':    amplicon_num,
        'fp_sequence':     'DESIGN_FAILED', 'rp_sequence':     'DESIGN_FAILED',
        'fp_length': 0,    'rp_length': 0,
        'fp_tm': 0,        'rp_tm': 0,
        'fp_gc': 0,        'rp_gc': 0,
        'fp_hairpin_tm': 0, 'rp_hairpin_tm': 0,
        'fp_end_stability': 0, 'rp_end_stability': 0,
        'fp_penalty': 0,   'rp_penalty': 0,   'pair_penalty': 0,
        'fp_self_any': 0,  'fp_self_end': 0,
        'rp_self_any': 0,  'rp_self_end': 0,
        'amplicon_start':  seg_start, 'amplicon_end': seg_end,
        'amplicon_length': seg_end - seg_start,
        'overlap_next': 0, 'overlap_prev': 0,
        'amplicon_name':   f'Amplicon_{amplicon_num}',
        'version': 1,      'status': 'Design Failed',
        'violations': [f'Amplicon {amplicon_num}: Primer3 design failed'],
    }


def validate_primers(all_primers, min_overlap=50, max_amplicon=MAX_AMPLICON):
    violations = []
    valid = [p for p in all_primers if p['fp_sequence'] != 'DESIGN_FAILED']
    if not valid:
        return ['No valid primers designed.']

    if valid[0]['amplicon_start'] > 1:
        violations.append(
            f"Rule 1 ❌ Amplicon 1 FP starts at position {valid[0]['amplicon_start']} "
            f"(must start at base 1)"
        )
    for i, p in enumerate(valid):
        if p['amplicon_length'] > max_amplicon:
            violations.append(
                f"Rule 2 ❌ Amplicon {p['amplicon_num']}: {p['amplicon_length']} bp "
                f"exceeds maximum {max_amplicon} bp"
            )
        if p['amplicon_length'] < MIN_AMPLICON:
            violations.append(
                f"Rule 2b ❌ Amplicon {p['amplicon_num']}: {p['amplicon_length']} bp "
                f"below minimum {MIN_AMPLICON} bp"
            )
        if i < len(valid) - 1:
            nxt = valid[i + 1]
            overlap = p['amplicon_end'] - nxt['amplicon_start']
            if overlap < 0:
                violations.append(
                    f"Rule 4 ❌ Gap of {abs(overlap)} bp between "
                    f"Amplicon {p['amplicon_num']} and {nxt['amplicon_num']}"
                )
            elif overlap < min_overlap:
                violations.append(
                    f"Rule 3 ❌ Amplicon {p['amplicon_num']}–{nxt['amplicon_num']}: "
                    f"overlap = {overlap} bp (minimum {min_overlap} bp required)"
                )
    return violations


def design_all_primers(sequence, max_amplicon=MAX_AMPLICON,
                        min_overlap=50, params=None):
    """
    Design overlapping primers covering the full vector.
    Rules enforced:
      1. Amplicon 1 FP starts at base 1
      2. Every amplicon 150–500 bp
      3. Consecutive overlap >= 50 bp
      4. Full vector coverage — no gaps
      5. Short terminal segments (<150 bp) merged into previous amplicon
    """
    if params is None:
        params = DEFAULT_PARAMS.copy()

    seq_len      = len(sequence)
    all_primers  = []
    amplicon_num = 1
    seg_start    = 0
    MAX_RETRIES  = 5

    while seg_start < seq_len:
        seg_end     = min(seg_start + max_amplicon, seq_len)
        force_first = (amplicon_num == 1)

        # Check if remaining sequence is too short for a new amplicon
        remaining = seq_len - seg_start
        if remaining < MIN_AMPLICON and all_primers:
            # Merge: extend RP of previous amplicon to cover end of vector
            prev = all_primers[-1]
            if prev['fp_sequence'] != 'DESIGN_FAILED':
                # Redesign previous segment extended to end of vector
                prev_seg_start = max(0, prev['amplicon_start'])
                r, offset = _design_segment(
                    sequence, prev_seg_start, seq_len, params
                )
                merged = _extract_best(r, offset, prev['amplicon_num'],
                                        prev['version'], max_amplicon)
                if merged:
                    merged['overlap_prev'] = prev.get('overlap_prev', 0)
                    merged['status']       = prev.get('status', 'Pending')
                    all_primers[-1] = merged
            break

        primer = None
        retry_seg_start = seg_start

        for attempt in range(MAX_RETRIES):
            seg_end  = min(retry_seg_start + max_amplicon, seq_len)
            r, offset = _design_segment(
                sequence, retry_seg_start, seg_end, params,
                force_first=force_first
            )
            candidate = _extract_best(r, offset, amplicon_num,
                                       version=1, max_amplicon=max_amplicon)
            if candidate is None:
                break

            # Check overlap with previous amplicon
            if all_primers and all_primers[-1]['fp_sequence'] != 'DESIGN_FAILED':
                prev_amp_end   = all_primers[-1]['amplicon_end']
                actual_overlap = prev_amp_end - candidate['amplicon_start']
                if actual_overlap < min_overlap:
                    pull_back = (min_overlap - actual_overlap) + 10
                    retry_seg_start = max(0, retry_seg_start - pull_back)
                    prev_start = all_primers[-1]['amplicon_start'] if all_primers else 0
                    if retry_seg_start <= prev_start:
                        break
                    continue

            primer = candidate
            break

        if primer is None:
            primer = _failed_placeholder(amplicon_num, seg_start,
                                          min(seg_start + max_amplicon, seq_len))
            all_primers.append(primer)
            amp_end = min(seg_start + max_amplicon, seq_len)
        else:
            all_primers.append(primer)
            amp_end = primer['amplicon_end']

        if amp_end >= seq_len:
            break

        next_seg_start = amp_end - min_overlap - FP_ZONE_WIDTH
        if next_seg_start <= seg_start:
            next_seg_start = seg_start + max(1, max_amplicon // 2)
        if next_seg_start >= seq_len:
            break

        seg_start    = next_seg_start
        amplicon_num += 1

    # Recalculate overlap_prev / overlap_next from actual positions
    if all_primers:
        all_primers[0]['overlap_prev']  = None
        all_primers[-1]['overlap_next'] = None
    for i in range(len(all_primers) - 1):
        curr = all_primers[i]
        nxt  = all_primers[i + 1]
        if (curr['fp_sequence'] != 'DESIGN_FAILED' and
                nxt['fp_sequence'] != 'DESIGN_FAILED'):
            ov = curr['amplicon_end'] - nxt['amplicon_start']
            curr['overlap_next'] = ov
            nxt['overlap_prev']  = ov

    # Hard enforcement: mark overlap violations
    for i in range(len(all_primers) - 1):
        curr = all_primers[i]
        nxt  = all_primers[i + 1]
        if (curr['fp_sequence'] != 'DESIGN_FAILED' and
                nxt['fp_sequence'] != 'DESIGN_FAILED'):
            if (curr.get('overlap_next') or 0) < min_overlap:
                curr['status'] = 'Overlap Violation'
                curr['violations'] = curr.get('violations', []) + [
                    f"Rule 3 ❌ Downstream overlap = {curr['overlap_next']} bp "
                    f"(minimum {min_overlap} bp) — redesign required"
                ]

    violations = validate_primers(all_primers, min_overlap, max_amplicon)
    for p in all_primers:
        p['violations'] = p.get('violations', []) + [
            v for v in violations if f"Amplicon {p['amplicon_num']}" in v
        ]

    return all_primers, violations


# Failure type → recommended extension strategy
FAILURE_RECOMMENDATIONS = {
    'No band':              {'ext_left': 100, 'ext_right': 100,
                             'note': 'Extend both sides — gives Primer3 maximum flexibility'},
    'Multiple bands':       {'ext_left': 50,  'ext_right': 150,
                             'note': 'Extend right — move RP into more unique downstream sequence'},
    'Weak band':            {'ext_left': 100, 'ext_right': 100,
                             'note': 'Extend both — find primers with better thermodynamic properties'},
    'Wrong band size':      {'ext_left': 50,  'ext_right': 50,
                             'note': 'Small extension — reposition within same region'},
    'Primer dimer':         {'ext_left': 150, 'ext_right': 150,
                             'note': 'Large extension — force completely new binding positions'},
    'Overlap violation':    {'ext_left': 150, 'ext_right': 0,
                             'note': 'Extend left only — pulls FP upstream to increase upstream overlap'},
    'Other':                {'ext_left': 100, 'ext_right': 100,
                             'note': 'Default extension — adjust manually if needed'},
}

MAX_REDESIGN_VERSIONS = 3


def get_redesign_recommendation(failure_type):
    """Return recommended extension values and guidance note for a failure type."""
    return FAILURE_RECOMMENDATIONS.get(failure_type,
                                        FAILURE_RECOMMENDATIONS['Other'])


def redesign_primers(sequence, seg_start, seg_end, amplicon_num,
                     ext_left=100, ext_right=100, old_version=1,
                     params=None, prev_amp_end=None, next_amp_start=None):
    """
    Redesign primers for a failed amplicon.

    Extension rules:
      - ext_left: pulls segment start leftward — gives Primer3 more upstream
        sequence, helping FP land further left → increases upstream overlap
      - ext_right: pushes segment end rightward — gives Primer3 more downstream
        sequence for RP placement → but DOES NOT directly reduce downstream
        overlap because next segment start is recalculated from actual amp_end

    Overlap validation:
      - After design, upstream overlap = prev_amp_end - new_amp_start (must ≥ 50)
      - After design, downstream overlap = new_amp_end - next_amp_start (must ≥ 50)
      - Both checked and returned with the result for preview before saving

    Max versions: 3 — after v3, returns None with a message.
    """
    if old_version >= MAX_REDESIGN_VERSIONS:
        return None, f"Maximum redesign attempts ({MAX_REDESIGN_VERSIONS}) reached for Amplicon {amplicon_num}"

    if params is None:
        params = DEFAULT_PARAMS.copy()

    seq_len      = len(sequence)
    actual_start = max(0, seg_start - ext_left)
    actual_end   = min(seq_len, seg_end + ext_right)

    # Enforce max segment size
    if actual_end - actual_start > MAX_AMPLICON:
        actual_end = actual_start + MAX_AMPLICON

    r, offset = _design_segment(sequence, actual_start, actual_end, params)
    primer    = _extract_best(r, offset, amplicon_num,
                               version=old_version + 1,
                               max_amplicon=MAX_AMPLICON)

    if primer is None:
        return None, "Primer3 could not design a valid pair with current extension values"

    # Calculate actual overlaps with neighbours
    if prev_amp_end is not None:
        primer['overlap_prev'] = prev_amp_end - primer['amplicon_start']
    else:
        primer['overlap_prev'] = None

    if next_amp_start is not None:
        primer['overlap_next'] = primer['amplicon_end'] - next_amp_start
    else:
        primer['overlap_next'] = None

    # Validate overlaps
    violations = []
    if primer['overlap_prev'] is not None and primer['overlap_prev'] < 50:
        violations.append(
            f"Upstream overlap = {primer['overlap_prev']} bp (< 50 bp minimum). "
            f"Try increasing upstream extension."
        )
    if primer['overlap_next'] is not None and primer['overlap_next'] < 50:
        violations.append(
            f"Downstream overlap = {primer['overlap_next']} bp (< 50 bp minimum). "
            f"Downstream overlap is controlled by the NEXT amplicon's FP position, "
            f"not by right extension of this amplicon. "
            f"If this persists after accept, mark the next amplicon for redesign."
        )

    primer['redesign_violations'] = violations
    primer['redesign_ok']         = len(violations) == 0

    return primer, None