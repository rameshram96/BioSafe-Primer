import streamlit as st
import os, sys, json
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.sequence_parser import parse_sequence, detect_format, parse_pasted_sequence
from modules.primer_design   import (design_all_primers, redesign_primers,
                                      get_redesign_recommendation,
                                      MIN_AMPLICON, MAX_AMPLICON,
                                      MIN_PRIMER_LEN, MAX_PRIMER_LEN,
                                      MAX_REDESIGN_VERSIONS)
from modules.vector_map      import build_interactive_map
from modules.project_file    import (new_project, save_project_bytes,
                                      load_project_bytes,
                                      encode_gel_image, decode_gel_image,
                                      primers_to_excel_bytes,
                                      primers_to_pdf_bytes,
                                      primers_to_summary_excel_bytes,
                                      primers_to_order_csv_bytes,
                                      get_best_primers, add_primers,
                                      update_primer_status,
                                      update_amplicon_name, add_pcr_run,
                                      add_redesign_history, assign_ids,
                                      get_project_stats)

st.set_page_config(page_title="BioSafe Primer", page_icon="🧬",
                   layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&family=Source+Code+Pro:wght@400;600&display=swap');
html,body,[class*="css"]{font-family:'Source Sans 3','Segoe UI',Arial,sans-serif !important;color:#1C1C1E;}
.stApp{background:#F7F5F2;}
[data-testid="stSidebar"]{background:#FFF;border-right:2px solid #D0D7E3;}
[data-testid="stSidebar"] *{color:#1C1C1E !important;}
.main-header{background:#0072B2;border-radius:10px;padding:20px 28px;margin-bottom:20px;
  box-shadow:0 3px 14px rgba(0,114,178,.22);display:flex;align-items:center;justify-content:space-between;}
.main-header h1{color:#FFF;font-size:1.8rem;font-weight:700;margin:0;}
.main-header p{color:#CDEAF8;font-size:.9rem;margin:4px 0 0;}
.active-proj-badge{background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.4);
  border-radius:20px;padding:5px 14px;color:white;font-size:.85rem;font-weight:600;white-space:nowrap;}
.home-box{background:#FFF;border:2px dashed #A8BACA;border-radius:12px;padding:28px 32px;margin-bottom:18px;}
.home-box h3{color:#0072B2;margin:0 0 14px;font-size:1.05rem;font-weight:700;}
.proj-banner{background:#EEF2F7;border:1.5px solid #C3CFE0;border-radius:8px;
  padding:10px 16px;margin-bottom:14px;display:flex;align-items:center;justify-content:space-between;}
.proj-banner .pname{font-weight:700;color:#0072B2;font-size:1rem;}
.proj-banner .pmeta{color:#5A6475;font-size:12px;}
.metric-card{background:#FFF;border:2px solid #D0D7E3;border-radius:10px;
  padding:14px 16px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,.06);}
.metric-card .value{font-size:1.9rem;font-weight:700;color:#0072B2;}
.metric-card .label{font-size:.72rem;color:#5A6475;text-transform:uppercase;letter-spacing:.8px;margin-top:4px;}
.metric-done .value{color:#009E73;} .metric-pending .value{color:#E69F00;} .metric-failed .value{color:#D55E00;}
.section-header{border-left:4px solid #0072B2;padding-left:12px;color:#0072B2;
  font-size:1.1rem;font-weight:600;margin:20px 0 12px;}
.upload-done{background:#E8F5E9;border:1.5px solid #009E73;border-radius:8px;
  padding:12px 16px;color:#1B4332;font-size:13px;margin-bottom:10px;}
.circ-note{background:#E3F2FD;border:1.5px solid #0072B2;border-radius:8px;
  padding:10px 16px;color:#0D47A1;font-size:12.5px;margin-bottom:10px;}
.param-confirm{background:#FFF;border:2px solid #0072B2;border-radius:10px;
  padding:16px 20px;margin:12px 0;}
.param-confirm h4{color:#0072B2;margin:0 0 10px;font-size:1rem;font-weight:700;}
.param-row{display:flex;justify-content:space-between;padding:4px 0;
  border-bottom:1px solid #EEF2F7;font-size:13px;}
.param-label{color:#5A6475;font-weight:500;}
.param-value{color:#1C1C1E;font-weight:600;}
.compact-row{background:#FFF;border:1px solid #D0D7E3;border-radius:8px;
  padding:10px 14px;margin-bottom:6px;display:flex;align-items:center;gap:12px;}
.primer-code{font-family:'Source Code Pro','Courier New',monospace !important;background:#EEF2F7;
  border-radius:6px;padding:6px 10px;font-size:12.5px;color:#1C1C1E;margin:4px 0;border-left:3px solid #0072B2;}
.primer-code.rp{border-left-color:#D55E00;}
.ov-badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600;}
.ov-ok{background:#D4EDDA;color:#155724;border:1px solid #009E73;}
.ov-fail{background:#FDECEA;color:#721C24;border:1px solid #D55E00;}
.ov-na{background:#EEF2F7;color:#5A6475;border:1px solid #C3CFE0;}
.circ-badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600;
  background:#E1F5FE;color:#01579B;border:1px solid #0288D1;}
.status-badge{display:inline-block;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700;color:white;}
.redesign-preview{background:#FFF8EC;border:2px solid #E69F00;border-radius:10px;padding:16px 20px;margin-top:12px;}
.redesign-preview h4{color:#7A4F00;margin:0 0 10px;font-size:1rem;font-weight:700;}
.split-warning{background:#FFF3CD;border:2px solid #E69F00;border-radius:8px;padding:10px 14px;margin-bottom:10px;}
.rule-pass{color:#009E73;font-weight:600;} .rule-fail{color:#D55E00;font-weight:600;}
.stTabs [data-baseweb="tab"]{color:#5A6475 !important;font-weight:500;font-size:.92rem;}
.stTabs [aria-selected="true"]{color:#0072B2 !important;border-bottom:3px solid #0072B2 !important;font-weight:700;}
.stButton>button{border-radius:7px;font-weight:600;font-family:'Source Sans 3',sans-serif !important;}
.footer-ribbon{position:fixed;bottom:0;left:0;right:0;background:#0072B2;color:#CDEAF8;
  text-align:center;font-size:11.5px;font-weight:500;padding:7px 20px;z-index:9999;
  box-shadow:0 -2px 8px rgba(0,114,178,.18);font-family:'Source Sans 3','Segoe UI',Arial,sans-serif;}
.footer-ribbon strong{color:#FFF;}
.block-container{padding-bottom:48px !important;}
</style>
""", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────────────────────────────
def footer():
    st.markdown('<div class="footer-ribbon"><strong>BioSafe Primer</strong>'
                ' &nbsp;·&nbsp; Developed and maintained by '
                '<strong>Division of Plant Physiology, ICAR-Indian Agricultural Research Institute</strong>'
                '</div>', unsafe_allow_html=True)

def fmt_ov(val):   return f"{val} bp" if val is not None else "N/A"
def ov_badge(val, mn=50):
    if val is None: return '<span class="ov-badge ov-na">N/A</span>'
    if val >= mn:   return f'<span class="ov-badge ov-ok">✔ {val} bp</span>'
    return f'<span class="ov-badge ov-fail">✖ {val} bp</span>'
def rule_check(ok, label):
    return f'<span class="{"rule-pass" if ok else "rule-fail"}">{"✅" if ok else "❌"} {label}</span>'
def amp_label(p):  return p.get('amplicon_name') or f"Amplicon_{p['amplicon_num']}"
def proj():        return st.session_state['project']

STATUS_COLORS = {
    'Pending':'#E69F00','Success':'#009E73','Failed':'#D55E00',
    'Overlap Violation':'#6a1b9a','Design Failed':'#546e7a','Redesigned':'#0072B2'
}

def status_badge(s):
    c = STATUS_COLORS.get(s, '#546e7a')
    return f'<span class="status-badge" style="background:{c}">{s}</span>'


# ── Parameter confirmation panel ─────────────────────────────────────────────
def _param_confirm_panel(max_amp, min_over, opt_tm, min_tm, max_tm):
    """Returns True if user confirms, False otherwise."""
    st.markdown("""
<div class="param-confirm">
  <h4>⚙️ Confirm Design Parameters Before Running</h4>
</div>""", unsafe_allow_html=True)

    st.markdown(
        '<div class="circ-note">🔁 <strong>Circular plasmid mode:</strong> the vector is '
        'treated as circular — the last amplicon will be designed to read through the '
        'origin and overlap Amplicon 1 by the minimum overlap set below.</div>',
        unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Amplicon**")
        st.markdown(f"Max size: **{max_amp} bp**")
        st.markdown(f"Min size: **{MIN_AMPLICON} bp**")
        st.markdown(f"Min overlap: **{min_over} bp**")
    with c2:
        st.markdown("**Melting Temperature**")
        st.markdown(f"Optimal Tm: **{opt_tm}°C**")
        st.markdown(f"Min Tm: **{min_tm}°C**")
        st.markdown(f"Max Tm: **{max_tm}°C**")
    with c3:
        st.markdown("**Primer**")
        st.markdown(f"Length: **{MIN_PRIMER_LEN}–{MAX_PRIMER_LEN} bp**")
        st.markdown(f"GC%: **40–60%**")
        st.markdown(f"Amp 1 starts: **base 1**")

    ca, cb = st.columns([1, 3])
    confirmed = ca.button("✅ Confirm & Design", type="primary", key="confirm_design")
    if cb.button("✏️ Adjust Parameters", key="adjust_params"):
        st.session_state.pop('confirm_pending', None)
        st.rerun()
    return confirmed


# ── Redesign UI ───────────────────────────────────────────────────────────────
def _redesign_ui(p):
    st.markdown("---")
    st.markdown("**🔄 Redesign Primers**")
    pk = f"rdp_{p['_id']}"

    if p.get('wraps_origin'):
        st.info("🔁 This is the final, origin-spanning amplicon of the circular vector. "
                "After redesigning, please confirm it still overlaps Amplicon 1 across "
                "the origin by at least the minimum overlap.")

    if pk in st.session_state:
        rd      = st.session_state[pk]
        ext_l   = rd['ext_l'];   ext_r = rd['ext_r']
        reason  = rd['reason'];  ft    = rd['failure_type']
        attempt = rd['attempt']
        is_split = rd.get('is_split', False)
        results  = rd['results']  # list of primer dicts (1 or 2)

        if is_split:
            st.markdown("""<div class="split-warning">
⚠️ <strong>Region exceeds 500 bp — split into 2 amplicons</strong><br>
The extended region is too large for a single amplicon. Two new overlapping
amplicons (A and B) have been designed to cover the full region with no gap.
</div>""", unsafe_allow_html=True)

        all_rules_ok = True
        for np in results:
            prev_ov = np.get('overlap_prev')
            next_ov = np.get('overlap_next')
            amp_ok   = MIN_AMPLICON <= np['amplicon_length'] <= MAX_AMPLICON
            ov_up_ok = prev_ov is None or prev_ov >= 50
            ov_dn_ok = next_ov is None or next_ov >= 50
            fp_ok    = MIN_PRIMER_LEN <= np['fp_length'] <= MAX_PRIMER_LEN
            rp_ok    = MIN_PRIMER_LEN <= np['rp_length'] <= MAX_PRIMER_LEN
            pair_ok  = amp_ok and fp_ok and rp_ok and ov_up_ok and ov_dn_ok
            if not pair_ok: all_rules_ok = False

            lbl = f"Amp {amp_label(p)}{np.get('split_label','')} v{np['version']}"
            viol_list = np.get('redesign_violations', [])
            viol_html = ('<div style="margin-top:8px;background:#FDECEA;border-radius:6px;padding:8px 10px;">'
                         + "".join(f'<div style="font-size:11px;color:#D55E00">⚠ {v}</div>' for v in viol_list)
                         + '</div>') if viol_list else (
                         '<div style="margin-top:8px;background:#D4EDDA;border-radius:6px;'
                         'padding:7px 10px;font-size:11.5px;color:#155724">✅ All rules pass</div>')
            rules_html = " | ".join([
                rule_check(amp_ok,   f"Amp {np['amplicon_length']} bp"),
                rule_check(fp_ok,    f"FP {np['fp_length']} bp"),
                rule_check(rp_ok,    f"RP {np['rp_length']} bp"),
                rule_check(ov_up_ok, "Upstream ≥50 bp"),
                rule_check(ov_dn_ok, "Downstream ≥50 bp"),
            ])
            st.markdown(f"""<div class="redesign-preview">
  <h4>📋 {lbl}</h4>
  <div style="margin-bottom:8px">{rules_html}</div>
  <div class="primer-code">FP: {np['fp_sequence']}</div>
  <div style="font-size:11px;color:#5A6475;margin:2px 0 7px 4px">
    {np['fp_length']} bp | Tm {np['fp_tm']}°C | GC {np['fp_gc']}% |
    Hairpin {np.get('fp_hairpin_tm',0)}°C | 3'Stab {np.get('fp_end_stability',0)} | Penalty {np.get('fp_penalty',0)}</div>
  <div class="primer-code rp">RP: {np['rp_sequence']}</div>
  <div style="font-size:11px;color:#5A6475;margin:2px 0 7px 4px">
    {np['rp_length']} bp | Tm {np['rp_tm']}°C | GC {np['rp_gc']}% |
    Hairpin {np.get('rp_hairpin_tm',0)}°C | 3'Stab {np.get('rp_end_stability',0)} | Penalty {np.get('rp_penalty',0)}</div>
  <div style="font-size:12px;margin-bottom:8px">
    <strong>Pos:</strong> {np['amplicon_start']}–{np['amplicon_end']} bp |
    <strong>Len:</strong> {np['amplicon_length']} bp |
    <strong>Pair Penalty:</strong> {np.get('pair_penalty',0)}</div>
  <div style="display:flex;gap:10px;align-items:center;margin-bottom:4px">
    <span style="font-size:12px;font-weight:600;color:#3A4A5C">🔼 Upstream (Amp {np['amplicon_num']-1}):</span>
    {ov_badge(prev_ov)}</div>
  <div style="display:flex;gap:10px;align-items:center">
    <span style="font-size:12px;font-weight:600;color:#3A4A5C">🔽 Downstream (Amp {np['amplicon_num']+1}):</span>
    {ov_badge(next_ov)}</div>
  {viol_html}
</div>""", unsafe_allow_html=True)

        ca, cb = st.columns(2)
        if ca.button("✅ Accept & Save", key=f"acc_{p['_id']}", type="primary", disabled=not all_rules_ok):
            for np in results:
                np['status'] = 'Pending'
                np['amplicon_name'] = amp_label(p) + np.get('split_label', '')
                np['_id'] = len(proj()['primers'])
                proj()['primers'].append(np)
            update_primer_status(proj(), p['_id'], 'Redesigned')
            add_redesign_history(proj(), p['amplicon_num'], p['_id'],
                ext_l, ext_r, reason, ft, attempt,
                results[0].get('overlap_prev'), results[-1].get('overlap_next'))
            del st.session_state[pk]
            st.success(f"✅ {'2 split amplicons' if is_split else 'New primers'} saved! Remember to 💾 Save Project.")
            if p.get('wraps_origin'):
                st.warning("🔁 Reminder: verify the redesigned amplicon still overlaps "
                           "Amplicon 1 across the plasmid origin (Rule 5).")
            st.rerun()
        if cb.button("❌ Reject & Try Again", key=f"rej_{p['_id']}"):
            del st.session_state[pk]; st.rerun()
        if not all_rules_ok:
            st.error("⛔ Fix rule violations before accepting.")
        return

    # ── Step 1: inputs ────────────────────────────────────────────────────────
    if p.get('version', 1) >= MAX_REDESIGN_VERSIONS:
        st.error(f"⛔ Maximum {MAX_REDESIGN_VERSIONS} redesign attempts reached."); return

    FOPTS = ['No band','Multiple bands','Weak band','Wrong band size',
             'Primer dimer','Overlap violation','Other']
    default_f = 'Overlap violation' if p.get('status') == 'Overlap Violation' else 'No band'
    ft  = st.selectbox("Failure reason", FOPTS, index=FOPTS.index(default_f), key=f"ftype_{p['_id']}")
    rec = get_redesign_recommendation(ft)
    st.info(f"💡 **Recommended:** {rec['note']}")

    rc1, rc2 = st.columns(2)
    ext_l = rc1.number_input("Upstream extension (bp)", 0, 200, rec['ext_left'], key=f"el_{p['_id']}",
        help="Extends search window toward vector start.")
    ext_r = rc2.number_input("Downstream extension (bp)", 0, 200, rec['ext_right'], key=f"er_{p['_id']}",
        help="Extends search window toward vector end. Does not directly control downstream overlap.")
    if ext_r > 0:
        st.warning("⚠️ Downstream extension does not guarantee downstream overlap. Check the preview.")

    # Auto-split warning
    region_len = (min(len(proj()['vector_sequence']), p['amplicon_end'] + ext_r) -
                  max(0, p['amplicon_start'] - ext_l))
    if region_len > MAX_AMPLICON:
        st.info(f"ℹ️ Extended region ({region_len} bp) exceeds 500 bp — "
                "Primer3 will still search for amplicons ≤500 bp within it. "
                "Auto-split only occurs if no valid pair is found.")

    reason = st.text_input("Additional notes (optional)",
                            placeholder="e.g. No band after 35 cycles", key=f"rsn_{p['_id']}")
    st.caption(f"Attempt {p.get('version',1)} of {MAX_REDESIGN_VERSIONS} maximum")

    if st.button("🔬 Run Redesign", key=f"red_{p['_id']}", type="primary"):
        seq  = proj()['vector_sequence']
        best = get_best_primers(proj())
        idx  = next((i for i,x in enumerate(best) if x['amplicon_num']==p['amplicon_num']), None)
        prev_end   = best[idx-1]['amplicon_end']   if idx and idx > 0 else None
        next_start = best[idx+1]['amplicon_start'] if idx is not None and idx < len(best)-1 else None

        with st.spinner("Redesigning with Primer3…"):
            result, err, is_split = redesign_primers(seq,
                p['amplicon_start'], p['amplicon_end'],
                p['amplicon_num'], ext_l, ext_r, p['version'],
                prev_amp_end=prev_end, next_amp_start=next_start)

        if result is not None:
            results = result if is_split else [result]
            st.session_state[f"rdp_{p['_id']}"] = {
                'results': results, 'is_split': is_split,
                'ext_l': ext_l, 'ext_r': ext_r,
                'reason': reason, 'failure_type': ft,
                'attempt': p.get('version',1) + 1,
            }
            st.rerun()
        else:
            st.error(f"Redesign failed — {err}")


# ── Header ────────────────────────────────────────────────────────────────────
def render_header():
    p = st.session_state.get('project')
    badge = (f'<div class="active-proj-badge">📂 {p["project_name"]} &nbsp;·&nbsp; {p["vector_length"]:,} bp</div>'
             if p else "")
    st.markdown(f"""<div class="main-header">
  <div><h1>🧬 BioSafe Primer</h1>
  <p>Overlapping PCR primer design · Progress monitoring · GMO exemption workflow</p></div>
  {badge}</div>""", unsafe_allow_html=True)

render_header()

# ══════════════════════════════════════════════════════════════════════════════
# HOME
# ══════════════════════════════════════════════════════════════════════════════
if 'project' not in st.session_state:
    st.markdown('<div class="section-header">Project Hub</div>', unsafe_allow_html=True)

    # Create New Project
    st.markdown('<div class="home-box"><h3>🆕 Create New Project</h3>', unsafe_allow_html=True)
    new_name = st.text_input("Project name", placeholder="e.g. pCAMBIA1300_GFP", key="new_name")

    input_mode = st.radio(
        "Sequence input method",
        ["📁 Upload file", "📋 Paste sequence"],
        horizontal=True, key="input_mode"
    )

    si = None
    parse_error = None

    if input_mode == "📁 Upload file":
        new_file = st.file_uploader("Upload vector sequence (FASTA or GenBank)",
                                     type=['fa','fasta','fna','gb','gbk','genbank'], key="new_file")
        if new_file and new_name:
            try:
                content = new_file.read().decode('utf-8', errors='ignore')
                fmt = detect_format(new_file.name)
                si  = parse_sequence(content, fmt)
            except Exception as e:
                parse_error = str(e)
        elif new_file and not new_name:
            st.warning("⚠️ Please enter a project name before creating.")
    else:
        pasted = st.text_area(
            "Paste FASTA, GenBank, or raw sequence text",
            height=180,
            placeholder=(">MyPlasmid\nATGCGTACGT...\n\n"
                         "— or paste full GenBank text (starting with 'LOCUS') —\n\n"
                         "— or just paste the raw sequence letters —"),
            key="pasted_seq"
        )
        if pasted.strip() and new_name:
            try:
                si = parse_pasted_sequence(pasted, new_name)
            except Exception as e:
                parse_error = str(e)
        elif pasted.strip() and not new_name:
            st.warning("⚠️ Please enter a project name before creating.")

    if parse_error:
        st.error(f"Parse error: {parse_error}")

    if si:
        st.markdown(
            '<div class="circ-note">🔁 This vector will be treated as a <strong>circular '
            'plasmid</strong> — the design step will make the last amplicon overlap '
            'Amplicon 1 across the origin.</div>', unsafe_allow_html=True)
        mc1,mc2,mc3 = st.columns(3)
        mc1.markdown(f'<div class="metric-card"><div class="value">{si["length"]:,}</div><div class="label">Vector Length (bp)</div></div>', unsafe_allow_html=True)
        mc2.markdown(f'<div class="metric-card"><div class="value">{len(si["features"])}</div><div class="label">Features</div></div>', unsafe_allow_html=True)
        mc3.markdown(f'<div class="metric-card"><div class="value">{"Pasted" if input_mode=="📋 Paste sequence" else "File"}</div><div class="label">Source</div></div>', unsafe_allow_html=True)
        st.success(f"✅ Parsed: **{si['name']}** — {si['length']:,} bp")
        if st.button("🚀 Create Project", type="primary"):
            p = new_project(new_name, si['name'], si['length'], si['sequence'], si.get('features',[]))
            st.session_state['project']  = p
            st.session_state['seq_info'] = si
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # Open Existing Project
    st.markdown("---")
    st.markdown('<div class="home-box"><h3>📂 Open Saved Project</h3>', unsafe_allow_html=True)
    bsp_file = st.file_uploader("Upload a .bsp project file", type=['bsp','json'], key="open_bsp")
    if bsp_file:
        try:
            p  = load_project_bytes(bsp_file.read())
            si = {'name':p['vector_name'],'sequence':p['vector_sequence'],
                  'length':p['vector_length'],'features':p.get('vector_features',[])}
            stats = get_project_stats(p)
            st.success(f"✅ **{p['project_name']}** — {p['vector_length']:,} bp — "
                       f"{stats['done']}/{stats['total']} amplicons done")
            if st.button("📂 Open Project", type="primary"):
                st.session_state['project']  = p
                st.session_state['seq_info'] = si
                st.rerun()
        except Exception as e:
            st.error(f"Could not load file: {e}")
    st.markdown('</div>', unsafe_allow_html=True)
    footer(); st.stop()

# ══════════════════════════════════════════════════════════════════════════════
# PROJECT WORKSPACE
# ══════════════════════════════════════════════════════════════════════════════
si    = st.session_state.get('seq_info', {})
pname = proj()['project_name']

st.markdown(f"""<div class="proj-banner">
  <div><span class="pname">📂 {pname}</span>
  <span class="pmeta">&nbsp;·&nbsp; {proj().get('vector_name','—')}
  &nbsp;·&nbsp; {proj().get('vector_length',0):,} bp
  &nbsp;·&nbsp; Created {proj().get('created_at','—')[:16]}</span></div>
</div>""", unsafe_allow_html=True)

ba, bb = st.columns([2,2])
with ba:
    if st.button("← Close Project"):
        del st.session_state['project']; st.session_state.pop('seq_info',None)
        st.session_state.pop('confirm_pending',None); st.rerun()
with bb:
    st.download_button("💾 Save Project (.bsp)", data=save_project_bytes(proj()),
        file_name=f"{pname}.bsp", mime="application/json", key="save_banner")

with st.sidebar:
    st.markdown("#### ⚙️ PCR Parameters")
    max_amp  = st.slider("Max amplicon (bp)", 300, 500, 500, 50)
    min_over = st.slider("Min overlap (bp)",   50, 150,  50, 10)
    opt_tm   = st.slider("Optimal Tm (°C)",  55.0, 65.0, 60.0, 0.5)
    min_tm   = st.slider("Min Tm (°C)",      50.0, 60.0, 58.0, 0.5)
    max_tm   = st.slider("Max Tm (°C)",      60.0, 70.0, 62.0, 0.5)
    st.markdown("---")
    st.markdown(f"**Protocol Rules**  \nAmp: {MIN_AMPLICON}–{MAX_AMPLICON} bp  \n"
                f"Primer: {MIN_PRIMER_LEN}–{MAX_PRIMER_LEN} bp  \nOverlap ≥ 50 bp  \n"
                f"Amp 1 starts at base 1  \nFull vector coverage  \n"
                f"🔁 Circular closure (last ↔ first)")

tab1,tab2,tab3,tab4,tab5 = st.tabs([
    "🔬 Design Primers","🗺️ Vector Map","📊 Progress Tracker","🧫 Gel Upload","📥 Export"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Design Primers
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown('<div class="section-header">Design Overlapping Primers</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="upload-done">✅ <strong>Vector:</strong> {proj()["vector_name"]} — '
                f'{proj()["vector_length"]:,} bp — {len(proj().get("vector_features",[]))} features</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="circ-note">🔁 <strong>Circular plasmid:</strong> primer design will '
        'make the last amplicon overlap Amplicon 1 across the origin, in addition to all '
        'the normal consecutive overlaps.</div>', unsafe_allow_html=True)
    existing = get_best_primers(proj())
    if existing: st.info(f"ℹ️ {len(existing)} amplicons already designed.")

    # ── Parameter confirmation flow ───────────────────────────────────────────
    if 'confirm_pending' not in st.session_state:
        if st.button("🚀 Design Primers", type="primary"):
            st.session_state['confirm_pending'] = True
            st.rerun()
    else:
        confirmed = _param_confirm_panel(max_amp, min_over, opt_tm, min_tm, max_tm)
        if confirmed:
            params = {'PRIMER_OPT_SIZE':20,'PRIMER_MIN_SIZE':18,'PRIMER_MAX_SIZE':25,
                      'PRIMER_OPT_TM':opt_tm,'PRIMER_MIN_TM':min_tm,'PRIMER_MAX_TM':max_tm,
                      'PRIMER_MIN_GC':40.0,'PRIMER_MAX_GC':60.0,'PRIMER_MAX_POLY_X':4,
                      'PRIMER_SALT_MONOVALENT':50.0,'PRIMER_DNA_CONC':50.0,'PRIMER_NUM_RETURN':5,
                      'PRIMER_MAX_SELF_ANY':12,'PRIMER_MAX_SELF_END':8,
                      'PRIMER_PAIR_MAX_COMPL_ANY':12,'PRIMER_PAIR_MAX_COMPL_END':8}
            with st.spinner("Designing primers with Primer3 (circular closure included)…"):
                primers, violations = design_all_primers(proj()['vector_sequence'], max_amp, min_over, params)
            assign_ids(primers)
            offset = len(proj()['primers'])
            for p in primers: p['_id'] += offset
            add_primers(proj(), primers)
            st.session_state.pop('confirm_pending', None)
            st.session_state['last_designed'] = primers

            failed = sum(1 for p in primers if p['fp_sequence']=='DESIGN_FAILED')
            st.success(f"✅ Designed **{len(primers)}** primer pairs  |  ⚠️ {failed} failed")

            last_valid = next((p for p in reversed(primers) if p['fp_sequence'] != 'DESIGN_FAILED'), None)
            if last_valid:
                if last_valid.get('wraps_origin') and last_valid.get('circular_overlap', 0) >= min_over:
                    st.success(f"🔁 Circular closure achieved: last amplicon overlaps "
                               f"Amplicon 1 by **{last_valid['circular_overlap']} bp** across the origin.")
                else:
                    st.error(f"🔁 Circular closure ❌ — last amplicon overlap with Amplicon 1 = "
                             f"{last_valid.get('circular_overlap', 0)} bp "
                             f"(minimum {min_over} bp required). Consider redesigning this amplicon.")

            ov_v = [v for v in violations if 'Rule 3' in v or 'Rule 4' in v or 'Rule 5' in v]
            ot_v = [v for v in violations if v not in ov_v]
            if ov_v:
                st.error("🚫 Overlap violations:")
                for v in ov_v: st.error(v)
            for v in ot_v: st.warning(v)
            if not violations: st.success("✅ All protocol rules passed")

            df = pd.DataFrame(primers)
            if 'amplicon_name' not in df.columns:
                df['amplicon_name'] = df['amplicon_num'].apply(lambda n: f'Amplicon_{n}')
            df['overlap_prev'] = df['overlap_prev'].apply(fmt_ov)
            df['overlap_next'] = df['overlap_next'].apply(fmt_ov)
            show = ['amplicon_num','amplicon_name','fp_sequence','fp_tm','fp_gc',
                    'fp_hairpin_tm','fp_end_stability','fp_penalty','rp_sequence',
                    'rp_tm','rp_gc','rp_hairpin_tm','rp_end_stability','rp_penalty',
                    'pair_penalty','amplicon_length','overlap_prev','overlap_next','status']
            st.dataframe(df[[c for c in show if c in df.columns]], use_container_width=True)

    # ── Post-design downloads: order sheet + long/short result files ─────────
    latest_batch = st.session_state.get('last_designed')
    if latest_batch:
        st.markdown("---")
        st.markdown("**📥 Download this design run**")
        dc1, dc2, dc3 = st.columns(3)
        with dc1:
            st.download_button(
                "🧾 Order Primers (CSV)",
                data=primers_to_order_csv_bytes(latest_batch),
                file_name=f"{pname}_order_primers.csv", mime="text/csv",
                key="dl_order_tab1",
                help="Primer Name, Sequence, Number of Bases — ready to paste into an oligo order sheet."
            )
        with dc2:
            st.download_button(
                "📄 Full Results (Excel, long format)",
                data=primers_to_excel_bytes(latest_batch, pname),
                file_name=f"{pname}_primers_full.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_long_tab1"
            )
        with dc3:
            st.download_button(
                "📋 Summary Results (Excel, short format)",
                data=primers_to_summary_excel_bytes(latest_batch, pname),
                file_name=f"{pname}_primers_summary.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_short_tab1"
            )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Vector Map
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown('<div class="section-header">Interactive Linear Vector Map (Circular Vector)</div>', unsafe_allow_html=True)
    best = get_best_primers(proj())
    if not best: st.info("No primers designed yet.")
    else:
        st.components.v1.html(build_interactive_map(si, best), height=440, scrolling=True)
        st.caption("💡 Click any amplicon for details | ESC to close | Show Sequence → Ctrl+F | "
                   "🔁 cyan highlight near position 0 = circular overlap with the last amplicon")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Progress Tracker
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown('<div class="section-header">PCR Progress Dashboard</div>', unsafe_allow_html=True)
    best = get_best_primers(proj())
    total   = len(best)
    done    = sum(1 for p in best if p['status']=='Success')
    pending = sum(1 for p in best if p['status']=='Pending')
    failed  = sum(1 for p in best if p['status'] in ('Failed','Overlap Violation'))

    c1,c2,c3,c4 = st.columns(4)
    c1.markdown(f'<div class="metric-card"><div class="value">{total}</div><div class="label">Total Amplicons</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="metric-card metric-done"><div class="value">{done}</div><div class="label">✅ Success</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="metric-card metric-pending"><div class="value">{pending}</div><div class="label">⏳ Pending</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="metric-card metric-failed"><div class="value">{failed}</div><div class="label">❌ Failed</div></div>', unsafe_allow_html=True)
    if total > 0:
        st.markdown(f"**Progress: {done}/{total} ({done/total*100:.0f}%)**")
        st.progress(done/total)

    if best:
        last = best[-1]
        if last.get('wraps_origin') and last.get('circular_overlap', 0) >= 50:
            st.markdown(f'<span class="circ-badge">🔁 Circular closure OK — '
                        f'{last["circular_overlap"]} bp overlap with Amplicon 1</span>',
                        unsafe_allow_html=True)
        else:
            st.markdown(f'<span class="circ-badge" style="background:#FDECEA;color:#721C24;'
                        f'border-color:#D55E00">🔁 Circular closure NOT satisfied — '
                        f'{last.get("circular_overlap",0)} bp (redesign Amplicon '
                        f'{last["amplicon_num"]})</span>', unsafe_allow_html=True)

    st.markdown("---")

    # ── Bulk actions ──────────────────────────────────────────────────────────
    ba1, ba2, ba3 = st.columns([2, 2, 4])
    select_all = ba1.button("☑️ Select All")
    deselect   = ba2.button("☐ Deselect All")
    mark_all_success = ba3.button("✅ Mark Selected as Success", type="primary")

    if select_all:
        for p in best:
            st.session_state[f"chk_{p['_id']}"] = True
    if deselect:
        for p in best:
            st.session_state[f"chk_{p['_id']}"] = False
    if mark_all_success:
        for p in best:
            if st.session_state.get(f"chk_{p['_id']}", False):
                update_primer_status(proj(), p['_id'], 'Success')
        st.rerun()

    st.markdown("---")

    # ── Compact rows + expanders ──────────────────────────────────────────────
    VALID_S = ['Pending','Success','Failed','Overlap Violation']
    for p in best:
        label = amp_label(p)
        col_chk, col_info, col_sel, col_btn = st.columns([0.5, 4, 2, 1.2])

        # Checkbox
        checked = col_chk.checkbox("", value=st.session_state.get(f"chk_{p['_id']}",False),
                                    key=f"chk_{p['_id']}", label_visibility="collapsed")

        # Info
        wrap_tag = " &nbsp; 🔁" if p.get('wraps_origin') else ""
        col_info.markdown(
            f"**{label}**{wrap_tag} &nbsp; v{p['version']} &nbsp;|&nbsp; "
            f"{p['amplicon_start']}–{p['amplicon_end']} bp &nbsp;|&nbsp; "
            f"{p['amplicon_length']} bp &nbsp;|&nbsp; "
            f"🔼 {fmt_ov(p.get('overlap_prev'))} &nbsp; 🔽 {fmt_ov(p.get('overlap_next'))} &nbsp;&nbsp;"
            + status_badge(p.get('status','Pending')),
            unsafe_allow_html=True
        )

        # Status dropdown
        cur = p['status'] if p['status'] in VALID_S else 'Pending'
        new_s = col_sel.selectbox("", VALID_S, index=VALID_S.index(cur),
                                   key=f"st_{p['_id']}", label_visibility="collapsed")

        # Update button
        if col_btn.button("Update", key=f"upd_{p['_id']}"):
            update_primer_status(proj(), p['_id'], new_s); st.rerun()

        # Expander for details + redesign
        with st.expander(f"🔍 Details & Redesign — {label}"):
            # Rename
            new_name = st.text_input("Amplicon name", value=label, key=f"aname_{p['_id']}")
            if st.button("Rename", key=f"rename_{p['_id']}"):
                update_amplicon_name(proj(), p['_id'], new_name)
                st.success(f"Renamed to **{new_name}**"); st.rerun()
            st.markdown("---")
            d1, d2 = st.columns([3,1])
            with d1:
                st.markdown(f'<div class="primer-code">FP: {p["fp_sequence"]}</div>', unsafe_allow_html=True)
                st.caption(f"**FP:** {p['fp_length']} bp | Tm {p['fp_tm']}°C | GC {p['fp_gc']}% | "
                           f"Hairpin {p.get('fp_hairpin_tm',0)}°C | 3'Stab {p.get('fp_end_stability',0)} | Penalty {p.get('fp_penalty',0)}")
                st.markdown(f'<div class="primer-code rp">RP: {p["rp_sequence"]}</div>', unsafe_allow_html=True)
                st.caption(f"**RP:** {p['rp_length']} bp | Tm {p['rp_tm']}°C | GC {p['rp_gc']}% | "
                           f"Hairpin {p.get('rp_hairpin_tm',0)}°C | 3'Stab {p.get('rp_end_stability',0)} | Penalty {p.get('rp_penalty',0)}")
                st.markdown(
                    f"**Pair Penalty:** {p.get('pair_penalty',0)} &nbsp;|&nbsp; "
                    f"**Amp:** {p['amplicon_length']} bp &nbsp;|&nbsp; "
                    f"🔼 Upstream: {ov_badge(p.get('overlap_prev'))} &nbsp; "
                    f"🔽 Downstream: {ov_badge(p.get('overlap_next'))}",
                    unsafe_allow_html=True)
                if p.get('wraps_origin'):
                    st.markdown(f'🔁 **Wraps plasmid origin** — overlaps Amplicon 1 by '
                                f'**{p.get("circular_overlap",0)} bp**')
            with d2:
                st.markdown(f"**Version:** v{p['version']}")
                st.markdown(f"**Position:** {p['amplicon_start']}–{p['amplicon_end']}")
            if p['status'] in ('Failed','Overlap Violation'): _redesign_ui(p)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Gel Upload
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown('<div class="section-header">Gel Image Upload & PCR Run Log</div>', unsafe_allow_html=True)
    best  = get_best_primers(proj())
    popts = {f"{amp_label(p)} (v{p['version']})": p for p in best}
    if not popts:
        st.info("No primers designed yet.")
    else:
        st.markdown("#### Log a PCR Run")
        gc1, gc2 = st.columns(2)
        with gc1:
            g_sel    = st.selectbox("Primer pair", list(popts.keys()))
            g_p      = popts[g_sel]
            g_result = st.radio("Result", ["Pass ✅","Fail ❌"], horizontal=True)
            g_lane   = st.number_input("Lane number", 1, 50, 1)
        with gc2:
            g_gel  = st.file_uploader("Gel image", type=['png','jpg','jpeg','tif'])
            g_note = st.text_area("Notes", placeholder="Band size, anomalies…")

        if st.button("💾 Save Run", type="primary"):
            gel_b64 = encode_gel_image(g_gel.read()) if g_gel else None
            g_rs    = "Pass" if "Pass" in g_result else "Fail"
            add_pcr_run(proj(), g_p['_id'], g_rs, gel_b64, g_lane, g_note,
                        g_p['amplicon_num'], g_p['fp_sequence'], g_p['rp_sequence'])
            update_primer_status(proj(), g_p['_id'], "Success" if g_rs=="Pass" else "Failed")
            st.success("✅ Run saved! Remember to 💾 Save Project."); st.rerun()

        if g_p.get('status') in ('Failed','Overlap Violation'):
            st.warning(f"⚠️ {amp_label(g_p)} is marked {g_p['status']} — redesign available below.")
            _redesign_ui(g_p)

        st.markdown("---")
        st.markdown("#### 🗂️ PCR Run Archive")
        runs = proj().get('pcr_runs', [])
        amp_nums = sorted(set(r.get('amplicon_num') for r in runs if r.get('amplicon_num')))
        filt = st.selectbox("Filter by amplicon",
                             ["All amplicons"]+[f"Amplicon {n}" for n in amp_nums], key="gel_filter")
        filtered = runs if filt=="All amplicons" else \
                   [r for r in runs if r.get('amplicon_num')==int(filt.split()[1])]
        if filtered:
            for run in filtered:
                with st.expander(f"Amplicon {run.get('amplicon_num')} — {run.get('run_date','—')} — "
                                 f"{'✅ Pass' if run.get('result')=='Pass' else '❌ Fail'}"):
                    rc1, rc2 = st.columns([2,2])
                    with rc1:
                        st.write(f"**Lane:** {run.get('lane_number','—')}")
                        st.write(f"**Notes:** {run.get('notes','—')}")
                        st.markdown(f'<div class="primer-code">FP: {run.get("fp_sequence","—")}</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="primer-code rp">RP: {run.get("rp_sequence","—")}</div>', unsafe_allow_html=True)
                    with rc2:
                        b64 = run.get('gel_image_b64')
                        if b64:
                            img_bytes = decode_gel_image(b64)
                            st.image(img_bytes, caption="Gel image", use_container_width=True)
                            st.download_button("⬇️ Download gel image", data=img_bytes,
                                file_name=f"gel_amp{run.get('amplicon_num','')}_lane{run.get('lane_number','')}.png",
                                mime="image/png", key=f"dl_gel_{run.get('id','')}")
                        else:
                            st.caption("No gel image uploaded.")
        else:
            st.info("No runs logged yet.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — Export
# ══════════════════════════════════════════════════════════════════════════════
with tab5:
    st.markdown('<div class="section-header">Export Results</div>', unsafe_allow_html=True)
    all_primers = proj().get('primers',[])
    best_primers = get_best_primers(proj())
    pcr_runs    = proj().get('pcr_runs',[])

    st.markdown("#### 💾 Save Project File")
    st.download_button("⬇️ Download .bsp project file", data=save_project_bytes(proj()),
        file_name=f"{pname}.bsp", mime="application/json",
        help="Complete project — open next session to resume.")
    st.caption("Contains everything: primers, gel images (embedded), PCR runs, redesign history.")

    st.markdown("---")
    st.markdown("#### 📊 Result Files")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("📊 Generate Full Excel (long format)", type="primary"):
            buf = primers_to_excel_bytes(all_primers, pname)
            st.download_button("⬇️ Download Full Excel", data=buf,
                file_name=f"{pname}_primers_full.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_excel")
    with c2:
        if st.button("📋 Generate Summary Excel (short format)"):
            buf = primers_to_summary_excel_bytes(best_primers, pname)
            st.download_button("⬇️ Download Summary Excel", data=buf,
                file_name=f"{pname}_primers_summary.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_summary_excel")
    with c3:
        if st.button("🧾 Generate Order Primers (CSV)"):
            buf = primers_to_order_csv_bytes(best_primers)
            st.download_button("⬇️ Download Order CSV", data=buf,
                file_name=f"{pname}_order_primers.csv", mime="text/csv",
                key="dl_order_csv")
    with c4:
        if st.button("📄 Generate PDF Report"):
            buf = primers_to_pdf_bytes(pname, all_primers, pcr_runs)
            st.download_button("⬇️ Download PDF", data=buf,
                file_name=f"{pname}_report.pdf", mime="application/pdf", key="dl_pdf")

    st.caption("**Full Excel** = every field currently tracked (long format). "
               "**Summary Excel** = Amplicon No, Amplicon Name, FP/RP sequence, GC%, Tm, "
               "amplicon length, overlap_prev, overlap_next (short format). "
               "**Order CSV** = one row per primer — Primer Name, Sequence, Number of Bases.")

    history = proj().get('redesign_history',[])
    if history:
        st.markdown("---")
        st.markdown("#### 🔄 Redesign History")
        df = pd.DataFrame(history)
        show_h = ['amplicon_num','failure_type','attempt_num','extension_left','extension_right',
                  'upstream_overlap_result','downstream_overlap_result','reason','redesign_date']
        st.dataframe(df[[c for c in show_h if c in df.columns]], use_container_width=True)

footer()
