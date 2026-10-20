"""
PDF report renderer. Consumes report_data.build_report_data() — the same
content as the Word report. Differences by design:
  * PDF has no Word-style comments, so primers in the sequence appendix get
    small numbered tags (e.g. 3F / 3R) and a legend table below the sequence.
  * Only the built-in PDF fonts are used, so text is sanitised to Latin-1.
"""
import base64
from collections import defaultdict
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (Image as RLImage, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

from .seq_annot import (BLOCK, FP_COLOR, PER_LINE, RP_COLOR, build_cover,
                        color_for, tag_for, verify_footprint)

NAVY, INDIGO, GRID = '#1A237E', '#283593', '#9FA8DA'
STATUS_BG = {
    'Pending': '#FFF9C4', 'Success': '#C8E6C9', 'Done': '#C8E6C9', 'Failed': '#FFCDD2',
    'Overlap Violation': '#E1BEE7', 'Design Failed': '#F8BBD9', 'Redesigned': '#B3E5FC',
}
PASS_BG, FAIL_BG, NA_BG = '#C8E6C9', '#FFCDD2', '#EEEEEE'
LABEL_W = 7

_REPL = {'→': '->', '←': '<-', '≥': '>=', '≤': '<=', '✓': 'ok', '✗': 'x', '✅': '', '❌': '',
         '−': '-', '’': "'", '‘': "'", '“': '"', '”': '"', 'µ': 'u', ' ': ' '}


def _safe(v):
    """Make text safe for the built-in (Latin-1) PDF fonts."""
    s = '' if v is None else str(v)
    for k, r in _REPL.items():
        s = s.replace(k, r)
    return s.encode('cp1252', errors='replace').decode('cp1252')


def _styles():
    ss = getSampleStyleSheet()
    st = {
        'title': ParagraphStyle('t', parent=ss['Title'], fontSize=18, alignment=0,
                                textColor=colors.HexColor(NAVY), spaceAfter=4),
        'h1': ParagraphStyle('h1', parent=ss['Heading2'], fontSize=13,
                             textColor=colors.HexColor(NAVY), spaceBefore=12, spaceAfter=5),
        'h2': ParagraphStyle('h2', parent=ss['Heading3'], fontSize=10.5,
                             textColor=colors.HexColor(INDIGO), spaceBefore=6, spaceAfter=3),
        'body': ParagraphStyle('b', parent=ss['Normal'], fontSize=9, leading=11.5, spaceAfter=3),
        'note': ParagraphStyle('n', parent=ss['Normal'], fontSize=8, leading=10,
                               textColor=colors.HexColor('#555555'), fontName='Helvetica-Oblique',
                               spaceAfter=4),
        'cell': ParagraphStyle('c', parent=ss['Normal'], fontSize=7.5, leading=9),
        'cellc': ParagraphStyle('cc', parent=ss['Normal'], fontSize=7.5, leading=9, alignment=TA_CENTER),
        'mono': ParagraphStyle('m', parent=ss['Normal'], fontSize=7, leading=9, fontName='Courier'),
        'head': ParagraphStyle('hd', parent=ss['Normal'], fontSize=7.5, leading=9,
                               textColor=colors.white, fontName='Helvetica-Bold', alignment=TA_CENTER),
        'cap': ParagraphStyle('cap', parent=ss['Normal'], fontSize=7, leading=8.5, alignment=TA_CENTER),
        'seq': ParagraphStyle('seq', parent=ss['Normal'], fontName='Courier', fontSize=7.5,
                              leading=11, spaceAfter=3),
    }
    return st


def _P(text, style):
    return Paragraph(escape(_safe(text)).replace('\n', '<br/>'), style)


def _table(S, headers, rows, widths_cm, mono_cols=(), status_col=None, result_col=None,
           center_cols=(), label_col0=False):
    data = [[Paragraph(escape(_safe(h)).replace('\n', '<br/>'), S['head']) for h in headers]]
    for row in rows:
        cells = []
        for ci, v in enumerate(row):
            if ci in mono_cols:
                sty = S['mono']
            elif ci in center_cols or ci in (status_col, result_col):
                sty = S['cellc']
            else:
                sty = S['cell']
            cells.append(_P(v, sty))
        data.append(cells)
    t = Table(data, colWidths=[w * cm for w in widths_cm], repeatRows=1)
    cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(INDIGO)),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor(GRID)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F5FF')]),
    ]
    if label_col0:
        cmds.append(('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#E8EAF6')))
    for ri, row in enumerate(rows, 1):
        if status_col is not None:
            cmds.append(('BACKGROUND', (status_col, ri), (status_col, ri),
                         colors.HexColor(STATUS_BG.get(str(row[status_col]), '#FFFFFF'))))
        if result_col is not None:
            v = str(row[result_col])
            cmds.append(('BACKGROUND', (result_col, ri), (result_col, ri),
                         colors.HexColor(PASS_BG if v == 'Pass' else FAIL_BG if v == 'Fail' else NA_BG)))
    t.setStyle(TableStyle(cmds))
    return t


def _fmt(v):
    return 'N/A' if v is None else str(v)


def _position_text(p, seq_len):
    s, e = p['amplicon_start'] + 1, p['amplicon_end']
    return f"{s}-{seq_len}, 1-{e - seq_len}" if e > seq_len else f"{s}-{e}"


def _png_flowable(buf, max_w_cm, max_h_cm):
    buf.seek(0)
    iw, ih = ImageReader(buf).getSize()
    buf.seek(0)
    scale = min(max_w_cm * cm / iw, max_h_cm * cm / ih)
    return RLImage(buf, width=iw * scale, height=ih * scale)


def _gel_png(b64):
    try:
        from PIL import Image
        img = Image.open(BytesIO(base64.b64decode(b64)))
        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')
        out = BytesIO()
        img.save(out, format='PNG')
        out.seek(0)
        return out
    except Exception:
        return None


# ── sections ─────────────────────────────────────────────────────────────────
def _title_block(S, rd):
    m, best = rd['meta'], rd['primers']
    cnt = defaultdict(int)
    for p in best:
        cnt[p.get('status', 'Pending')] += 1
    rows = [("Project", m['project_name']),
            ("Vector", f"{m['vector_name']}  ({m['vector_length']:,} bp, circular)"),
            ("Report date", m['report_date'])]
    if m.get('author'):
        rows.append(("Prepared by", m['author']))
    if m.get('lab'):
        rows.append(("Laboratory / Institute", m['lab']))
    rows.append(("Amplicons",
                 f"{len(best)} total - {cnt['Success'] + cnt['Done']} success, {cnt['Pending']} pending, "
                 f"{cnt['Failed'] + cnt['Overlap Violation'] + cnt['Design Failed']} failed/violation"))
    data = [[_P(k, ParagraphStyle('k', parent=S['cell'], fontName='Helvetica-Bold', fontSize=8.5)),
             _P(v, ParagraphStyle('v', parent=S['cell'], fontSize=8.5))] for k, v in rows]
    t = Table(data, colWidths=[5 * cm, 21.7 * cm])
    t.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor(GRID)),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E8EAF6')),
        ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    return [Paragraph(escape(_safe(f"Overlapping PCR Primer Report: {m['project_name']}")), S['title']),
            _P("SOPrimeR - Division of Plant Physiology, ICAR-Indian Agricultural Research Institute - "
               "full vector coverage verification for genome-edited plant exemption.", S['note']),
            t]


def _params(S, rd, n):
    p = rd['design_params']
    tm = (f"{p['min_tm']}-{p['max_tm']} C (optimum {p['opt_tm']} C)"
          if p.get('opt_tm') is not None else "Not recorded")
    rows = [("Amplicon size", f"{p['min_amplicon']}-{p['max_amplicon']} bp"),
            ("Minimum overlap between consecutive amplicons", f"{p['min_overlap']} bp"),
            ("Primer length", f"{p['primer_len_min']}-{p['primer_len_max']} nt"),
            ("Primer Tm", tm),
            ("Primer GC content", f"{p['min_gc']}-{p['max_gc']} %"),
            ("Salt (monovalent) / DNA concentration", f"{p['salt_monovalent']} mM / {p['dna_conc']} nM"),
            ("Designed at", p.get('designed_at') or "Not recorded"),
            ("Vector topology", "Circular (last amplicon closes the circle across the origin)")]
    out = [Paragraph(f"{n}. Design Parameters", S['h1']),
           _table(S, ["Parameter", "Value"], rows, [10, 16.7], label_col0=True)]
    if not rd['params_recorded']:
        out.append(_P("Design parameters were not stored for this project (designed before parameter "
                      "recording was added); default values are shown and Tm limits are not available.",
                      S['note']))
    return out


def _rules(S, rd, n):
    rules = rd['rules']
    passed = sum(1 for r in rules if r['status'] == 'Pass')
    graded = sum(1 for r in rules if r['status'] != 'N/A')
    rows = [(r['rule'], r['text'], r['status'], r['detail']) for r in rules]
    return [Paragraph(f"{n}. Protocol Rule Verification", S['h1']),
            _P(f"{passed} of {graded} rules passed on the current (latest-version) primer set.", S['body']),
            _table(S, ["Rule", "Requirement", "Result", "Detail"], rows, [1.4, 11, 2.0, 12.3],
                   result_col=2, center_cols=(0,))]


def _map(S, rd, n):
    si = rd.get('seq_info')
    valid = [p for p in rd['primers'] if p.get('fp_sequence') != 'DESIGN_FAILED']
    if not si or not valid:
        return [], n
    try:
        from .vector_map import build_static_circular_map_png
        img = _png_flowable(build_static_circular_map_png(si, valid), 16, 15.5)
    except Exception:
        return [], n
    img.hAlign = 'CENTER'
    return [PageBreak(), Paragraph(f"{n}. Circular Vector Map - Amplicons & Primers", S['h1']), img], n + 1


def _primers(S, rd, n):
    L = rd['meta']['vector_length']
    rows = [(p['amplicon_num'], p.get('amplicon_name') or f"Amplicon_{p['amplicon_num']}",
             p.get('version', 1), p.get('status', 'Pending'),
             p['fp_sequence'], p['fp_length'], p['fp_tm'], p['fp_gc'],
             p['rp_sequence'], p['rp_length'], p['rp_tm'], p['rp_gc'],
             _position_text(p, L), p['amplicon_length'],
             _fmt(p.get('overlap_prev')), _fmt(p.get('overlap_next'))) for p in rd['primers']]
    return [PageBreak(), Paragraph(f"{n}. Primer Design Summary", S['h1']),
            _table(S, ["Amp\n#", "Name", "Ver", "Status", "Forward primer (5'-3')", "Len", "Tm\n(C)",
                       "GC\n(%)", "Reverse primer (5'-3')", "Len", "Tm\n(C)", "GC\n(%)",
                       "Position (bp)", "Amp\nlen", "Ovl\nup", "Ovl\ndown"],
                   rows, [0.9, 2.6, 0.8, 1.8, 4.2, 0.9, 1.0, 0.9, 4.2, 0.9, 1.0, 0.9, 2.6, 1.2, 1.4, 1.4],
                   mono_cols=(4, 8), status_col=3,
                   center_cols=(0, 2, 5, 6, 7, 9, 10, 11, 13, 14, 15)),
            _P("Overlap up/down = bp shared with the previous/next amplicon. For the first and last "
               "amplicons, the missing neighbour is the circular partner across the origin. Positions "
               "are 1-based; a wrapped amplicon lists both segments.", S['note'])]


def _controls(S, rd, n):
    out = [Paragraph(f"{n}. Control Primers (endogenous gene, positive control)", S['h1'])]
    if not rd['controls']:
        return out + [_P("No control primers were recorded for this project.", S['note'])]
    rows = [(c['name'], c.get('target', ''), c.get('fp_sequence', ''), c.get('fp_length', ''),
             c.get('fp_tm', ''), c.get('fp_gc', ''), c.get('rp_sequence', ''), c.get('rp_length', ''),
             c.get('rp_tm', ''), c.get('rp_gc', ''), _fmt(c.get('expected_size')), c.get('notes', ''))
            for c in rd['controls']]
    out.append(_table(S, ["Control", "Target gene", "Forward (5'-3')", "Len", "Tm\n(C)", "GC\n(%)",
                          "Reverse (5'-3')", "Len", "Tm\n(C)", "GC\n(%)", "Expected\nsize (bp)", "Notes"],
                      rows, [2.3, 2.4, 4.0, 0.9, 1.0, 0.9, 4.0, 0.9, 1.0, 0.9, 1.8, 6.6],
                      mono_cols=(2, 6), center_cols=(3, 4, 5, 7, 8, 9, 10)))
    return out


def _runs(S, rd, n):
    out = [Paragraph(f"{n}. PCR Run Log", S['h1'])]
    if not rd['runs']:
        return out + [_P("No PCR runs were logged for this project.", S['note'])]
    rows = []
    for r in rd['runs']:
        ctrl = ", ".join(c['name'] for c in r.get('controls', [])) or "-"
        lanes = "; ".join(f"{i + 1}: {l}" for i, l in enumerate(r.get('lane_labels') or [])) or "-"
        rows.append((r.get('run_date', ''), r.get('amplicon_num', ''), r.get('result', ''),
                     r.get('lane_number', ''), ctrl, lanes, r.get('notes', '')))
    out.append(_table(S, ["Run date", "Amp\n#", "Result", "Lane", "Control pair(s)", "Lanes in gel", "Notes"],
                      rows, [3.0, 1.1, 1.5, 1.2, 4.0, 8.0, 7.9], result_col=2, center_cols=(1, 3)))
    return out


def _gels(S, rd, n):
    gel_runs = [r for r in rd['runs'] if r.get('gel_image_b64')]
    if not gel_runs:
        return [], n
    out = [PageBreak(), Paragraph(f"{n}. Gel Images", S['h1'])]
    by_amp = defaultdict(list)
    for r in gel_runs:
        by_amp[r.get('amplicon_num', '?')].append(r)
    for amp in sorted(by_amp, key=lambda x: (str(type(x)), x)):
        out.append(Paragraph(f"Amplicon {amp}", S['h2']))
        items = by_amp[amp]
        for i in range(0, len(items), 3):
            cells = []
            for r in items[i:i + 3]:
                png = _gel_png(r['gel_image_b64'])
                ok = r.get('result') == 'Pass'
                col = '#1B5E20' if ok else '#B71C1C'
                extra = []
                ctrl = ", ".join(c['name'] for c in r.get('controls', []))
                if ctrl:
                    extra.append(f"Control: {ctrl}")
                if r.get('lane_labels'):
                    extra.append("Lanes: " + ", ".join(r['lane_labels']))
                if r.get('notes'):
                    extra.append(r['notes'])
                cap = Paragraph(
                    f"<font color='{col}'><b>{'PASS' if ok else 'FAIL'}</b> - Lane "
                    f"{escape(_safe(r.get('lane_number', '')))} - {escape(_safe(r.get('run_date', '')))}</font>"
                    + (f"<br/>{escape(_safe(' | '.join(extra)))}" if extra else ""), S['cap'])
                img = (_png_flowable(png, 8.2, 6) if png else _P("[image could not be read]", S['cap']))
                cells.append([img, Spacer(1, 3), cap])
            while len(cells) < 3:
                cells.append('')
            t = Table([cells], colWidths=[8.9 * cm] * 3)
            t.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor(GRID)),
                                   ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                   ('ALIGN', (0, 0), (-1, -1), 'CENTER')]))
            out += [t, Spacer(1, 5)]
    return out, n + 1


def _history(S, rd, n):
    if not rd['history']:
        return []
    rows = [(h.get('amplicon_num', ''), h.get('failure_type', ''), h.get('attempt_num', ''),
             h.get('extension_left', ''), h.get('extension_right', ''),
             _fmt(h.get('upstream_overlap_result')), _fmt(h.get('downstream_overlap_result')),
             h.get('reason', ''), h.get('redesign_date', '')) for h in rd['history']]
    return [Paragraph(f"{n}. Redesign History", S['h1']),
            _table(S, ["Amp\n#", "Failure reason", "Attempt", "Ext\nleft", "Ext\nright",
                       "Overlap\nup", "Overlap\ndown", "Notes", "Date"],
                   rows, [1.2, 4.0, 1.5, 1.3, 1.3, 1.8, 1.8, 9.8, 3.0], center_cols=(0, 2, 3, 4, 5, 6))]


# ── Appendix A: sequence with numbered primer tags ───────────────────────────
def _sequence_appendix(S, rd, status):
    sequence = rd['sequence'].upper()
    L = len(sequence)
    fps = rd['footprints']
    cover = build_cover(L, fps)
    out = [PageBreak(), Paragraph("Appendix A. Vector Sequence with Annotated Primers", S['h1']),
           Paragraph(
               f"{escape(_safe(rd['meta']['vector_name']))} - {L:,} bp, circular. Numbering is 1-based, "
               f"100 bp per line, blocks of 10. "
               f"<font color='#{FP_COLOR}'><b>Forward primer</b></font> &nbsp; "
               f"<font color='#{RP_COLOR}'><b>Reverse primer</b></font>", S['body']),
           _P("Each primer is marked with a small tag at its first base (amplicon number + F or R, "
              "e.g. 3F). Reverse primers are shown as their top-strand footprint.", S['note'])]

    for line_start in range(0, L, PER_LINE):
        parts, state = [], {'text': '', 'keys': None}

        def flush():
            if state['text']:
                col = color_for(state['keys'], fps)
                parts.append(f"<font color='#{col}'><b>{state['text']}</b></font>" if col else state['text'])
            state['text'], state['keys'] = '', None

        def add(ch, keys):
            if state['keys'] != keys:
                flush()
                state['keys'] = keys
            state['text'] += ch

        num = str(line_start + 1)
        label = ('&nbsp;' * (LABEL_W - len(num)) + num + '&nbsp;&nbsp;')
        end = min(line_start + PER_LINE, L)
        for pos in range(line_start, end):
            keys = frozenset(cover[pos])
            if pos > line_start and (pos - line_start) % BLOCK == 0:
                prev = frozenset(cover[pos - 1])
                add('&nbsp;', prev if (prev and prev == keys) else frozenset())
            for (i, j) in sorted(keys):
                if pos == fps[i]['spans'][j][0]:
                    flush()
                    parts.append(f"<super><font size='5' color='{NAVY}'><b>{tag_for(fps[i])}</b></font></super>")
            add(sequence[pos], keys)
        flush()
        out.append(Paragraph(f"<font color='#78909C'>{label}</font>" + ''.join(parts), S['seq']))

    for f in fps:
        if not verify_footprint(f, sequence):
            status['mismatches'].append(f['name'])
    if status['mismatches']:
        out.append(Paragraph(
            "<font color='#B71C1C'><i>Warning: these primers do not match the vector sequence at their "
            "recorded position - " + escape(_safe(', '.join(status['mismatches']))) +
            ". Verify before submission.</i></font>", S['note']))
    return out


# ── public entry point ───────────────────────────────────────────────────────
def build_pdf_report(rd, return_status=False):
    """
    rd = report_data.build_report_data(...). Returns BytesIO (.pdf), or
    (BytesIO, status) with status = {'mismatches': [...]} when return_status=True.
    """
    S = _styles()
    opts = rd['options']
    status = {'mismatches': []}
    story = []
    story += _title_block(S, rd)
    n = 1
    story += _params(S, rd, n); n += 1
    story += _rules(S, rd, n); n += 1
    if rd.get('seq_info') and rd['primers']:
        m, n2 = _map(S, rd, n)
        story += m
        n = n2
    story += _primers(S, rd, n); n += 1
    if opts.get('include_controls', True):
        story += _controls(S, rd, n); n += 1
    story += _runs(S, rd, n); n += 1
    if opts.get('include_gels', True):
        g, n = _gels(S, rd, n)
        story += g
    if opts.get('include_history', True):
        story += _history(S, rd, n)
    if opts.get('include_sequence', True) and rd.get('sequence') and rd.get('footprints'):
        story += _sequence_appendix(S, rd, status)

    title = _safe(f"{rd['meta']['project_name']} - SOPrimeR report")

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#555555'))
        canvas.drawCentredString(landscape(A4)[0] / 2, 0.8 * cm, f"{title}    |    Page {doc.page}")
        canvas.restoreState()

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.6 * cm, title=title,
                            author=_safe(rd['meta'].get('author') or 'SOPrimeR'))
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    buf.seek(0)
    return (buf, status) if return_status else buf
