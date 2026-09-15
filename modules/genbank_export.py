"""
genbank_export.py — BioSafe Primer
Builds a GenBank (.gb) file annotated with amplicon and primer features,
readable in SnapGene, ApE, Benchling, etc.

Feature layout (amplicon/primer annotations ONLY — no source feature and
no features carried over from the originally uploaded file):
  misc_feature  — one per amplicon, colored by status
  primer_bind   — one per FP (forward strand) and RP (reverse strand)
"""
import io
import re
from datetime import datetime

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.SeqFeature import SeqFeature, FeatureLocation
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
        a_start = max(0, min(p['amplicon_start'], seq_len))
        a_end   = max(a_start + 1, min(p['amplicon_end'], seq_len))

        prev_ov = p.get('overlap_prev')
        next_ov = p.get('overlap_next')
        amp_note = (
            f"Status: {status}; Version: {p.get('version', 1)}; "
            f"Length: {p.get('amplicon_length', a_end - a_start)} bp; "
            f"Overlap upstream: {prev_ov if prev_ov is not None else 'N/A'} bp; "
            f"Overlap downstream: {next_ov if next_ov is not None else 'N/A'} bp; "
            f"Pair penalty: {p.get('pair_penalty', 0)}"
        )
        features.append(SeqFeature(
            FeatureLocation(a_start, a_end, strand=1),
            type='misc_feature',
            qualifiers={
                'label':             [name],
                'note':              [amp_note],
                'ApEinfo_fwdcolor':  [color],
                'ApEinfo_revcolor':  [color],
            }
        ))

        # Forward primer — binds top strand, at amplicon start
        fp_len   = p.get('fp_length', 0)
        fp_start = a_start
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

        # Reverse primer — binds bottom strand, at amplicon end
        rp_len   = p.get('rp_length', 0)
        rp_end   = a_end
        rp_start = max(0, rp_end - rp_len)
        if rp_end > rp_start:
            features.append(SeqFeature(
                FeatureLocation(rp_start, rp_end, strand=-1),
                type='primer_bind',
                qualifiers={
                    'label': [f'{name}_RP'],
                    'note': [
                        f"Sequence: {p.get('rp_sequence','')}; "
                        f"Tm={p.get('rp_tm',0)}°C; GC={p.get('rp_gc',0)}%; "
                        f"Len={rp_len}bp; Penalty={p.get('rp_penalty',0)}"
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
