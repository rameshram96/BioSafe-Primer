"""
genbank_export.py — BioSafe Primer
Builds a GenBank (.gb) file annotated with amplicon and primer features,
readable in SnapGene, ApE, Benchling, etc.

Feature layout (amplicon/primer annotations ONLY — no source feature and
no features carried over from the originally uploaded file):
  misc_feature  — one per amplicon, colored by status
  primer_bind   — one per FP (forward strand) and RP (reverse strand)

CIRCULAR-ORIGIN FIX: primer_design.py stores the origin-spanning ("wrap")
amplicon using "extended" (monotonic) coordinates — amplicon_end can be
> seq_len so that amplicon_length == amplicon_end - amplicon_start stays
simple everywhere. Any code that writes real sequence coordinates (this
module) MUST convert those extended coordinates back to real circular
coordinates via primer_design.split_origin_span() before building a
Bio.SeqFeature location. Previously this module didn't do that — it just
clipped the extended end down to seq_len, which silently:
  - truncated the amplicon's misc_feature so it no longer visibly spanned
    the origin, and
  - placed the reverse primer's primer_bind feature at the physical TAIL
    of the vector sequence (seq_len - rp_length .. seq_len) instead of
    where it actually binds, near the origin (0 .. circular_overlap) —
    i.e. at a position where that primer's sequence isn't actually
    present. This module now builds a two-segment CompoundLocation
    (join-style) for any amplicon/FP/RP feature that crosses the origin.
"""
import io
import re
from datetime import datetime

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.SeqFeature import SeqFeature, FeatureLocation, CompoundLocation
from Bio import SeqIO

from .primer_design import split_origin_span

AMPLICON_STATUS_COLORS = {
    'Pending':           '#e65100',
    'Success':           '#2e7d32',
    'Done':              '#2e7d32',
    'Failed':            '#b71c1c',
    'Overlap Violation': '#6a1b9a',
    'Design Failed':     '#37474f',
    'Redesigned':        '#1565c0',
}
FP_COLOR = '#0072B2'
RP_COLOR = '#D55E00'


def _sanitize_locus_name(name):
    """GenBank LOCUS names must be short and free of spaces/odd characters."""
    name = re.sub(r'[^A-Za-z0-9_]', '_', name or 'vector')
    name = name.strip('_') or 'vector'
    return name[:15]


def _amp_label(p):
    return p.get('amplicon_name') or f"Amplicon_{p['amplicon_num']}"


def _build_location(start, end, seq_len, strand):
    """
    Build a Bio.SeqFeature location for a (possibly origin-spanning) span.

    `start`/`end` may be given in "extended" coordinates (end > seq_len
    for a span that wraps past the origin) — this always converts via
    split_origin_span() first, so callers never need to pre-clip.

    Returns a single FeatureLocation for a normal (non-wrapping) span, or
    a CompoundLocation (join of two segments, in increasing genomic
    order) when the span crosses the origin — the standard way to
    represent an origin-spanning feature on a circular sequence.
    """
    spans = split_origin_span(start, end, seq_len)
    parts = [FeatureLocation(s, e, strand=strand) for s, e in spans if e > s]
    if not parts:
        # Degenerate/zero-length — fall back to a minimal 1 bp feature
        # rather than raising, so one bad primer doesn't break the export.
        safe_start = max(0, min(start, seq_len - 1))
        return FeatureLocation(safe_start, safe_start + 1, strand=strand)
    if len(parts) == 1:
        return parts[0]
    return CompoundLocation(parts, operator='join')


def build_annotated_genbank(seq_info, primers, project_name, circular=True):
    """
    Build a GenBank file (as a string) annotating ONLY amplicons and
    primers on top of the vector sequence (no source feature, no
    original/carried-over features).

    seq_info: dict with 'name', 'sequence', 'features' (as produced by
              sequence_parser.parse_sequence or reconstructed from a
              loaded .bsp project)
    primers:  list of primer dicts — pass the DEDUPED/"best" list
              (e.g. project_file.get_best_primers(proj)), not the full
              version history.
    """
    sequence = seq_info['sequence']
    seq_len  = len(sequence)

    record = SeqRecord(Seq(sequence))
    record.id   = _sanitize_locus_name(seq_info.get('name', 'vector'))
    record.name = record.id
    record.description = (
        f"{project_name} — annotated with PCR primers and amplicons "
        f"(BioSafe Primer, ICAR-IARI)"
    )
    record.annotations['molecule_type'] = 'DNA'
    record.annotations['topology']      = 'circular' if circular else 'linear'
    record.annotations['organism']      = 'synthetic construct'
    record.annotations['source']        = 'synthetic construct'
    record.annotations['date']          = datetime.now().strftime('%d-%b-%Y').upper()

    features = []

    # NOTE: by design this export contains ONLY amplicon and primer
    # annotations — no whole-sequence 'source' feature and no features
    # carried over from the originally uploaded file. Amplicon/primer
    # features still carry their full notes (Tm, GC%, penalty, etc.).

    # Amplicons + primers
    for p in primers:
        if p.get('fp_sequence') == 'DESIGN_FAILED':
            continue  # nothing real to annotate

        name    = _amp_label(p)
        status  = p.get('status', 'Pending')
        color   = AMPLICON_STATUS_COLORS.get(status, '#78909c')
        wraps   = bool(p.get('wraps_origin'))

        # Amplicon extent, in EXTENDED coordinates as stored by
        # primer_design.py (amplicon_end may exceed seq_len for the
        # wrap amplicon) — _build_location() converts these to real
        # circular coordinates (splitting across the origin if needed).
        a_start_ext = max(0, p['amplicon_start'])
        a_end_ext   = max(a_start_ext + 1, p['amplicon_end'])

        prev_ov = p.get('overlap_prev')
        next_ov = p.get('overlap_next')
        amp_note = (
            f"Status: {status}; Version: {p.get('version', 1)}; "
            f"Length: {p.get('amplicon_length', a_end_ext - a_start_ext)} bp; "
            f"Overlap upstream: {prev_ov if prev_ov is not None else 'N/A'} bp; "
            f"Overlap downstream: {next_ov if next_ov is not None else 'N/A'} bp; "
            f"Pair penalty: {p.get('pair_penalty', 0)}"
            + ("; spans plasmid origin" if wraps else "")
        )
        features.append(SeqFeature(
            _build_location(a_start_ext, a_end_ext, seq_len, strand=1),
            type='misc_feature',
            qualifiers={
                'label':             [name],
                'note':              [amp_note],
                'ApEinfo_fwdcolor':  [color],
                'ApEinfo_revcolor':  [color],
            }
        ))

        # Forward primer — binds top strand, at amplicon start.
        # The FP always sits on the "tail" side of a wrap amplicon (i.e.
        # at a real, non-extended coordinate < seq_len), so this normally
        # never needs splitting — but _build_location() handles it safely
        # either way.
        fp_len      = p.get('fp_length', 0)
        fp_start    = a_start_ext
        fp_end_ext  = fp_start + fp_len
        if fp_end_ext > fp_start:
            features.append(SeqFeature(
                _build_location(fp_start, fp_end_ext, seq_len, strand=1),
                type='primer_bind',
                qualifiers={
                    'label': [f'{name}_FP'],
                    'note': [
                        f"Sequence: {p.get('fp_sequence','')}; "
                        f"Tm={p.get('fp_tm',0)}°C; GC={p.get('fp_gc',0)}%; "
                        f"Len={fp_len}bp; Penalty={p.get('fp_penalty',0)}"
                    ],
                    'ApEinfo_fwdcolor': [FP_COLOR],
                    'ApEinfo_revcolor': [FP_COLOR],
                }
            ))

        # Reverse primer — binds bottom strand, at amplicon end.
        # For the wrap amplicon this end is in EXTENDED coordinates (past
        # seq_len), so the RP itself can straddle the origin — this is
        # exactly the case that was previously mis-placed at the tail of
        # the sequence. _build_location() now splits it correctly.
        rp_len       = p.get('rp_length', 0)
        rp_end_ext   = a_end_ext
        rp_start_ext = max(0, rp_end_ext - rp_len)
        if rp_end_ext > rp_start_ext:
            features.append(SeqFeature(
                _build_location(rp_start_ext, rp_end_ext, seq_len, strand=-1),
                type='primer_bind',
                qualifiers={
                    'label': [f'{name}_RP'],
                    'note': [
                        f"Sequence: {p.get('rp_sequence','')}; "
                        f"Tm={p.get('rp_tm',0)}°C; GC={p.get('rp_gc',0)}%; "
                        f"Len={rp_len}bp; Penalty={p.get('rp_penalty',0)}"
                        + ("; binds across plasmid origin" if wraps else "")
                    ],
                    'ApEinfo_fwdcolor': [RP_COLOR],
                    'ApEinfo_revcolor': [RP_COLOR],
                }
            ))

    features.sort(key=lambda ft: (int(ft.location.start), ft.type != 'source'))
    record.features = features

    handle = io.StringIO()
    SeqIO.write(record, handle, 'genbank')
    return handle.getvalue()


def build_annotated_genbank_bytes(seq_info, primers, project_name, circular=True):
    """Same as build_annotated_genbank but returns UTF-8 bytes, ready for
    st.download_button."""
    return build_annotated_genbank(seq_info, primers, project_name,
                                    circular=circular).encode('utf-8')
