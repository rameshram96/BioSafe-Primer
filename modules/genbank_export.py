import io
import re
from datetime import datetime

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.SeqFeature import SeqFeature, FeatureLocation, CompoundLocation
from Bio import SeqIO

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


def _real_spans(start, end, seq_len):
    """
    Convert an 'extended' (possibly > seq_len, monotonic) coordinate span
    into one or two REAL 0-based half-open spans on the circular vector.

    Handles all three cases that show up for the origin-spanning amplicon
    and its reverse primer:
      - span entirely before the origin            -> unchanged, 1 span
      - span straddles the origin (start<seq_len<end) -> 2 spans (the
        case `split_origin_span()` in primer_design.py already covered)
      - span ENTIRELY past the origin (start>=seq_len) -> both ends need
        seq_len subtracted; this is the case that was missing and is
        exactly what produces a mis-sized/mis-placed reverse primer,
        because the RP of the wrap amplicon usually sits *fully* inside
        the wrapped pad near base 1, not straddling it.
    """
    if start >= seq_len:
        return [(start - seq_len, end - seq_len)]
    if end <= seq_len:
        return [(start, end)]
    return [(start, seq_len), (0, end - seq_len)]


def _location_from_spans(spans, strand):
    locs = [FeatureLocation(s, e, strand=strand) for s, e in spans]
    return locs[0] if len(locs) == 1 else CompoundLocation(locs)


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

        # 'amplicon_start'/'amplicon_end' are EXTENDED (monotonic) coords —
        # amplicon_end can exceed seq_len for the amplicon that wraps the
        # plasmid origin. Always convert to real spans before building any
        # GenBank location; never clamp-and-truncate (that silently drops
        # the wrapped portion and mis-anchors anything measured from it,
        # which is what was producing the bad reverse-primer location/size).
        raw_start = max(0, p['amplicon_start'])
        raw_end   = max(raw_start + 1, p['amplicon_end'])

        amp_spans = _real_spans(raw_start, raw_end, seq_len)
        amp_loc   = _location_from_spans(amp_spans, strand=1)

        prev_ov = p.get('overlap_prev')
        next_ov = p.get('overlap_next')
        amp_note = (
            f"Status: {status}; Version: {p.get('version', 1)}; "
            f"Length: {p.get('amplicon_length', raw_end - raw_start)} bp; "
            f"Overlap upstream: {prev_ov if prev_ov is not None else 'N/A'} bp; "
            f"Overlap downstream: {next_ov if next_ov is not None else 'N/A'} bp; "
            f"Pair penalty: {p.get('pair_penalty', 0)}"
            + (" (wraps plasmid origin — location is a join() across base 1)"
               if len(amp_spans) > 1 else "")
        )
        features.append(SeqFeature(
            amp_loc,
            type='misc_feature',
            qualifiers={
                'label':             [name],
                'note':              [amp_note],
                'ApEinfo_fwdcolor':  [color],
                'ApEinfo_revcolor':  [color],
            }
        ))

        # Forward primer — binds top strand, at amplicon start.
        # FP always sits within the pre-origin part of the amplicon, so it
        # is always in real (< seq_len) coordinates already — no wrap
        # handling needed here.
        fp_len   = p.get('fp_length', 0)
        fp_start = raw_start
        fp_end   = min(seq_len, fp_start + fp_len)
        if fp_end > fp_start:
            features.append(SeqFeature(
                FeatureLocation(fp_start, fp_end, strand=1),
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
        # THIS is the fix: previously rp_end was taken from the amplicon's
        # CLAMPED end (min(amplicon_end, seq_len)), which for the wrap
        # amplicon anchors the RP at the physical end of the vector — a
        # location that has nothing to do with where the primer actually
        # binds (the wrap pad taken from near base 1). Worse, because
        # rp_start was then computed as rp_end - rp_len from that wrong
        # anchor, the feature could visually swallow most of the
        # already-truncated amplicon block, reading as an oversized RP.
        # Fix: compute RP's real (start, end) directly from the amplicon's
        # own EXTENDED end, then convert THAT to real spans — same rule
        # used for the amplicon block itself.
        rp_len        = p.get('rp_length', 0)
        rp_raw_end    = raw_end
        rp_raw_start  = raw_end - rp_len
        if rp_raw_end > rp_raw_start:
            rp_spans = _real_spans(rp_raw_start, rp_raw_end, seq_len)
            rp_loc   = _location_from_spans(rp_spans, strand=-1)
            features.append(SeqFeature(
                rp_loc,
                type='primer_bind',
                qualifiers={
                    'label': [f'{name}_RP'],
                    'note': [
                        f"Sequence: {p.get('rp_sequence','')}; "
                        f"Tm={p.get('rp_tm',0)}°C; GC={p.get('rp_gc',0)}%; "
                        f"Len={rp_len}bp; Penalty={p.get('rp_penalty',0)}"
                        + (" (wraps plasmid origin)" if len(rp_spans) > 1 else "")
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
