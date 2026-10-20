"""
Pure-Python helpers shared by the Word and PDF sequence appendices
(no python-docx / reportlab imports here).
"""
from .coords import revcomp

# Text colours (hex, no '#') for primer footprints in the sequence appendix
FP_COLOR, RP_COLOR, BOTH_COLOR = '0D47A1', 'D84315', '6A1B9A'   # blue / deep orange / purple
PER_LINE, BLOCK = 100, 10


def build_cover(seq_len, footprints):
    """cover[pos] -> set of (footprint_index, span_index) keys."""
    cover = [set() for _ in range(seq_len)]
    for i, f in enumerate(footprints):
        for j, (s, e) in enumerate(f['spans']):
            for pos in range(max(0, s), min(seq_len, e)):
                cover[pos].add((i, j))
    return cover


def color_for(keys, footprints):
    """Text colour (hex, no '#') for a set of covering keys, or None."""
    if not keys:
        return None
    kinds = {footprints[i]['kind'] for i, _ in keys}
    if len(kinds) > 1:
        return BOTH_COLOR
    return FP_COLOR if 'FP' in kinds else RP_COLOR


def verify_footprint(f, sequence):
    """True if the primer matches the vector at its recorded position."""
    top = ''.join(sequence[s:e] for s, e in f['spans']).upper()
    ordered = f['sequence'].upper()
    return top == ordered if f['kind'] == 'FP' else revcomp(top) == ordered


def pos_text(f):
    return ', '.join(f"{s + 1}-{e}" for s, e in f['spans'])


def tag_for(f):
    """Short marker for the PDF sequence, e.g. '3F' / '3R'."""
    return f"{f['amplicon_num']}{'F' if f['kind'] == 'FP' else 'R'}"
