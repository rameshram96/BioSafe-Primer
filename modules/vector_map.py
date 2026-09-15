"""
Interactive circular vector map — HTML/JS/SVG.
Amplicons only (no separate feature ring), drawn as two alternating
concentric bands so overlapping amplicons never visually collide.
Labels sit outside the ring on leader lines (SnapGene-style).
Base 1 is at 12 o'clock, increasing clockwise.
"""
import json
import math

STATUS_COLORS = {
    'Done':              '#2e7d32',
    'Pending':           '#e65100',
    'Failed':            '#b71c1c',
    'Overlap Violation': '#6a1b9a',
    'Design Failed':     '#37474f',
    'Redesigned':        '#1565c0',
}
AMP_PALETTE = [
    '#4C9BE8', '#E8834C', '#4CE87A', '#E84C4C',
    '#A04CE8', '#E8D44C', '#4CE8D4', '#E84CA0',
    '#8CE84C', '#4C4CE8', '#E84C82', '#4CE8B4',
]

# ── Geometry constants (viewBox is 800 x 800, center at 400,400) ──────────────
CX, CY        = 400, 400
RING_A_OUTER, RING_A_INNER = 300, 260   # even-index amplicons (outer band)
RING_B_OUTER, RING_B_INNER = 248, 208   # odd-index amplicons (inner band)
BACKBONE_R    = 322                     # thin reference circle + ticks
TICK_OUT_R    = 334
TICK_LABEL_R  = 348
LEADER_END_R  = 360                     # where leader lines terminate
LABEL_TEXT_R  = 372                     # where the text sits


def _polar(r, angle_deg):
    """Point on a circle of radius r at angle_deg measured clockwise from top."""
    rad = math.radians(angle_deg)
    x = CX + r * math.sin(rad)
    y = CY - r * math.cos(rad)
    return x, y


def build_interactive_map(seq_info, primers):
    seq_len  = seq_info['length']
    sequence = seq_info.get('sequence', '')

    amp_data = []
    for i, p in enumerate(primers):
        amp_data.append({
            'idx':          i,
            'num':          p['amplicon_num'],
            'start':        p['amplicon_start'],
            'end':          p['amplicon_end'],
            'length':       p['amplicon_length'],
            'fp_seq':       p['fp_sequence'],
            'rp_seq':       p['rp_sequence'],
            'fp_len':       p['fp_length'],
            'rp_len':       p['rp_length'],
            'fp_tm':        p['fp_tm'],
            'rp_tm':        p['rp_tm'],
            'fp_gc':        p['fp_gc'],
            'rp_gc':        p['rp_gc'],
            'fp_hairpin':   p.get('fp_hairpin_tm', 0),
            'rp_hairpin':   p.get('rp_hairpin_tm', 0),
            'fp_end_stab':  p.get('fp_end_stability', 0),
            'rp_end_stab':  p.get('rp_end_stability', 0),
            'fp_penalty':   p.get('fp_penalty', 0),
            'rp_penalty':   p.get('rp_penalty', 0),
            'pair_penalty': p.get('pair_penalty', 0),
            'status':       p.get('status', 'Pending'),
            'version':      p.get('version', 1),
            'name':         p.get('amplicon_name', f'Amplicon_{p["amplicon_num"]}'),
            'overlap_prev': p.get('overlap_prev'),
            'overlap_next': p.get('overlap_next'),
            'color':        AMP_PALETTE[i % len(AMP_PALETTE)],
            'status_color': STATUS_COLORS.get(p.get('status', 'Pending'), '#78909c'),
        })

    amp_json = json.dumps(amp_data)

    # Sequence panel with position markers every 10 bp (unchanged behaviour)
    seq_lines = []
    chunk = 60
    for i in range(0, len(sequence), chunk):
        pos    = i + 1
        seg    = sequence[i:i + chunk]
        marked = ''
        for j, base in enumerate(seg):
            abs_pos = i + j + 1
            if (abs_pos % 10) == 0:
                marked += f'<span class="pos-mark">{base}</span>'
            else:
                marked += base
        seq_lines.append(f'<span class="pos-label">{pos:>6}</span>  {marked}')
    seq_html = '\n'.join(seq_lines)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{
  background:#0f0f23; font-family:'Segoe UI',sans-serif;
  color:#e0e0e0; padding:12px;
}}
#map-container {{
  background:#1a1a2e; border:1px solid #3949ab;
  border-radius:10px; padding:16px; position:relative;
}}
#map-title {{
  color:#90caf9; font-size:13px; font-weight:600;
  margin-bottom:12px; letter-spacing:0.5px;
}}
#svg-wrap {{ display:flex; justify-content:center; }}
svg {{ width:100%; max-width:640px; display:block; }}

/* ── Detail Panel ── */
#detail-panel {{
  display:none; position:fixed;
  background:#1e2140; border:2px solid #3949ab;
  border-radius:12px; padding:20px 22px 16px;
  min-width:360px; max-width:460px;
  box-shadow:0 8px 40px rgba(0,0,0,0.7);
  z-index:9999; font-size:12.5px;
  max-height:85vh; overflow-y:auto;
}}
#detail-panel h3 {{
  color:#64b5f6; font-size:14px; margin-bottom:10px;
  border-bottom:1px solid #3949ab; padding-bottom:6px;
  padding-right:28px;
}}
#close-btn {{
  position:absolute; top:12px; right:14px;
  cursor:pointer; color:#90caf9;
  font-size:22px; font-weight:bold; line-height:1;
  width:28px; height:28px; display:flex;
  align-items:center; justify-content:center;
  border-radius:50%; background:#252550;
  border:1px solid #3949ab; transition:all 0.15s;
}}
#close-btn:hover {{ background:#b71c1c; color:white; border-color:#b71c1c; }}
.section-title {{
  color:#ffd54f; font-size:11px; font-weight:700;
  text-transform:uppercase; letter-spacing:0.8px;
  margin:10px 0 4px; padding-bottom:2px;
  border-bottom:1px solid #2a2a50;
}}
.detail-row {{
  display:flex; justify-content:space-between;
  padding:3px 0; border-bottom:1px solid #1a1a35;
}}
.detail-label {{ color:#90caf9; font-weight:500; }}
.detail-value {{
  color:#e0e0e0; font-family:monospace; font-size:11.5px;
  max-width:260px; word-break:break-all; text-align:right;
}}
.status-badge {{
  display:inline-block; padding:2px 10px;
  border-radius:12px; font-size:11px; font-weight:700; color:white;
}}
.overlap-box {{
  margin-top:8px; background:#1a1a35;
  border:1px solid #3949ab; border-radius:6px; padding:8px 10px;
}}
.overlap-row {{
  display:flex; justify-content:space-between;
  padding:3px 0; font-size:12px;
}}
.ov-val {{ color:#ffd54f; font-weight:700; font-family:monospace; }}
.warn {{ color:#ff8a80; }}

/* ── Sequence Panel ── */
#seq-toggle {{
  margin-top:12px; background:#252547;
  border:1px solid #3949ab; border-radius:6px;
  padding:7px 14px; cursor:pointer; font-size:12px;
  color:#90caf9; font-weight:600; display:inline-block;
  user-select:none;
}}
#seq-toggle:hover {{ background:#1a237e; }}
#seq-panel {{
  display:none; margin-top:8px;
  background:#0d0d1a; border:1px solid #2a2a50;
  border-radius:6px; padding:12px 14px;
  max-height:260px; overflow-y:auto;
  font-family:'Courier New',monospace; font-size:12px;
  line-height:1.9; color:#c8e6c9; white-space:pre;
  user-select:text; -webkit-user-select:text;
}}
.pos-label {{ color:#546e7a; font-size:10px; }}
.pos-mark  {{ color:#ffd54f; font-weight:bold; }}

/* ── Legend ── */
#legend {{
  display:flex; flex-wrap:wrap; gap:10px;
  margin-top:12px; font-size:11px; justify-content:center;
}}
.legend-item {{ display:flex; align-items:center; gap:5px; }}
.legend-dot  {{ width:12px; height:12px; border-radius:3px; flex-shrink:0; }}

/* ── Protocol rules ── */
#rules-box {{
  margin-top:10px; background:#12122a;
  border:1px solid #3949ab; border-radius:6px;
  padding:8px 12px; font-size:11px; color:#90caf9;
  line-height:1.7;
}}
#rules-box strong {{ color:#ffd54f; }}
</style>
</head>
<body>

<div id="map-container">
  <div id="map-title">
    🧬 {seq_info['name']} &nbsp;|&nbsp; {seq_len:,} bp (circular)
    &nbsp;|&nbsp; Click any amplicon for full details
    &nbsp;|&nbsp; <span style="color:#ffd54f">ESC</span> to close panel
  </div>
  <div id="svg-wrap">
    <svg id="vec-svg" viewBox="0 0 800 800"
         preserveAspectRatio="xMidYMid meet"></svg>
  </div>

  <div id="legend">
    <div class="legend-item"><div class="legend-dot" style="background:#2e7d32"></div>Done</div>
    <div class="legend-item"><div class="legend-dot" style="background:#e65100"></div>Pending</div>
    <div class="legend-item"><div class="legend-dot" style="background:#b71c1c"></div>Failed</div>
    <div class="legend-item"><div class="legend-dot" style="background:#6a1b9a"></div>Overlap Violation</div>
    <div class="legend-item"><div class="legend-dot" style="background:#ffd54f;height:8px;border-radius:2px"></div>Overlap region</div>
    <div class="legend-item"><div class="legend-dot" style="background:white;height:8px;border-radius:8px;opacity:.6"></div>FP end</div>
    <div class="legend-item"><div class="legend-dot" style="background:#ff8a80;height:8px;border-radius:8px;opacity:.8"></div>RP end</div>
  </div>

  <div id="rules-box">
    <strong>Active Protocol Rules:</strong> &nbsp;
    Amplicon size: 150–500 bp &nbsp;|&nbsp;
    Min overlap: 50 bp &nbsp;|&nbsp;
    Primer length: 18–25 bp &nbsp;|&nbsp;
    Amplicon 1 must start at base 1 &nbsp;|&nbsp;
    Full vector coverage required
  </div>

  <div id="seq-toggle" onclick="toggleSeq()">
    🔍 Show Vector Sequence (Ctrl+F searchable)
  </div>
  <div id="seq-panel">{seq_html}</div>
</div>

<!-- Detail panel -->
<div id="detail-panel">
  <div id="close-btn" onclick="closePanel()" title="Close (ESC)">✕</div>
  <h3 id="dp-title"></h3>
  <div id="dp-body"></div>
</div>

<script>
const SEQ_LEN = {seq_len};
const AMPS    = {amp_json};

const CX = 400, CY = 400;
const RING_A_OUTER = 300, RING_A_INNER = 260;   // even-index amplicons
const RING_B_OUTER = 248, RING_B_INNER = 208;   // odd-index amplicons
const BACKBONE_R   = 322;
const TICK_OUT_R   = 334;
const TICK_LABEL_R = 348;
const LEADER_END_R = 360;
const LABEL_TEXT_R = 372;

function bp2angle(bp) {{ return (bp / SEQ_LEN) * 360.0; }}

function polar(r, angleDeg) {{
  const rad = angleDeg * Math.PI / 180;
  return {{ x: CX + r * Math.sin(rad), y: CY - r * Math.cos(rad) }};
}}

function mkEl(tag, attrs) {{
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
}}

function ringFor(idx) {{
  return (idx % 2 === 0)
    ? {{ outer: RING_A_OUTER, inner: RING_A_INNER }}
    : {{ outer: RING_B_OUTER, inner: RING_B_INNER }};
}}

// Donut-segment path from angle a1 -> a2 (degrees, a2 > a1), radii rOuter/rInner
function arcPath(a1, a2, rOuter, rInner) {{
  const span = a2 - a1;
  const largeArc = span > 180 ? 1 : 0;
  const p1 = polar(rOuter, a1), p2 = polar(rOuter, a2);
  const p3 = polar(rInner, a2), p4 = polar(rInner, a1);
  return `M ${{p1.x}} ${{p1.y}} A ${{rOuter}} ${{rOuter}} 0 ${{largeArc}} 1 ${{p2.x}} ${{p2.y}} `
       + `L ${{p3.x}} ${{p3.y}} A ${{rInner}} ${{rInner}} 0 ${{largeArc}} 0 ${{p4.x}} ${{p4.y}} Z`;
}}

function drawMap() {{
  const svg = document.getElementById('vec-svg');
  svg.innerHTML = '';

  // Backbone circle
  svg.appendChild(mkEl('circle', {{
    cx: CX, cy: CY, r: BACKBONE_R, fill: 'none',
    stroke: '#4a4a6a', 'stroke-width': 2
  }}));

  // Position ticks every 10% + start marker
  for (let i = 0; i < 10; i++) {{
    const bp = Math.round((i / 10) * SEQ_LEN);
    const ang = bp2angle(bp);
    const p1  = polar(BACKBONE_R, ang);
    const p2  = polar(TICK_OUT_R, ang);
    svg.appendChild(mkEl('line', {{
      x1: p1.x, y1: p1.y, x2: p2.x, y2: p2.y,
      stroke: '#6a6a8a', 'stroke-width': 1
    }}));
    const pt = polar(TICK_LABEL_R, ang);
    const t = mkEl('text', {{
      x: pt.x, y: pt.y, 'text-anchor': 'middle',
      'dominant-baseline': 'middle', fill: '#8888aa', 'font-size': 9
    }});
    t.textContent = bp >= 1000 ? (bp / 1000).toFixed(1) + 'k' : bp;
    svg.appendChild(t);
  }}
  // Base-1 marker at top
  const top = polar(BACKBONE_R - 6, 0);
  const tTop = mkEl('text', {{
    x: top.x, y: top.y - 8, 'text-anchor': 'middle', fill: '#ffd54f', 'font-size': 9, 'font-weight': 'bold'
  }});
  tTop.textContent = '1 bp';
  svg.appendChild(tTop);

  // Overlap highlights (span full band, both rings, at the junction angle range)
  for (let i = 0; i < AMPS.length - 1; i++) {{
    const cur = AMPS[i], nxt = AMPS[i + 1];
    const ov = cur.end - nxt.start;
    if (ov > 0) {{
      const a1 = bp2angle(nxt.start), a2 = bp2angle(cur.end);
      const path = arcPath(a1, a2, RING_A_OUTER, RING_B_INNER);
      svg.appendChild(mkEl('path', {{
        d: path, fill: '#ffd54f', opacity: 0.18
      }}));
    }}
  }}

  // Amplicon arcs
  AMPS.forEach((amp) => {{
    const ring = ringFor(amp.idx);
    let a1 = bp2angle(amp.start), a2 = bp2angle(amp.end);
    if (a2 <= a1) a2 += 0.5; // guard against zero-width arcs

    const path = mkEl('path', {{
      d: arcPath(a1, a2, ring.outer, ring.inner),
      fill: amp.status_color, opacity: 0.82,
      stroke: 'white', 'stroke-width': 0.7, cursor: 'pointer'
    }});
    path.addEventListener('mouseenter', () => path.setAttribute('opacity', '1'));
    path.addEventListener('mouseleave', () => path.setAttribute('opacity', '0.82'));
    path.addEventListener('click', e => showDetail(amp.idx, e));
    svg.appendChild(path);

    // FP marker (white dot, start of arc) / RP marker (red dot, end of arc)
    const midR = (ring.outer + ring.inner) / 2;
    const fpP = polar(midR, a1), rpP = polar(midR, a2);
    svg.appendChild(mkEl('circle', {{
      cx: fpP.x, cy: fpP.y, r: 4, fill: 'white', opacity: 0.75, 'pointer-events': 'none'
    }}));
    svg.appendChild(mkEl('circle', {{
      cx: rpP.x, cy: rpP.y, r: 4, fill: '#ff8a80', opacity: 0.85, 'pointer-events': 'none'
    }}));

    // Leader line + outside label
    const midAngle = (a1 + a2) / 2;
    const leaderStart = polar(ring.outer, midAngle);
    const leaderEnd   = polar(LEADER_END_R, midAngle);
    svg.appendChild(mkEl('line', {{
      x1: leaderStart.x, y1: leaderStart.y, x2: leaderEnd.x, y2: leaderEnd.y,
      stroke: amp.color, 'stroke-width': 1, opacity: 0.8, 'pointer-events': 'none'
    }}));
    const labelPt = polar(LABEL_TEXT_R, midAngle);
    const anchor = labelPt.x >= CX - 1 ? 'start' : 'end';
    const label = mkEl('text', {{
      x: labelPt.x, y: labelPt.y, 'text-anchor': anchor,
      'dominant-baseline': 'middle', fill: '#e0e0e0', 'font-size': 10,
      'font-weight': 'bold', 'pointer-events': 'none'
    }});
    label.textContent = `A${{amp.num}}`;
    svg.appendChild(label);
  }});
}}

function showDetail(idx, evt) {{
  const amp = AMPS[idx];
  document.getElementById('dp-title').textContent =
    `${{amp.name}}  ·  v${{amp.version}}  ·  ${{amp.status}}`;

  const prevOv = amp.overlap_prev != null
    ? `${{amp.overlap_prev}} bp` : 'N/A (first amplicon)';
  const nextOv = amp.overlap_next != null
    ? `${{amp.overlap_next}} bp` : 'N/A (last amplicon)';
  const prevWarn = (amp.overlap_prev != null && amp.overlap_prev < 50)
    ? ' <span class="warn">⚠ below 50 bp</span>' : '';
  const nextWarn = (amp.overlap_next != null && amp.overlap_next < 50)
    ? ' <span class="warn">⚠ below 50 bp</span>' : '';

  document.getElementById('dp-body').innerHTML = `
    <div class="section-title">📍 Amplicon Info</div>
    <div class="detail-row">
      <span class="detail-label">Position</span>
      <span class="detail-value">${{amp.start}} – ${{amp.end}} bp</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">Length</span>
      <span class="detail-value">${{amp.length}} bp</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">Status</span>
      <span class="detail-value">
        <span class="status-badge" style="background:${{amp.status_color}}">${{amp.status}}</span>
      </span>
    </div>

    <div class="section-title">➡ Forward Primer</div>
    <div class="detail-row">
      <span class="detail-label">Sequence (5'→3')</span>
      <span class="detail-value">${{amp.fp_seq}}</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">Length / Tm / GC%</span>
      <span class="detail-value">${{amp.fp_len}} bp · ${{amp.fp_tm}}°C · ${{amp.fp_gc}}%</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">Hairpin Tm</span>
      <span class="detail-value">${{amp.fp_hairpin}}°C</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">3' End Stability (ΔG)</span>
      <span class="detail-value">${{amp.fp_end_stab}} kcal/mol</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">Penalty Score</span>
      <span class="detail-value">${{amp.fp_penalty}}</span>
    </div>

    <div class="section-title">⬅ Reverse Primer</div>
    <div class="detail-row">
      <span class="detail-label">Sequence (5'→3')</span>
      <span class="detail-value">${{amp.rp_seq}}</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">Length / Tm / GC%</span>
      <span class="detail-value">${{amp.rp_len}} bp · ${{amp.rp_tm}}°C · ${{amp.rp_gc}}%</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">Hairpin Tm</span>
      <span class="detail-value">${{amp.rp_hairpin}}°C</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">3' End Stability (ΔG)</span>
      <span class="detail-value">${{amp.rp_end_stab}} kcal/mol</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">Penalty Score</span>
      <span class="detail-value">${{amp.rp_penalty}}</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">Pair Penalty</span>
      <span class="detail-value">${{amp.pair_penalty}}</span>
    </div>

    <div class="overlap-box">
      <div class="section-title" style="margin-top:0">⬌ Overlap Coverage</div>
      <div class="overlap-row">
        <span style="color:#90caf9">⬆ Upstream (with Amp ${{amp.num - 1}})</span>
        <span class="ov-val">${{prevOv}}${{prevWarn}}</span>
      </div>
      <div class="overlap-row">
        <span style="color:#90caf9">⬇ Downstream (with Amp ${{amp.num + 1}})</span>
        <span class="ov-val">${{nextOv}}${{nextWarn}}</span>
      </div>
    </div>
  `;

  const panel = document.getElementById('detail-panel');
  panel.style.display = 'block';

  // Screen-boundary safe positioning
  const PW = 460, PH = 520;
  let px = evt.clientX + 12;
  let py = evt.clientY + 12;
  if (px + PW > window.innerWidth  - 10) px = evt.clientX - PW - 12;
  if (py + PH > window.innerHeight - 10) py = evt.clientY - PH - 12;
  if (px < 5) px = 5;
  if (py < 5) py = 5;
  panel.style.left = px + 'px';
  panel.style.top  = py + 'px';
}}

function closePanel() {{
  document.getElementById('detail-panel').style.display = 'none';
}}

function toggleSeq() {{
  const p = document.getElementById('seq-panel');
  const b = document.getElementById('seq-toggle');
  if (p.style.display === 'block') {{
    p.style.display = 'none';
    b.textContent   = '🔍 Show Vector Sequence (Ctrl+F searchable)';
  }} else {{
    p.style.display = 'block';
    b.textContent   = '🔼 Hide Vector Sequence';
  }}
}}

// ESC key closes panel
document.addEventListener('keydown', e => {{
  if (e.key === 'Escape') closePanel();
}});

// Click outside panel closes it
document.addEventListener('click', e => {{
  const panel = document.getElementById('detail-panel');
  if (!panel.contains(e.target) && !e.target.closest('svg') &&
      !e.target.closest('#close-btn'))
    closePanel();
}});

drawMap();
window.addEventListener('resize', drawMap);
</script>
</body>
</html>"""
    return html


def save_interactive_map(seq_info, primers, output_path):
    html = build_interactive_map(seq_info, primers)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return output_path


# ══════════════════════════════════════════════════════════════════════════
# Static circular map (matplotlib PNG) — for embedding in the PDF report.
# Mirrors the styling of the interactive map: alternating amplicon bands,
# colored arcs, base-1 marker, tick marks, leader-line labels.
# ══════════════════════════════════════════════════════════════════════════
def build_static_circular_map_png(seq_info, primers, dpi=150):
    """
    Render a static circular vector map as a PNG (matplotlib), for
    embedding in the PDF report. `primers` should be the deduped/"best"
    list (one entry per amplicon), non-failed only.
    Returns a BytesIO containing PNG bytes.
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon
    from io import BytesIO

    seq_len = seq_info['length']

    def bp2angle(bp):
        return (bp / seq_len) * 360.0 if seq_len else 0.0

    def arc_points(a1, a2, r_outer, r_inner, n=48):
        pts = []
        for i in range(n + 1):
            a = a1 + (a2 - a1) * i / n
            pts.append(_polar(r_outer, a))
        for i in range(n + 1):
            a = a2 - (a2 - a1) * i / n
            pts.append(_polar(r_inner, a))
        return pts

    n_amps = len(primers)

    # ── Anti-overlap label layout ────────────────────────────────────────────
    # With many amplicons packed around the circle, fixed-radius horizontal
    # labels collide with their neighbours. Two independent measures fix
    # this: (1) stagger the label radius per amplicon (near/far, matching
    # the existing near/far arc-ring alternation) so adjacent labels are
    # not competing for the same horizontal band, and (2) shrink font size
    # as amplicon count grows, since angular spacing per label shrinks too.
    label_r_near  = LABEL_TEXT_R
    label_r_far   = LABEL_TEXT_R + 34
    leader_r_near = LEADER_END_R
    leader_r_far  = LEADER_END_R + 26

    if n_amps <= 8:
        label_fontsize = 8.5
    elif n_amps <= 14:
        label_fontsize = 7.0
    elif n_amps <= 22:
        label_fontsize = 5.8
    else:
        label_fontsize = 4.8

    # Canvas needs extra room for the staggered "far" label ring plus the
    # widest label text; expand the plotted bounds symmetrically instead of
    # keeping the tight 0-800 box the interactive (screen) map uses.
    PAD = 60
    XLIM = (0 - PAD, 800 + PAD)
    YLIM = (0 - PAD, 800 + PAD)

    fig, ax = plt.subplots(figsize=(9, 9), dpi=dpi)
    ax.set_xlim(*XLIM)
    ax.set_ylim(*YLIM)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.invert_yaxis()  # match the clockwise-from-top convention of _polar()

    # Backbone circle
    theta = list(range(0, 361, 2))
    bx = [CX + BACKBONE_R * math.sin(math.radians(t)) for t in theta]
    by = [CY - BACKBONE_R * math.cos(math.radians(t)) for t in theta]
    ax.plot(bx, by, color='#37474f', linewidth=1.2, zorder=1)

    # Position ticks every 10% of the vector
    for i in range(10):
        bp  = round((i / 10) * seq_len)
        ang = bp2angle(bp)
        p1  = _polar(BACKBONE_R, ang)
        p2  = _polar(TICK_OUT_R, ang)
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color='#607d8b', linewidth=1, zorder=1)
        pt  = _polar(TICK_LABEL_R, ang)
        lbl = f"{bp/1000:.1f}k" if bp >= 1000 else str(bp)
        ax.text(pt[0], pt[1], lbl, ha='center', va='center', fontsize=7, color='#455a64')

    # Base-1 marker at top
    top = _polar(BACKBONE_R - 6, 0)
    ax.text(top[0], top[1] - 10, '1 bp', ha='center', va='center',
             fontsize=8, color='#b8860b', fontweight='bold')

    # Overlap highlights between consecutive amplicons
    for i in range(len(primers) - 1):
        cur, nxt = primers[i], primers[i + 1]
        ov = cur['amplicon_end'] - nxt['amplicon_start']
        if ov > 0:
            a1 = bp2angle(nxt['amplicon_start'])
            a2 = bp2angle(cur['amplicon_end'])
            poly = Polygon(arc_points(a1, a2, RING_A_OUTER, RING_B_INNER),
                            closed=True, facecolor='#ffd54f', alpha=0.25,
                            edgecolor='none', zorder=2)
            ax.add_patch(poly)

    # Amplicon arcs, alternating bands + leader-line labels
    for i, p in enumerate(primers):
        ring_outer, ring_inner = (
            (RING_A_OUTER, RING_A_INNER) if i % 2 == 0
            else (RING_B_OUTER, RING_B_INNER)
        )
        a1 = bp2angle(p['amplicon_start'])
        a2 = bp2angle(p['amplicon_end'])
        if a2 <= a1:
            a2 += 0.5
        color = AMP_PALETTE[i % len(AMP_PALETTE)]

        poly = Polygon(arc_points(a1, a2, ring_outer, ring_inner), closed=True,
                        facecolor=color, edgecolor='white', linewidth=0.8,
                        alpha=0.9, zorder=3)
        ax.add_patch(poly)

        mid_angle = (a1 + a2) / 2

        # Stagger both the leader length and label radius by parity so
        # neighbouring amplicon labels sit on two different concentric
        # "reading rings" instead of piling onto one, which is what caused
        # overlapping text for vectors with several amplicons.
        leader_r = leader_r_near if i % 2 == 0 else leader_r_far
        label_r  = label_r_near  if i % 2 == 0 else label_r_far

        leader_start = _polar(ring_outer, mid_angle)
        leader_mid   = _polar(leader_r, mid_angle)
        ax.plot([leader_start[0], leader_mid[0]], [leader_start[1], leader_mid[1]],
                color=color, linewidth=1, alpha=0.85, zorder=2)

        label_pt = _polar(label_r, mid_angle)
        ha = 'left' if label_pt[0] >= CX - 1 else 'right'
        name = p.get('amplicon_name') or f"Amplicon_{p['amplicon_num']}"
        ax.text(label_pt[0], label_pt[1], name, ha=ha, va='center',
                fontsize=label_fontsize, fontweight='bold', color='#263238',
                zorder=4,
                bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                          edgecolor='none', alpha=0.72))

    ax.text(CX, 20, f"{seq_info.get('name', 'Vector')}  ({seq_len:,} bp, circular)",
            ha='center', va='center', fontsize=11, fontweight='bold', color='#1A237E')

    buf = BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buf.seek(0)
    return buf
