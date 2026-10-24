"""
Word (.docx) report renderer. Consumes the dict from report_data.build_report_data()
so it stays in sync with the PDF renderer.

Stage 3: everything EXCEPT the vector sequence appendix (added in stage 4).
"""
import base64
from collections import defaultdict
from io import BytesIO

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

NAVY = '1A237E'
INDIGO = '283593'
GRID = '9FA8DA'
ROW_ALT = 'F5F5FF'
PASS_BG, FAIL_BG, NA_BG = 'C8E6C9', 'FFCDD2', 'EEEEEE'
STATUS_BG = {
    'Pending': 'FFF9C4', 'Success': 'C8E6C9', 'Done': 'C8E6C9', 'Failed': 'FFCDD2',
    'Overlap Violation': 'E1BEE7', 'Design Failed': 'F8BBD9', 'Redesigned': 'B3E5FC',
}
MONO = 'Courier New'


# ── low-level helpers ────────────────────────────────────────────────────────
def _shade(cell, hex_fill):
    tcPr = cell._tc.get_or_add_tcPr()
    for old in tcPr.findall(qn('w:shd')):
        tcPr.remove(old)
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hex_fill)
    tcPr.append(shd)


def _repeat_header(row):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement('w:tblHeader')
    el.set(qn('w:val'), 'true')
    trPr.append(el)


def _no_split(row):
    trPr = row._tr.get_or_add_trPr()
    trPr.append(OxmlElement('w:cantSplit'))


def _set_cell(cell, text, size=8, bold=False, color=None, mono=False,
              align=None, italic=False):
    cell.text = ''
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.space_before = Pt(0)
    if align == 'center':
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run('' if text is None else str(text))
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    if mono:
        run.font.name = MONO
        run._element.rPr.rFonts.set(qn('w:eastAsia'), MONO)
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


def _borders(table, color=GRID, sz=4):
    tblPr = table._tbl.tblPr
    b = OxmlElement('w:tblBorders')
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        e = OxmlElement(f'w:{edge}')
        e.set(qn('w:val'), 'single')
        e.set(qn('w:sz'), str(sz))
        e.set(qn('w:space'), '0')
        e.set(qn('w:color'), color)
        b.append(e)
    tblPr.append(b)


def _table(doc, headers, rows, widths_cm, size=8, mono_cols=(), status_col=None,
           result_col=None, center_cols=()):
    t = doc.add_table(rows=1, cols=len(headers))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    _borders(t)
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        _set_cell(c, h, size=size, bold=True, color='FFFFFF', align='center')
        _shade(c, INDIGO)
    _repeat_header(t.rows[0])

    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        _no_split(t.rows[-1])
        for ci, val in enumerate(row):
            mono = ci in mono_cols
            _set_cell(cells[ci], val, size=(size - 0.5 if mono else size), mono=mono,
                      align=None if mono else ('center' if ci in center_cols or
                                               ci in (status_col, result_col) else None))
            if ri % 2:
                _shade(cells[ci], ROW_ALT)
        if status_col is not None:
            _shade(cells[status_col], STATUS_BG.get(str(row[status_col]), 'FFFFFF'))
        if result_col is not None:
            v = str(row[result_col])
            _shade(cells[result_col],
                   PASS_BG if v == 'Pass' else FAIL_BG if v == 'Fail' else NA_BG)

    _apply_widths(t, widths_cm)
    return t


def _apply_widths(table, widths_cm):
    """Fixed layout + tblGrid + per-cell widths (Word and LibreOffice both honour it)."""
    tblPr = table._tbl.tblPr
    layout = OxmlElement('w:tblLayout')
    layout.set(qn('w:type'), 'fixed')
    tblPr.append(layout)
    for i, w in enumerate(widths_cm):
        table.columns[i].width = Cm(w)
    for row in table.rows:
        for i, w in enumerate(widths_cm):
            row.cells[i].width = Cm(w)


def _heading(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    for r in h.runs:
        r.font.color.rgb = RGBColor.from_string(NAVY if level == 1 else INDIGO)
    return h


def _note(doc, text, italic=True, size=9):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.italic = italic
    r.font.size = Pt(size)
    r.font.color.rgb = RGBColor.from_string('555555')
    return p


def _add_field(run, instr):
    for kind, text in (('begin', None), (None, instr), ('end', None)):
        if kind:
            el = OxmlElement('w:fldChar')
            el.set(qn('w:fldCharType'), kind)
        else:
            el = OxmlElement('w:instrText')
            el.set(qn('xml:space'), 'preserve')
            el.text = text
        run._r.append(el)


def _footer(section, left_text):
    p = section.footer.paragraphs[0]
    p.text = ''
    r = p.add_run(f"{left_text}    |    Page ")
    r.font.size = Pt(8)
    r2 = p.add_run()
    r2.font.size = Pt(8)
    _add_field(r2, 'PAGE')
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER


def _fmt(v, suffix=''):
    return 'N/A' if v is None else f"{v}{suffix}"


def _position_text(p, seq_len):
    s, e = p['amplicon_start'] + 1, p['amplicon_end']
    if e > seq_len:
        return f"{s}–{seq_len}, 1–{e - seq_len}"
    return f"{s}–{e}"


def _gel_png(b64):
    """base64 image -> PNG BytesIO (normalises TIFF/JPEG etc.), or None."""
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
def _title_block(doc, rd):
    m = rd['meta']
    t = doc.add_paragraph()
    r = t.add_run(f"Overlapping PCR Primer Report: {m['project_name']}")
    r.bold = True
    r.font.size = Pt(18)
    r.font.color.rgb = RGBColor.from_string(NAVY)
    _note(doc, "GE-EDIT · Division of Plant Physiology, ICAR-Indian Agricultural "
               "Research Institute — full vector coverage verification for "
               "genome-edited plant exemption.", italic=False)

    best = rd['primers']
    cnt = defaultdict(int)
    for p in best:
        cnt[p.get('status', 'Pending')] += 1
    rows = [
        ("Project", m['project_name']),
        ("Vector", f"{m['vector_name']}  ({m['vector_length']:,} bp, circular)"),
        ("Report date", m['report_date']),
    ]
    if m.get('author'):
        rows.append(("Prepared by", m['author']))
    if m.get('lab'):
        rows.append(("Laboratory / Institute", m['lab']))
    rows += [
        ("Amplicons", f"{len(best)} total — {cnt['Success'] + cnt['Done']} success, "
                      f"{cnt['Pending']} pending, "
                      f"{cnt['Failed'] + cnt['Overlap Violation'] + cnt['Design Failed']} failed/violation"),
    ]
    t = doc.add_table(rows=0, cols=2)
    t.autofit = False
    _borders(t)
    for k, v in rows:
        cells = t.add_row().cells
        _set_cell(cells[0], k, size=9, bold=True)
        _shade(cells[0], 'E8EAF6')
        _set_cell(cells[1], v, size=9)
    _apply_widths(t, [5, 21.7])


def _params_section(doc, rd):
    _heading(doc, "1. Design Parameters")
    p = rd['design_params']
    tm = (f"{p['min_tm']}–{p['max_tm']} °C (optimum {p['opt_tm']} °C)"
          if p.get('opt_tm') is not None else "Not recorded")
    rows = [
        ("Amplicon size", f"{p['min_amplicon']}–{p['max_amplicon']} bp"),
        ("Minimum overlap between consecutive amplicons", f"{p['min_overlap']} bp"),
        ("Primer length", f"{p['primer_len_min']}–{p['primer_len_max']} nt"),
        ("Primer Tm", tm),
        ("Primer GC content", f"{p['min_gc']}–{p['max_gc']} %"),
        ("Salt (monovalent) / DNA concentration",
         f"{p['salt_monovalent']} mM / {p['dna_conc']} nM"),
        ("Designed at", p.get('designed_at') or "Not recorded"),
        ("Vector topology", "Circular (last amplicon closes the circle across the origin)"),
    ]
    _table(doc, ["Parameter", "Value"], rows, [10, 16.7], size=9)
    if not rd['params_recorded']:
        _note(doc, "Design parameters were not stored for this project (designed before "
                   "parameter recording was added); default values are shown and Tm "
                   "limits are not available.")


def _rules_section(doc, rd):
    _heading(doc, "2. Protocol Rule Verification")
    rules = rd['rules']
    passed = sum(1 for r in rules if r['status'] == 'Pass')
    graded = sum(1 for r in rules if r['status'] != 'N/A')
    _note(doc, f"{passed} of {graded} rules passed on the current (latest-version) primer set.",
          italic=False, size=10)
    rows = [(r['rule'], r['text'], r['status'], r['detail']) for r in rules]
    _table(doc, ["Rule", "Requirement", "Result", "Detail"], rows,
           [1.4, 11, 2.0, 12.3], size=9, result_col=2, center_cols=(0,))


def _map_section(doc, rd):
    si, best = rd.get('seq_info'), rd['primers']
    valid = [p for p in best if p.get('fp_sequence') != 'DESIGN_FAILED']
    if not si or not valid:
        return
    try:
        from .vector_map import build_static_circular_map_png
        buf = build_static_circular_map_png(si, valid)
    except Exception:
        return
    _heading(doc, "3. Circular Vector Map — Amplicons & Primers")
    doc.add_picture(buf, width=Cm(14))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER


def _primer_section(doc, rd, n):
    _heading(doc, f"{n}. Primer Design Summary")
    L = rd['meta']['vector_length']
    rows = []
    for p in rd['primers']:
        rows.append((
            p['amplicon_num'], p.get('amplicon_name') or f"Amplicon_{p['amplicon_num']}",
            p.get('version', 1), p.get('status', 'Pending'),
            p['fp_sequence'], p['fp_length'], p['fp_tm'], p['fp_gc'],
            p['rp_sequence'], p['rp_length'], p['rp_tm'], p['rp_gc'],
            _position_text(p, L), p['amplicon_length'],
            _fmt(p.get('overlap_prev')), _fmt(p.get('overlap_next')),
        ))
    _table(doc,
           ["Amp\n#", "Name", "Ver", "Status", "Forward primer (5'→3')", "Len", "Tm\n(°C)",
            "GC\n(%)", "Reverse primer (5'→3')", "Len", "Tm\n(°C)", "GC\n(%)",
            "Position (bp)", "Amp\nlen", "Ovl\nup", "Ovl\ndown"],
           rows,
           [0.9, 2.6, 0.8, 1.8, 4.2, 0.9, 1.0, 0.9, 4.2, 0.9, 1.0, 0.9, 2.6, 1.2, 1.4, 1.4],
           size=7.5, mono_cols=(4, 8), status_col=3, center_cols=(0, 2, 5, 6, 7, 9, 10, 11, 13, 14, 15))
    _note(doc, "Overlap up/down = bp shared with the previous/next amplicon. For the first "
               "and last amplicons, the missing neighbour is the circular partner across "
               "the origin. Positions are 1-based; a wrapped amplicon lists both segments.")


def _controls_section(doc, rd, n):
    _heading(doc, f"{n}. Control Primers (endogenous gene, positive control)")
    ctrls = rd['controls']
    if not ctrls:
        _note(doc, "No control primers were recorded for this project.")
        return
    rows = []
    for c in ctrls:
        rows.append((
            c['name'], c.get('target', ''), c.get('fp_sequence', ''), c.get('fp_length', ''),
            c.get('fp_tm', ''), c.get('fp_gc', ''), c.get('rp_sequence', ''),
            c.get('rp_length', ''), c.get('rp_tm', ''), c.get('rp_gc', ''),
            _fmt(c.get('expected_size')), c.get('notes', ''),
        ))
    _table(doc,
           ["Control", "Target gene", "Forward (5'→3')", "Len", "Tm\n(°C)", "GC\n(%)",
            "Reverse (5'→3')", "Len", "Tm\n(°C)", "GC\n(%)", "Expected\nsize (bp)", "Notes"],
           rows, [2.3, 2.4, 4.0, 0.9, 1.0, 0.9, 4.0, 0.9, 1.0, 0.9, 1.8, 6.6],
           size=7.5, mono_cols=(2, 6), center_cols=(3, 4, 5, 7, 8, 9, 10))


def _runs_section(doc, rd, n):
    _heading(doc, f"{n}. PCR Run Log")
    runs = rd['runs']
    if not runs:
        _note(doc, "No PCR runs were logged for this project.")
        return
    rows = []
    for r in runs:
        ctrl = ", ".join(c['name'] for c in r.get('controls', [])) or "—"
        lanes = "; ".join(f"{i + 1}: {l}" for i, l in enumerate(r.get('lane_labels') or [])) or "—"
        rows.append((r.get('run_date', ''), r.get('amplicon_num', ''), r.get('result', ''),
                     r.get('lane_number', ''), ctrl, lanes, r.get('notes', '')))
    _table(doc, ["Run date", "Amp\n#", "Result", "Lane", "Control pair(s)", "Lanes in gel", "Notes"],
           rows, [3.0, 1.1, 1.5, 1.2, 4.0, 8.0, 7.9], size=8, result_col=2, center_cols=(1, 3))


def _gel_section(doc, rd, n):
    gel_runs = [r for r in rd['runs'] if r.get('gel_image_b64')]
    if not gel_runs:
        return
    _heading(doc, f"{n}. Gel Images")
    by_amp = defaultdict(list)
    for r in gel_runs:
        by_amp[r.get('amplicon_num', '?')].append(r)
    for amp in sorted(by_amp, key=lambda x: (str(type(x)), x)):
        _heading(doc, f"Amplicon {amp}", level=2)
        items = by_amp[amp]
        for i in range(0, len(items), 3):
            chunk = items[i:i + 3]
            t = doc.add_table(rows=1, cols=3)
            t.autofit = False
            _borders(t, sz=2)
            for j in range(3):
                cell = t.rows[0].cells[j]
                cell.width = Cm(8.9)
                if j >= len(chunk):
                    continue
                r = chunk[j]
                png = _gel_png(r['gel_image_b64'])
                p = cell.paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                if png:
                    p.add_run().add_picture(png, width=Cm(8.0))
                else:
                    p.add_run("[image could not be read]").italic = True
                cap = cell.add_paragraph()
                cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                ok = r.get('result') == 'Pass'
                rr = cap.add_run(("PASS" if ok else "FAIL") +
                                 f" · Lane {r.get('lane_number', '')} · {r.get('run_date', '')}")
                rr.bold = True
                rr.font.size = Pt(8)
                rr.font.color.rgb = RGBColor.from_string('1B5E20' if ok else 'B71C1C')
                extra = []
                ctrl = ", ".join(c['name'] for c in r.get('controls', []))
                if ctrl:
                    extra.append(f"Control: {ctrl}")
                if r.get('lane_labels'):
                    extra.append("Lanes: " + ", ".join(r['lane_labels']))
                if r.get('notes'):
                    extra.append(r['notes'])
                if extra:
                    c2 = cell.add_paragraph()
                    c2.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    x = c2.add_run(" | ".join(extra))
                    x.font.size = Pt(7)
            _apply_widths(t, [8.9, 8.9, 8.9])
            doc.add_paragraph().paragraph_format.space_after = Pt(2)


def _history_section(doc, rd, n):
    hist = rd['history']
    if not hist:
        return
    _heading(doc, f"{n}. Redesign History")
    rows = [(h.get('amplicon_num', ''), h.get('failure_type', ''), h.get('attempt_num', ''),
             h.get('extension_left', ''), h.get('extension_right', ''),
             _fmt(h.get('upstream_overlap_result')), _fmt(h.get('downstream_overlap_result')),
             h.get('reason', ''), h.get('redesign_date', '')) for h in hist]
    _table(doc, ["Amp\n#", "Failure reason", "Attempt", "Ext\nleft", "Ext\nright",
                 "Overlap\nup", "Overlap\ndown", "Notes", "Date"],
           rows, [1.2, 4.0, 1.5, 1.3, 1.3, 1.8, 1.8, 9.8, 3.0], size=8,
           center_cols=(0, 2, 3, 4, 5, 6))


# ── public entry point ───────────────────────────────────────────────────────
def build_word_report(rd, return_status=False):
    """
    rd = report_data.build_report_data(...). Returns BytesIO (.docx), or
    (BytesIO, status) when return_status=True. status describes the sequence
    appendix: {'comments': int, 'comments_skipped_reason': str|None,
               'mismatches': [primer names]} (or None if no appendix).
    """
    doc = Document()
    st = doc.styles['Normal']
    st.font.name = 'Calibri'
    st.font.size = Pt(10)

    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = Cm(29.7), Cm(21.0)
    sec.left_margin = sec.right_margin = Cm(1.5)
    sec.top_margin = sec.bottom_margin = Cm(1.5)
    _footer(sec, f"{rd['meta']['project_name']} — GE-EDIT")

    opts = rd['options']
    _title_block(doc, rd)
    _params_section(doc, rd)
    _rules_section(doc, rd)

    n = 3
    if rd.get('seq_info') and rd['primers']:
        _map_section(doc, rd)
        n = 4
    _primer_section(doc, rd, n); n += 1
    if opts.get('include_controls', True):
        _controls_section(doc, rd, n); n += 1
    _runs_section(doc, rd, n); n += 1
    if opts.get('include_gels', True):
        _gel_section(doc, rd, n)
        if any(r.get('gel_image_b64') for r in rd['runs']):
            n += 1
    if opts.get('include_history', True):
        _history_section(doc, rd, n)

    status = None
    if opts.get('include_sequence', True) and rd.get('sequence') and rd.get('footprints'):
        from .word_sequence import add_sequence_appendix
        status = add_sequence_appendix(
            doc, rd, with_comments=opts.get('include_comments', True),
            author=(opts.get('author') or 'GE-EDIT'))

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return (buf, status) if return_status else buf
