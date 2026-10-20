"""
Shared coordinate helpers for the circular vector.

Amplicons are stored in "extended" (monotonic) coordinates: amplicon_start is
a real 0-based position (< seq_len) but amplicon_end may exceed seq_len when
the amplicon reads through the plasmid origin. Anything that draws or annotates
the real sequence (GenBank export, Word/PDF sequence appendix) must convert
through real_spans() first.
"""

_COMP = str.maketrans("ACGTacgtNnRYKMSWBDHVrykmswbdhv",
                      "TGCAtgcaNnYRMKSWVHDByrmkswvhdb")


def revcomp(seq):
    return seq.translate(_COMP)[::-1]


def real_spans(start, end, seq_len):
    """
    Convert an extended span into one or two REAL 0-based half-open spans.
      - entirely before the origin         -> [(start, end)]
      - straddles the origin               -> [(start, seq_len), (0, end-seq_len)]
      - entirely past the origin           -> [(start-seq_len, end-seq_len)]
    """
    if start >= seq_len:
        return [(start - seq_len, end - seq_len)]
    if end <= seq_len:
        return [(start, end)]
    return [(start, seq_len), (0, end - seq_len)]


def primer_footprints(p, seq_len):
    """
    Real top-strand footprints of a primer pair's FP and RP.

    Returns a list of up to two dicts:
      {'kind': 'FP'|'RP', 'amplicon_num', 'name', 'sequence' (5'->3' as
       ordered), 'spans': [(s, e), ...] real 0-based half-open, 'strand': +1/-1,
       'length', 'tm', 'gc'}
    Failed placeholders yield an empty list.
    """
    if p.get('fp_sequence') == 'DESIGN_FAILED':
        return []
    name = p.get('amplicon_name') or f"Amplicon_{p['amplicon_num']}"
    start = max(0, p['amplicon_start'])
    end = max(start + 1, p['amplicon_end'])
    out = []

    fp_len = p.get('fp_length', 0)
    if fp_len:
        out.append({
            'kind': 'FP', 'amplicon_num': p['amplicon_num'], 'name': f"{name}_FP",
            'sequence': p['fp_sequence'], 'strand': 1, 'length': fp_len,
            'tm': p.get('fp_tm', 0), 'gc': p.get('fp_gc', 0),
            'spans': real_spans(start, start + fp_len, seq_len),
        })
    rp_len = p.get('rp_length', 0)
    if rp_len:
        out.append({
            'kind': 'RP', 'amplicon_num': p['amplicon_num'], 'name': f"{name}_RP",
            'sequence': p['rp_sequence'], 'strand': -1, 'length': rp_len,
            'tm': p.get('rp_tm', 0), 'gc': p.get('rp_gc', 0),
            'spans': real_spans(end - rp_len, end, seq_len),
        })
    return out
