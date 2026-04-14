"""
Interactive linear vector map — HTML/JS.
Fixes: ESC close, screen-boundary popup, min clickable width,
       enlarged close button, full sequence panel with position markers.
"""

STATUS_COLORS = {
    'Done':              '#2e7d32',
    'Pending':           '#e65100',
    'Failed':            '#b71c1c',
    'Overlap Violation': '#6a1b9a',
    'Design Failed':     '#37474f',
    'Redesigned':        '#1565c0',
}
FEATURE_COLORS = {
    'CDS':          '#1565c0', 'gene':         '#2e7d32',
    'promoter':     '#c62828', 'terminator':   '#6a1b9a',
    'rep_origin':   '#e65100', 'misc_feature': '#546e7a',
    'default':      '#78909c',
}
AMP_PALETTE = [
    '#4C9BE8','#E8834C','#4CE87A','#E84C4C',
    '#A04CE8','#E8D44C','#4CE8D4','#E84CA0',
    '#8CE84C','#4C4CE8','#E84C82','#4CE8B4',
]


def build_interactive_map(seq_info, primers):
    seq_len  = seq_info['length']
    features = seq_info.get('features', [])
    sequence = seq_info.get('sequence', '')

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
    amp_json     = json.dumps(amp_data)
    feature_json = json.dumps([{
        'label': f['label'], 'start': f['start'], 'end': f['end'],
        'color': FEATURE_COLORS.get(f['type'], FEATURE_COLORS['default'])
    } for f in features])

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
svg {{ width:100%; display:block; }}

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
  margin-top:12px; font-size:11px;
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
    🧬 {seq_info['name']} &nbsp;|&nbsp; {seq_len:,} bp
    &nbsp;|&nbsp; Click any amplicon for full details
    &nbsp;|&nbsp; <span style="color:#ffd54f">ESC</span> to close panel
  </div>
  <svg id="vec-svg" viewBox="0 0 1000 230"
       preserveAspectRatio="xMidYMid meet"></svg>

  <div id="legend">
    <div class="legend-item"><div class="legend-dot" style="background:#2e7d32"></div>Done</div>
    <div class="legend-item"><div class="legend-dot" style="background:#e65100"></div>Pending</div>
    <div class="legend-item"><div class="legend-dot" style="background:#b71c1c"></div>Failed</div>
    <div class="legend-item"><div class="legend-dot" style="background:#6a1b9a"></div>Overlap Violation</div>
    <div class="legend-item"><div class="legend-dot" style="background:#ffd54f;height:8px;border-radius:2px"></div>Overlap region</div>
    <div class="legend-item"><div class="legend-dot" style="background:#1565c0;height:8px;border-radius:2px"></div>Feature</div>
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
const FEATURES = {feature_json};
const MIN_CLICK_W = 14; // minimum px width for clickable area

function bp2x(bp) {{ return 30 + (bp / SEQ_LEN) * 940; }}

function mkEl(tag, attrs) {{
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k,v] of Object.entries(attrs)) el.setAttribute(k,v);
  return el;
}}

function drawMap() {{
  const svg = document.getElementById('vec-svg');
  svg.innerHTML = '';
  const TRACK_Y = 80, FEAT_Y = 28, AMP_Y = 115, AMP_H = 28;

  // Backbone
  svg.appendChild(mkEl('line', {{
    x1:30, y1:TRACK_Y, x2:970, y2:TRACK_Y,
    stroke:'#4a4a6a', 'stroke-width':3
  }}));

  // Ticks + labels
  for (let i=0; i<=10; i++) {{
    const bp = Math.round((i/10)*SEQ_LEN);
    const x  = bp2x(bp);
    svg.appendChild(mkEl('line',{{x1:x,y1:TRACK_Y-6,x2:x,y2:TRACK_Y+6,stroke:'#6a6a8a','stroke-width':1}}));
    const t = mkEl('text',{{x,y:TRACK_Y+18,'text-anchor':'middle',fill:'#8888aa','font-size':9}});
    t.textContent = bp>=1000?(bp/1000).toFixed(1)+'k':bp;
    svg.appendChild(t);
  }}

  // Features
  FEATURES.forEach(f => {{
    const x=bp2x(f.start), w=Math.max(3, bp2x(f.end)-bp2x(f.start));
    svg.appendChild(mkEl('rect',{{x,y:FEAT_Y-8,width:w,height:16,rx:3,fill:f.color,opacity:0.85}}));
    if(w>28){{
      const t=mkEl('text',{{x:x+w/2,y:FEAT_Y+4,'text-anchor':'middle',fill:'white','font-size':8,'font-weight':'bold','pointer-events':'none'}});
      t.textContent=f.label; svg.appendChild(t);
    }}
  }});

  // Overlap highlights
  for(let i=0;i<AMPS.length-1;i++){{
    const cur=AMPS[i], nxt=AMPS[i+1];
    const ox=bp2x(nxt.start), ow=bp2x(cur.end)-bp2x(nxt.start);
    if(ow>0) svg.appendChild(mkEl('rect',{{x:ox,y:AMP_Y-5,width:ow,height:AMP_H+10,fill:'#ffd54f',opacity:0.15,rx:2}}));
  }}

  // Amplicons
  AMPS.forEach((amp,idx) => {{
    const x   = bp2x(amp.start);
    const rawW = bp2x(amp.end) - bp2x(amp.start);
    const w   = Math.max(MIN_CLICK_W, rawW);
    const y   = AMP_Y + (idx%2)*36;

    // Block
    const rect = mkEl('rect',{{
      x,y,width:w,height:AMP_H,rx:5,
      fill:amp.status_color,opacity:0.78,
      stroke:'white','stroke-width':0.7,cursor:'pointer'
    }});
    rect.addEventListener('mouseenter',()=>rect.setAttribute('opacity','1'));
    rect.addEventListener('mouseleave',()=>rect.setAttribute('opacity','0.78'));
    rect.addEventListener('click',e=>showDetail(idx,e));
    svg.appendChild(rect);

    // FP arrow
    const fpW=Math.min(w*0.25,16);
    svg.appendChild(mkEl('polygon',{{
      points:`${{x}},${{y+AMP_H/2}} ${{x+fpW}},${{y+4}} ${{x+fpW}},${{y+AMP_H-4}}`,
      fill:'white',opacity:0.45,'pointer-events':'none'
    }}));

    // RP arrow
    svg.appendChild(mkEl('polygon',{{
      points:`${{x+w}},${{y+AMP_H/2}} ${{x+w-fpW}},${{y+4}} ${{x+w-fpW}},${{y+AMP_H-4}}`,
      fill:'#ff8a80',opacity:0.55,'pointer-events':'none'
    }}));

    // Label
    if(w>36){{
      const t=mkEl('text',{{x:x+w/2,y:y+AMP_H/2+4,'text-anchor':'middle',
        fill:'white','font-size':10,'font-weight':'bold','pointer-events':'none'}});
      t.textContent=`A${{amp.num}}`;
      svg.appendChild(t);
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
