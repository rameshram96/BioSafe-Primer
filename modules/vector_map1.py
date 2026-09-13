"""
Interactive CIRCULAR vector map — HTML/JS.
Backbone ring, amplicon arcs (outer ring, alternating radius bands so
labels don't collide), overlap highlight arcs between consecutive
amplicons, a distinctly colored closure-overlap arc between the last and
first amplicon (where the circular vector joins back on itself),
click-to-inspect detail panel (screen-boundary safe), searchable sequence
panel, legend and protocol rules box. GenBank/NCBI-parsed sequence
features are intentionally NOT rendered on this map.
"""

STATUS_COLORS = {
    'Done':              '#2e7d32',
    'Pending':           '#e65100',
    'Failed':            '#b71c1c',
    'Overlap Violation': '#6a1b9a',
    'Design Failed':     '#37474f',
    'Redesigned':        '#1565c0',
}
AMP_PALETTE = [
    '#4C9BE8','#E8834C','#4CE87A','#E84C4C',
    '#A04CE8','#E8D44C','#4CE8D4','#E84CA0',
    '#8CE84C','#4C4CE8','#E84C82','#4CE8B4',
]


def build_interactive_map(seq_info, primers):
    seq_len  = seq_info['length']
    sequence = seq_info.get('sequence', '')
    # Note: GenBank/NCBI-parsed features (seq_info['features']) are
    # intentionally not rendered on this map.

    amp_data = []
    for i, p in enumerate(primers):
        amp_data.append({
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
            'status_color': STATUS_COLORS.get(p.get('status','Pending'), '#78909c'),
        })

    import json
    amp_json = json.dumps(amp_data)

    # Build sequence with position markers every 10 bp
    seq_lines = []
    chunk = 60
    for i in range(0, len(sequence), chunk):
        pos    = i + 1
        seg    = sequence[i:i+chunk]
        marked = ''
        for j, base in enumerate(seg):
            abs_pos = i + j + 1
            if (abs_pos % 10) == 0:
                marked += f'<span class="pos-mark">{base}</span>'
            else:
                marked += base
        seq_lines.append(
            f'<span class="pos-label">{pos:>6}</span>  {marked}'
        )
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
svg {{ width:100%; max-width:680px; height:auto; display:block; margin:0 auto; }}

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
  line-height:1.7; text-align:center;
}}
#rules-box strong {{ color:#ffd54f; }}
</style>
</head>
<body>

<div id="map-container">
  <div id="map-title">
    🧬 {seq_info['name']} &nbsp;|&nbsp; {seq_len:,} bp (circular)
    &nbsp;|&nbsp; Click any amplicon arc for full details
    &nbsp;|&nbsp; <span style="color:#ffd54f">ESC</span> to close panel
  </div>
  <svg id="vec-svg" viewBox="0 0 620 620"
       preserveAspectRatio="xMidYMid meet"></svg>

  <div id="legend">
    <div class="legend-item"><div class="legend-dot" style="background:#2e7d32"></div>Done</div>
    <div class="legend-item"><div class="legend-dot" style="background:#e65100"></div>Pending</div>
    <div class="legend-item"><div class="legend-dot" style="background:#b71c1c"></div>Failed</div>
    <div class="legend-item"><div class="legend-dot" style="background:#6a1b9a"></div>Overlap Violation</div>
    <div class="legend-item"><div class="legend-dot" style="background:#ffd54f;height:8px;border-radius:2px"></div>Overlap region</div>
    <div class="legend-item"><div class="legend-dot" style="background:#00e5ff;height:8px;border-radius:2px"></div>Closure overlap (last ↔ first)</div>
    <div class="legend-item">▶ FP (forward, clockwise)</div>
    <div class="legend-item">◀ RP (reverse, counter-clockwise)</div>
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
const SEQ_LEN  = {seq_len};
const AMPS     = {amp_json};

// ── Circular layout geometry ──────────────────────────────────────────────
const CX = 310, CY = 310;
const R_BACKBONE  = 170;
const R_TICK_OUT  = 179;
const R_TICK_LBL  = 191;
const R_OVERLAP   = 200;        // highlight ring for consecutive overlaps
const OV_THICK    = 8;
const R_CLOSURE   = 200;        // same ring, distinct color, for last↔first
const CLOSURE_THICK = 10;
const CLOSURE_COLOR = '#00e5ff';
const R_AMP = [220, 252];       // two alternating rings so labels don't collide
const AMP_THICK   = 24;
const MIN_ARC_DEG = 2;          // minimum visible arc span (prevents invisible slivers)

function angleOf(bp) {{
  // 0 bp -> top of circle (-90deg), increases clockwise
  return (-Math.PI/2) + (bp / SEQ_LEN) * 2 * Math.PI;
}}
function pt(r, angleRad) {{
  return {{ x: CX + r*Math.cos(angleRad), y: CY + r*Math.sin(angleRad) }};
}}
function mkEl(tag, attrs) {{
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k,v] of Object.entries(attrs)) el.setAttribute(k,v);
  return el;
}}
function arcPath(r, startBp, endBp) {{
  let a0 = angleOf(startBp), a1 = angleOf(endBp);
  if (a1 <= a0) a1 += 2*Math.PI; // guard against zero/negative spans
  const spanDeg = (a1 - a0) * 180/Math.PI;
  if (spanDeg < MIN_ARC_DEG) a1 = a0 + (MIN_ARC_DEG * Math.PI/180);
  const p0 = pt(r, a0), p1 = pt(r, a1);
  const largeArc = (a1 - a0) > Math.PI ? 1 : 0;
  return `M ${{p0.x}} ${{p0.y}} A ${{r}} ${{r}} 0 ${{largeArc}} 1 ${{p1.x}} ${{p1.y}}`;
}}
function tangentDeg(angleRad) {{
  return (angleRad + Math.PI/2) * 180/Math.PI;
}}
function drawArrow(svg, r, bp, angleRad, pointsForward, color, opacity) {{
  const p = pt(r, angleRad);
  let deg = tangentDeg(angleRad);
  if (!pointsForward) deg += 180;
  const tri = mkEl('polygon', {{
    points: '0,-6 11,0 0,6',
    fill: color, opacity: opacity, 'pointer-events':'none',
    transform: `translate(${{p.x}},${{p.y}}) rotate(${{deg}})`
  }});
  svg.appendChild(tri);
}}
function placeLabel(svg, r, angleRad, text, color) {{
  let deg = tangentDeg(angleRad);
  const norm = ((deg % 360) + 360) % 360;
  if (norm > 90 && norm < 270) deg += 180; // flip so text never renders upside-down
  const p = pt(r, angleRad);
  const t = mkEl('text', {{
    x:0, y:0, 'text-anchor':'middle', 'dominant-baseline':'middle',
    fill:color, 'font-size':10, 'font-weight':'bold', 'pointer-events':'none',
    transform:`translate(${{p.x}},${{p.y}}) rotate(${{deg}})`
  }});
  t.textContent = text;
  svg.appendChild(t);
}}

function drawMap() {{
  const svg = document.getElementById('vec-svg');
  svg.innerHTML = '';

  // Backbone ring
  svg.appendChild(mkEl('circle', {{
    cx:CX, cy:CY, r:R_BACKBONE, fill:'none',
    stroke:'#4a4a6a', 'stroke-width':3
  }}));

  // Ticks + position labels (every 10%)
  for (let i=0; i<10; i++) {{
    const bp = Math.round((i/10)*SEQ_LEN);
    const a  = angleOf(bp);
    const p0 = pt(R_BACKBONE-4, a), p1 = pt(R_TICK_OUT, a);
    svg.appendChild(mkEl('line', {{
      x1:p0.x, y1:p0.y, x2:p1.x, y2:p1.y, stroke:'#6a6a8a', 'stroke-width':1
    }}));
    const lp = pt(R_TICK_LBL, a);
    const t = mkEl('text', {{
      x:lp.x, y:lp.y, 'text-anchor':'middle', 'dominant-baseline':'middle',
      fill:'#8888aa', 'font-size':9
    }});
    t.textContent = bp>=1000 ? (bp/1000).toFixed(1)+'k' : bp;
    svg.appendChild(t);
  }}
  // Origin marker (base 1)
  const originPt = pt(R_BACKBONE, angleOf(0));
  svg.appendChild(mkEl('circle', {{cx:originPt.x, cy:originPt.y, r:3.5, fill:'#ffd54f'}}));

  // Overlap highlight arcs (between consecutive amplicons)
  for (let i=0; i<AMPS.length-1; i++) {{
    const cur=AMPS[i], nxt=AMPS[i+1];
    if (cur.end > nxt.start) {{
      const path = mkEl('path', {{
        d: arcPath(R_OVERLAP, nxt.start, cur.end),
        fill:'none', stroke:'#ffd54f', 'stroke-width':OV_THICK, opacity:0.35
      }});
      svg.appendChild(path);
    }}
  }}

  // Closure overlap arc — where the circular vector joins back on itself,
  // i.e. between the LAST amplicon and the FIRST amplicon, drawn distinctly
  // from the regular (yellow) consecutive-overlap arcs above.
  if (AMPS.length > 1) {{
    const first = AMPS[0], last = AMPS[AMPS.length - 1];
    // Junction where the vector closes: last amplicon's end meets the
    // first amplicon's start (both sit at/near position 0 on the circle).
    const path = mkEl('path', {{
      d: arcPath(R_CLOSURE, last.end, first.start),
      fill:'none', stroke:CLOSURE_COLOR, 'stroke-width':CLOSURE_THICK,
      opacity:0.65, 'stroke-linecap':'round'
    }});
    svg.appendChild(path);
  }}

  // Amplicon arcs (outer, alternating rings)
  AMPS.forEach((amp, idx) => {{
    const r = R_AMP[idx % 2];
    const path = mkEl('path', {{
      d: arcPath(r, amp.start, amp.end),
      fill:'none', stroke:amp.status_color, 'stroke-width':AMP_THICK,
      'stroke-linecap':'butt', opacity:0.82, cursor:'pointer'
    }});
    path.addEventListener('mouseenter', ()=>path.setAttribute('opacity','1'));
    path.addEventListener('mouseleave', ()=>path.setAttribute('opacity','0.82'));
    path.addEventListener('click', e=>showDetail(idx, e));
    svg.appendChild(path);

    // FP / RP direction arrows at the arc ends
    drawArrow(svg, r, amp.start, angleOf(amp.start), true,  'white',   0.55);
    drawArrow(svg, r, amp.end,   angleOf(amp.end),   false, '#ff8a80', 0.65);

    // Label
    const spanDeg = ((amp.end - amp.start) / SEQ_LEN) * 360;
    if (spanDeg > 5) {{
      placeLabel(svg, r, angleOf((amp.start+amp.end)/2), `A${{amp.num}}`, '#ffffff');
    }}
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
        <span style="color:#90caf9">⬆ Upstream (with Amp ${{amp.num-1}})</span>
        <span class="ov-val">${{prevOv}}${{prevWarn}}</span>
      </div>
      <div class="overlap-row">
        <span style="color:#90caf9">⬇ Downstream (with Amp ${{amp.num+1}})</span>
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