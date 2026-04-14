import streamlit as st
import os, sys, json
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

from modules.database import (
    init_db, save_project, get_all_projects, get_project, delete_project,
    save_primers, get_primers_by_project, update_primer_status,
    update_amplicon_name, get_project_stats, save_pcr_run,
    get_pcr_runs_by_project, save_redesign_history, get_redesign_history,
    get_user_by_email,
)
from modules.auth import (
    get_session_user, set_session_user, logout,
    login_with_password, register_with_password,
    get_google_auth_url, handle_google_callback, login_with_google,
    google_is_configured,
)
from modules.sequence_parser import parse_sequence, detect_format
from modules.primer_design import (
    design_all_primers, redesign_primers,
    get_redesign_recommendation,
    MIN_AMPLICON, MAX_AMPLICON,
    MIN_PRIMER_LEN, MAX_PRIMER_LEN,
    MAX_REDESIGN_VERSIONS,
)
from modules.vector_map import build_interactive_map
from modules.export     import export_primers_excel, export_full_report_pdf

BASE_DIR = os.path.dirname(__file__)
MAP_DIR  = os.path.join(BASE_DIR, 'exports')
os.makedirs(MAP_DIR, exist_ok=True)

init_db()

st.set_page_config(
    page_title="BioSafe Primer",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ══════════════════════════════════════════════════════════════════════════════
# Global CSS  (main app + auth pages)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&family=Source+Code+Pro:wght@400;600&display=swap');

html, body, [class*="css"] {
  font-family: 'Source Sans 3', 'Segoe UI', Arial, sans-serif !important;
  color: #1C1C1E;
}
.stApp { background: #F7F5F2; }

[data-testid="stSidebar"] { background:#FFFFFF; border-right:2px solid #D0D7E3; }
[data-testid="stSidebar"] * { color:#1C1C1E !important; }

/* ── Auth page ── */
.auth-logo { text-align:center; margin-bottom:24px; }
.auth-logo h1 { color:#0072B2; font-size:2.1rem; font-weight:700; margin:0; }
.auth-logo p  { color:#5A6475; font-size:0.88rem; margin:5px 0 0; }
.auth-logo small { color:#8A97A6; font-size:0.76rem; }

.google-btn-wrap { display:flex; justify-content:center; margin:14px 0 10px; }
.google-btn {
  display:inline-flex; align-items:center; gap:10px;
  background:#FFFFFF; border:2px solid #D0D7E3; border-radius:8px;
  padding:10px 28px; font-size:0.93rem; font-weight:600; color:#1C1C1E;
  text-decoration:none; cursor:pointer;
  transition:border-color .2s, box-shadow .2s;
  font-family:'Source Sans 3',sans-serif;
}
.google-btn:hover { border-color:#0072B2; box-shadow:0 2px 10px rgba(0,114,178,.15); }

.or-divider {
  display:flex; align-items:center; gap:10px;
  color:#A8BACA; font-size:0.83rem; margin:14px 0;
}
.or-divider::before, .or-divider::after {
  content:''; flex:1; border-top:1px solid #D0D7E3;
}

.tc-scroll {
  background:#F7F5F2; border:1px solid #D0D7E3; border-radius:8px;
  padding:16px 18px; max-height:290px; overflow-y:auto;
  font-size:12.5px; line-height:1.75; color:#3A4A5C;
}
.tc-scroll h4 { color:#0072B2; font-size:13px; margin:14px 0 5px; }
.tc-scroll p  { margin:0 0 8px; }
.tc-scroll ul { margin:0 0 8px; padding-left:18px; }

/* ── Main header ── */
.main-header {
  background:#0072B2; border-radius:10px; padding:20px 28px; margin-bottom:6px;
  box-shadow:0 3px 14px rgba(0,114,178,.22);
  display:flex; align-items:center; justify-content:space-between;
}
.main-header h1 { color:#FFF; font-size:1.8rem; font-weight:700; margin:0; }
.main-header p  { color:#CDEAF8; font-size:0.9rem; margin:4px 0 0; }
.active-project-badge {
  background:rgba(255,255,255,.18); border:1px solid rgba(255,255,255,.4);
  border-radius:20px; padding:5px 14px; color:white;
  font-size:0.85rem; font-weight:600; white-space:nowrap;
}

/* ── User strip ── */
.user-strip {
  display:flex; align-items:center; justify-content:space-between;
  background:#EEF2F7; border:1px solid #C3CFE0; border-radius:8px;
  padding:7px 14px; margin-bottom:16px; font-size:13px;
}
.user-strip .uname { color:#0072B2; font-weight:600; }
.user-strip .umeta { color:#5A6475; font-size:12px; }
.admin-badge {
  background:#E69F00; color:#fff; font-size:11px; font-weight:700;
  border-radius:20px; padding:2px 10px; margin-left:8px;
}

/* ── Project cards ── */
.proj-card {
  background:#FFFFFF; border:2px solid #D0D7E3; border-radius:12px;
  padding:18px 20px; margin-bottom:14px; cursor:pointer;
  transition:border-color .2s,box-shadow .2s;
  box-shadow:0 2px 8px rgba(0,0,0,.06);
}
.proj-card:hover { border-color:#0072B2; box-shadow:0 4px 16px rgba(0,114,178,.15); }
.proj-card h3   { color:#0072B2; margin:0 0 6px; font-size:1.1rem; font-weight:700; }
.proj-card .meta { color:#5A6475; font-size:12px; line-height:1.8; }
.proj-card .prog-bar-wrap { background:#EEF2F7; border-radius:20px; height:8px; margin-top:10px; }
.proj-card .prog-bar      { background:#009E73; border-radius:20px; height:8px; transition:width .4s; }

.new-proj-box {
  background:#FFFFFF; border:2px dashed #A8BACA; border-radius:12px;
  padding:24px 28px; margin-bottom:14px;
}

/* ── Active project banner ── */
.proj-banner {
  background:#EEF2F7; border:1.5px solid #C3CFE0; border-radius:8px;
  padding:10px 16px; margin-bottom:16px;
  display:flex; align-items:center; justify-content:space-between;
}
.proj-banner .pname { font-weight:700; color:#0072B2; font-size:1rem; }
.proj-banner .pmeta { color:#5A6475; font-size:12px; }

/* ── Metric cards ── */
.metric-card {
  background:#FFFFFF; border:2px solid #D0D7E3; border-radius:10px;
  padding:14px 16px; text-align:center; box-shadow:0 2px 8px rgba(0,0,0,.06);
}
.metric-card .value { font-size:1.9rem; font-weight:700; color:#0072B2; }
.metric-card .label { font-size:.72rem; color:#5A6475; text-transform:uppercase;
                       letter-spacing:.8px; margin-top:4px; }
.metric-done    .value { color:#009E73; }
.metric-pending .value { color:#E69F00; }
.metric-failed  .value { color:#D55E00; }

/* ── Section headers ── */
.section-header {
  border-left:4px solid #0072B2; padding-left:12px;
  color:#0072B2; font-size:1.1rem; font-weight:600; margin:20px 0 12px;
}

/* ── Upload done ── */
.upload-done {
  background:#E8F5E9; border:1.5px solid #009E73; border-radius:8px;
  padding:12px 16px; color:#1B4332; font-size:13px; margin-bottom:10px;
}

/* ── Primer code ── */
.primer-code {
  font-family:'Source Code Pro','Courier New',monospace !important;
  background:#EEF2F7; border-radius:6px; padding:6px 10px;
  font-size:12.5px; color:#1C1C1E; margin:4px 0;
  border-left:3px solid #0072B2;
}
.primer-code.rp { border-left-color:#D55E00; }

/* ── Overlap badges ── */
.ov-badge { display:inline-block; padding:3px 10px; border-radius:20px;
            font-size:12px; font-weight:600; }
.ov-ok   { background:#D4EDDA; color:#155724; border:1px solid #009E73; }
.ov-fail { background:#FDECEA; color:#721C24; border:1px solid #D55E00; }
.ov-na   { background:#EEF2F7; color:#5A6475; border:1px solid #C3CFE0; }

/* ── Redesign preview ── */
.redesign-preview {
  background:#FFF8EC; border:2px solid #E69F00; border-radius:10px;
  padding:16px 20px; margin-top:12px;
}
.redesign-preview h4 { color:#7A4F00; margin:0 0 10px; font-size:1rem; font-weight:700; }
.rule-pass { color:#009E73; font-weight:600; }
.rule-fail { color:#D55E00; font-weight:600; }

/* ── Proj meta sidebar ── */
.proj-meta {
  background:#EEF2F7; border:1px solid #C3CFE0; border-radius:8px;
  padding:10px 14px; font-size:12px; color:#3A4A5C; line-height:1.9;
}
.proj-meta strong { color:#0072B2; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab"] { color:#5A6475 !important; font-weight:500; font-size:.92rem; }
.stTabs [aria-selected="true"] { color:#0072B2 !important;
  border-bottom:3px solid #0072B2 !important; font-weight:700; }

/* ── Buttons ── */
.stButton > button { border-radius:7px; font-weight:600;
  font-family:'Source Sans 3',sans-serif !important; }

/* ── Footer ── */
.footer-ribbon {
  position:fixed; bottom:0; left:0; right:0;
  background:#0072B2; color:#CDEAF8; text-align:center;
  font-size:11.5px; font-weight:500; padding:7px 20px;
  z-index:9999; letter-spacing:.3px;
  box-shadow:0 -2px 8px rgba(0,114,178,.18);
  font-family:'Source Sans 3','Segoe UI',Arial,sans-serif;
}
.footer-ribbon strong { color:#FFFFFF; }
.block-container { padding-bottom:48px !important; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Helper — Google SVG icon
# ══════════════════════════════════════════════════════════════════════════════
_GOOGLE_SVG = """<svg width="18" height="18" viewBox="0 0 18 18"
  xmlns="http://www.w3.org/2000/svg">
  <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844
    c-.209 1.125-.843 2.078-1.796 2.716v2.258h2.908
    C16.658 14.013 17.64 11.706 17.64 9.2z" fill="#4285F4"/>
  <path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259
    c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711
    H.957v2.332A8.997 8.997 0 0 0 9 18z" fill="#34A853"/>
  <path d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71
    V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042
    l3.007-2.332z" fill="#FBBC05"/>
  <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58
    C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958
    L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z" fill="#EA4335"/>
</svg>"""


# ══════════════════════════════════════════════════════════════════════════════
# Terms & Conditions content
# ══════════════════════════════════════════════════════════════════════════════
def _tc_html() -> str:
    return """
<div class="tc-scroll">
<p><strong>BioSafe Primer — Terms of Use &amp; Data Privacy Policy</strong><br>
Division of Plant Physiology, ICAR–Indian Agricultural Research Institute, New Delhi<br>
<em>Effective Date: April 2026</em></p>

<h4>1. Acceptance of Terms</h4>
<p>By registering and using BioSafe Primer ("the Platform"), you agree to be bound by
these Terms of Use. If you do not agree, please do not register or use the Platform.</p>

<h4>2. Purpose of the Platform</h4>
<p>BioSafe Primer is a research tool developed for use by scientific personnel engaged
in plant molecular biology and genome editing research. Use of the Platform is strictly
limited to lawful research and academic purposes.</p>

<h4>3. Data You Upload</h4>
<p>When you upload vector sequences, design primers, or log experimental data, that data
is stored in a secure database associated exclusively with your user account. Your
uploaded data is:</p>
<ul>
  <li><strong>Visible only to you.</strong> No other registered user can access your
      projects or sequences.</li>
  <li><strong>Not shared with third parties</strong> for commercial, advertising, or
      any non-research purpose.</li>
  <li><strong>Not examined or disclosed</strong> by Platform administrators for any
      purpose other than routine technical maintenance (e.g., database integrity checks,
      bug resolution).</li>
</ul>

<h4>4. Administrator Access &amp; Confidentiality</h4>
<p>Platform administrators have technical access to the underlying database solely for
maintenance and operational purposes. Administrators are bound by institutional
confidentiality obligations and <strong>will not disclose, publish, reproduce, or
share</strong> any sequence data, primer designs, or experimental records uploaded by
users under any circumstances.</p>

<h4>5. Limitation of Liability — Server &amp; Infrastructure</h4>
<p>The Platform is hosted on third-party cloud infrastructure (Streamlit Community
Cloud). While reasonable efforts are made to maintain server security and data
integrity, <strong>ICAR–IARI and the Platform developers do not guarantee uninterrupted
service, data permanence, or protection against events beyond our reasonable
control</strong>, including but not limited to:</p>
<ul>
  <li>Server failure, corruption, or data loss</li>
  <li>Unauthorised access, cyberattacks, or security breaches affecting the hosting
      provider</li>
  <li>Accidental deletion or corruption of data resulting from software errors</li>
</ul>
<p><strong>By using this Platform, you acknowledge and accept that ICAR–IARI, its
developers, and affiliates shall not be held liable for any loss of data, research
materials, or consequential damages arising from such events.</strong> Users are
strongly encouraged to maintain independent local backups of all critical sequences
and experimental records.</p>

<h4>6. Intellectual Property</h4>
<p>You retain full ownership of all sequence data and research materials you upload.
By uploading data, you grant the Platform only the limited technical rights necessary
to store and display that data to you.</p>

<h4>7. Account Security</h4>
<p>You are responsible for maintaining the confidentiality of your login credentials.
Please notify the Platform administrators immediately if you suspect unauthorised access
to your account. The Platform administrators cannot be held responsible for unauthorised
access resulting from compromised credentials.</p>

<h4>8. Modifications to Terms</h4>
<p>These terms may be updated periodically. Continued use of the Platform following
notification of changes constitutes acceptance of the revised terms.</p>

<h4>9. Contact</h4>
<p>For questions regarding these terms or data privacy concerns, contact the
Division of Plant Physiology, ICAR–IARI, New Delhi.</p>

<p style="margin-top:14px;font-style:italic">
By checking the box below, you confirm that you have read, understood, and accepted
all terms above.</p>
</div>
"""


# ══════════════════════════════════════════════════════════════════════════════
# Auth — Login tab
# ══════════════════════════════════════════════════════════════════════════════
def _render_login_tab():
    # Google button (only shown when credentials are configured)
    if google_is_configured():
        auth_url = get_google_auth_url()
        st.markdown(f"""
        <div class="google-btn-wrap">
          <a href="{auth_url}" target="_self" class="google-btn">
            {_GOOGLE_SVG}&nbsp; Sign in with Google
          </a>
        </div>
        <div class="or-divider">or continue with email</div>
        """, unsafe_allow_html=True)
    else:
        st.info("ℹ️ Google Sign-In is not yet configured. Use email & password below.")

    email_v = st.text_input("Email address", key="login_email",
                             placeholder="you@example.com")
    pw_v    = st.text_input("Password", type="password", key="login_pw",
                             placeholder="••••••••")

    if st.button("Sign In →", type="primary", use_container_width=True,
                  key="btn_signin"):
        if not email_v or not pw_v:
            st.error("Please enter your email and password.")
            return
        result = login_with_password(email_v, pw_v)
        if result == "google_account":
            st.error("This email is registered via Google Sign-In. "
                     "Please use the 'Sign in with Google' button above.")
        elif result:
            set_session_user(result)
            st.rerun()
        else:
            st.error("Incorrect email or password. Please try again.")


# ══════════════════════════════════════════════════════════════════════════════
# Auth — Register tab
# ══════════════════════════════════════════════════════════════════════════════
def _render_register_tab():
    # Google button for new users too
    if google_is_configured():
        auth_url = get_google_auth_url()
        st.markdown(f"""
        <div class="google-btn-wrap">
          <a href="{auth_url}" target="_self" class="google-btn">
            {_GOOGLE_SVG}&nbsp; Continue with Google
          </a>
        </div>
        <div class="or-divider">or create an account with email</div>
        """, unsafe_allow_html=True)

    name_v  = st.text_input("Full name", key="reg_name",
                              placeholder="Dr. Firstname Lastname")
    email_v = st.text_input("Email address", key="reg_email",
                              placeholder="you@example.com")
    pw_v    = st.text_input("Password (minimum 8 characters)", type="password",
                             key="reg_pw", placeholder="••••••••")
    pw_c    = st.text_input("Confirm password", type="password",
                             key="reg_pwc", placeholder="••••••••")

    # Terms & Conditions — must expand and agree before registering
    st.markdown("**Terms of Use & Data Privacy Policy**")
    st.markdown(_tc_html(), unsafe_allow_html=True)

    agreed = st.checkbox(
        "I have read and agree to the Terms of Use & Data Privacy Policy",
        key="reg_agreed"
    )

    if st.button("Create Account →", type="primary",
                  use_container_width=True, key="btn_register",
                  disabled=not agreed):
        if not name_v or not email_v or not pw_v:
            st.error("Please fill in all fields.")
            return
        if pw_v != pw_c:
            st.error("Passwords do not match.")
            return
        user, err = register_with_password(name_v, email_v, pw_v)
        if err:
            st.error(err)
        elif user:
            set_session_user(user)
            st.success(f"Welcome to BioSafe Primer, {user['name']}! 🎉")
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# Auth — Full page (handles Google callback + shows login/register tabs)
# ══════════════════════════════════════════════════════════════════════════════
def render_auth_page():
    # ── Handle Google OAuth callback ──────────────────────────────────────────
    params = st.query_params
    if "code" in params:
        with st.spinner("Completing Google Sign-In…"):
            userinfo = handle_google_callback(params["code"])
        st.query_params.clear()
        if userinfo and userinfo.get("email"):
            user = login_with_google(userinfo)
            if user:
                set_session_user(user)
                st.rerun()
            else:
                st.error("Could not retrieve your account. Please try again.")
        else:
            st.error("Google Sign-In failed. Please try again or use email/password.")
        return

    # ── Layout: narrow centred column ─────────────────────────────────────────
    _, col, _ = st.columns([1, 2.2, 1])
    with col:
        st.markdown("""
        <div class="auth-logo">
          <h1>🧬 BioSafe Primer</h1>
          <p>Overlapping PCR Primer Design · GMO Exemption Research Tool</p>
          <small>Division of Plant Physiology · ICAR–IARI, New Delhi</small>
        </div>
        """, unsafe_allow_html=True)

        tab_in, tab_reg = st.tabs(["🔐 Sign In", "✏️ Create Account"])
        with tab_in:
            _render_login_tab()
        with tab_reg:
            _render_register_tab()

    _render_footer()


# ══════════════════════════════════════════════════════════════════════════════
# App Helpers
# ══════════════════════════════════════════════════════════════════════════════
def get_best_primers(primers):
    seen = {}
    for p in primers:
        an = p['amplicon_num']
        if an not in seen or p['version'] > seen[an]['version']:
            seen[an] = p
    return list(seen.values())

def fmt_ov(val):
    return f"{val} bp" if val is not None else "N/A"

def ov_badge(val, min_ov=50):
    if val is None:
        return '<span class="ov-badge ov-na">N/A</span>'
    if val >= min_ov:
        return f'<span class="ov-badge ov-ok">✔ {val} bp</span>'
    return f'<span class="ov-badge ov-fail">✖ {val} bp (min {min_ov})</span>'

def rule_check(ok, label):
    cls = 'rule-pass' if ok else 'rule-fail'
    return f'<span class="{cls}">{"✅" if ok else "❌"} {label}</span>'

def amp_label(p):
    return p.get('amplicon_name') or f"Amplicon_{p['amplicon_num']}"


# ══════════════════════════════════════════════════════════════════════════════
# Redesign UI (unchanged logic)
# ══════════════════════════════════════════════════════════════════════════════
def _redesign_ui(p, pid):
    st.markdown("---")
    st.markdown("**🔄 Redesign Primers**")
    preview_key = f"redesign_preview_{p['id']}"

    if preview_key in st.session_state:
        np      = st.session_state[preview_key]['primer']
        ext_l   = st.session_state[preview_key]['ext_l']
        ext_r   = st.session_state[preview_key]['ext_r']
        reason  = st.session_state[preview_key]['reason']
        prev_ov = np.get('overlap_prev')
        next_ov = np.get('overlap_next')

        amp_ok   = MIN_AMPLICON <= np['amplicon_length'] <= MAX_AMPLICON
        ov_up_ok = prev_ov is None or prev_ov >= 50
        ov_dn_ok = next_ov is None or next_ov >= 50
        fp_ok    = MIN_PRIMER_LEN <= np['fp_length'] <= MAX_PRIMER_LEN
        rp_ok    = MIN_PRIMER_LEN <= np['rp_length'] <= MAX_PRIMER_LEN

        viol_list = np.get('redesign_violations', [])
        if viol_list:
            viol_items = "".join(
                f'<div style="margin:3px 0;font-size:11.5px;color:#D55E00">⚠ {v}</div>'
                for v in viol_list
            )
            violations_html = (
                '<div style="margin-top:10px;background:#FDECEA;'
                'border-radius:6px;padding:8px 10px;">' + viol_items + '</div>'
            )
        else:
            violations_html = (
                '<div style="margin-top:10px;background:#D4EDDA;'
                'border-radius:6px;padding:8px 10px;font-size:11.5px;color:#155724">'
                '✅ All redesign rules pass — safe to accept.</div>'
            )

        rules_html = " &nbsp;|&nbsp; ".join([
            rule_check(amp_ok,   f"Amp size {np['amplicon_length']} bp"),
            rule_check(fp_ok,    f"FP {np['fp_length']} bp"),
            rule_check(rp_ok,    f"RP {np['rp_length']} bp"),
            rule_check(ov_up_ok, "Upstream ≥50 bp"),
            rule_check(ov_dn_ok, "Downstream ≥50 bp"),
        ])

        st.markdown(f"""
<div class="redesign-preview">
  <h4>📋 Redesign Preview — {amp_label(p)} v{np['version']}</h4>
  <div style="margin-bottom:10px">{rules_html}</div>
  <div class="primer-code">FP: {np['fp_sequence']}</div>
  <div style="font-size:11.5px;color:#5A6475;margin:3px 0 8px 4px">
    {np['fp_length']} bp &nbsp;|&nbsp; Tm {np['fp_tm']}°C &nbsp;|&nbsp;
    GC {np['fp_gc']}% &nbsp;|&nbsp; Hairpin {np.get('fp_hairpin_tm',0)}°C &nbsp;|&nbsp;
    3' Stab {np.get('fp_end_stability',0)} &nbsp;|&nbsp; Penalty {np.get('fp_penalty',0)}
  </div>
  <div class="primer-code rp">RP: {np['rp_sequence']}</div>
  <div style="font-size:11.5px;color:#5A6475;margin:3px 0 8px 4px">
    {np['rp_length']} bp &nbsp;|&nbsp; Tm {np['rp_tm']}°C &nbsp;|&nbsp;
    GC {np['rp_gc']}% &nbsp;|&nbsp; Hairpin {np.get('rp_hairpin_tm',0)}°C &nbsp;|&nbsp;
    3' Stab {np.get('rp_end_stability',0)} &nbsp;|&nbsp; Penalty {np.get('rp_penalty',0)}
  </div>
  <div style="font-size:12px;margin-bottom:10px">
    <strong>Position:</strong> {np['amplicon_start']}–{np['amplicon_end']} bp &nbsp;|&nbsp;
    <strong>Length:</strong> {np['amplicon_length']} bp &nbsp;|&nbsp;
    <strong>Pair Penalty:</strong> {np.get('pair_penalty',0)}
  </div>
  <div style="display:flex;gap:12px;align-items:center;margin-bottom:5px">
    <span style="font-size:12.5px;font-weight:600;color:#3A4A5C">
      🔼 Upstream overlap (with Amp {np['amplicon_num']-1}):
    </span>{ov_badge(prev_ov)}
  </div>
  <div style="display:flex;gap:12px;align-items:center">
    <span style="font-size:12.5px;font-weight:600;color:#3A4A5C">
      🔽 Downstream overlap (with Amp {np['amplicon_num']+1}):
    </span>{ov_badge(next_ov)}
  </div>
  {violations_html}
</div>""", unsafe_allow_html=True)

        ca, cb = st.columns(2)
        all_ok = amp_ok and fp_ok and rp_ok and ov_up_ok and ov_dn_ok
        if ca.button("✅ Accept & Save", key=f"acc_{p['id']}", type="primary",
                     disabled=not all_ok):
            np['status']        = 'Pending'
            np['amplicon_name'] = amp_label(p)
            save_primers(pid, [np])
            attempt      = st.session_state[preview_key].get('attempt', 1)
            failure_type = st.session_state[preview_key].get('failure_type', '')
            save_redesign_history(
                pid, p['amplicon_num'], p['id'], None, ext_l, ext_r, reason,
                failure_type=failure_type, attempt_num=attempt,
                upstream_overlap=np.get('overlap_prev'),
                downstream_overlap=np.get('overlap_next')
            )
            update_primer_status(p['id'], 'Redesigned')
            del st.session_state[preview_key]
            st.success("✅ Redesigned primers saved!")
            st.rerun()
        if cb.button("❌ Reject & Try Again", key=f"rej_{p['id']}"):
            del st.session_state[preview_key]
            st.rerun()
        if not all_ok:
            st.error("⛔ Accept & Save is disabled until all rule checks pass.")
        return

    # ── Max versions check ────────────────────────────────────────────────────
    if p.get('version', 1) >= MAX_REDESIGN_VERSIONS:
        st.error(
            f"⛔ Maximum {MAX_REDESIGN_VERSIONS} redesign attempts reached for "
            f"{amp_label(p)}. Consider manual primer design or extending "
            "coverage from adjacent amplicons."
        )
        return

    FAILURE_OPTIONS = [
        'No band', 'Multiple bands', 'Weak band',
        'Wrong band size', 'Primer dimer', 'Overlap violation', 'Other'
    ]
    default_failure = ('Overlap violation'
                       if p.get('status') == 'Overlap Violation' else 'No band')

    failure_type = st.selectbox(
        "Failure reason", FAILURE_OPTIONS,
        index=FAILURE_OPTIONS.index(default_failure),
        key=f"ftype_{p['id']}"
    )
    rec = get_redesign_recommendation(failure_type)
    st.info(f"💡 **Recommended strategy:** {rec['note']}")

    rc1, rc2 = st.columns(2)
    ext_l = rc1.number_input(
        "Upstream extension (bp)", min_value=0, max_value=200,
        value=rec['ext_left'], key=f"el_{p['id']}",
        help="Moves the primer search window leftward."
    )
    ext_r = rc2.number_input(
        "Downstream extension (bp)", min_value=0, max_value=200,
        value=rec['ext_right'], key=f"er_{p['id']}",
        help="Gives Primer3 more downstream sequence."
    )

    if ext_r > 0:
        st.warning(
            "⚠️ Downstream extension gives Primer3 more sequence but does not "
            "guarantee downstream overlap. Preview will show actual overlap values."
        )

    reason = st.text_input(
        "Additional notes (optional)",
        placeholder="e.g. No band after 35 cycles, checked with positive control",
        key=f"rsn_{p['id']}"
    )
    st.caption(f"Redesign attempt {p.get('version',1)} of {MAX_REDESIGN_VERSIONS} maximum")

    if st.button("🔬 Run Redesign", key=f"red_{p['id']}", type="primary"):
        seq_info = st.session_state.get('seq_info')
        if not seq_info:
            st.warning("Re-open project from Home to enable redesign.")
            return

        all_p = get_best_primers(get_primers_by_project(pid))
        idx   = next((i for i, x in enumerate(all_p)
                      if x['amplicon_num'] == p['amplicon_num']), None)
        prev_amp_end   = None
        next_amp_start = None
        if idx is not None:
            if idx > 0 and all_p[idx-1]['fp_sequence'] != 'DESIGN_FAILED':
                prev_amp_end = all_p[idx-1]['amplicon_end']
            if (idx < len(all_p)-1 and
                    all_p[idx+1]['fp_sequence'] != 'DESIGN_FAILED'):
                next_amp_start = all_p[idx+1]['amplicon_start']

        with st.spinner("Redesigning with Primer3…"):
            new_p, err_msg = redesign_primers(
                seq_info['sequence'],
                p['amplicon_start'], p['amplicon_end'],
                p['amplicon_num'], ext_l, ext_r, p['version'],
                prev_amp_end=prev_amp_end,
                next_amp_start=next_amp_start
            )

        if new_p:
            st.session_state[f"redesign_preview_{p['id']}"] = {
                'primer': new_p, 'ext_l': ext_l, 'ext_r': ext_r,
                'reason': reason, 'failure_type': failure_type,
                'attempt': p.get('version', 1) + 1,
            }
            st.rerun()
        else:
            st.error(f"Redesign failed — {err_msg}. Try larger extension values.")


# ══════════════════════════════════════════════════════════════════════════════
# Footer
# ══════════════════════════════════════════════════════════════════════════════
def _render_footer():
    st.markdown(
        '<div class="footer-ribbon">'
        '<strong>BioSafe Primer</strong> &nbsp;·&nbsp; '
        'Developed and maintained by '
        '<strong>Division of Plant Physiology, '
        'ICAR-Indian Agricultural Research Institute</strong>'
        '</div>',
        unsafe_allow_html=True
    )


# ══════════════════════════════════════════════════════════════════════════════
# ── AUTH GATE ────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
current_user = get_session_user()
if not current_user:
    render_auth_page()
    st.stop()

# Convenience variables available for the rest of the app
uid      = current_user["id"]
is_admin = st.session_state.get("is_admin", False)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN APP (authenticated users only beyond this point)
# ══════════════════════════════════════════════════════════════════════════════

pid      = st.session_state.get('project_id')
proj_rec = get_project(pid, uid) if pid else None   # ownership-checked

# ── Main header ───────────────────────────────────────────────────────────────
badge_html = ""
if proj_rec:
    badge_html = (
        f'<div class="active-project-badge">📂 {proj_rec["name"]}'
        f' &nbsp;·&nbsp; {proj_rec.get("vector_length",0):,} bp</div>'
    )

st.markdown(f"""
<div class="main-header">
  <div>
    <h1>🧬 BioSafe Primer</h1>
    <p>Overlapping PCR primer design · Progress monitoring · GMO exemption</p>
  </div>
  {badge_html}
</div>
""", unsafe_allow_html=True)

# ── User strip (name, role, sign-out) ─────────────────────────────────────────
admin_badge = '<span class="admin-badge">👑 Admin</span>' if is_admin else ""
u_col1, u_col2 = st.columns([8, 2])
with u_col1:
    st.markdown(
        f'<div class="user-strip">'
        f'<span>👤 &nbsp;<span class="uname">{current_user["name"]}</span>'
        f'<span class="umeta"> &nbsp;·&nbsp; {current_user["email"]}</span>'
        f'{admin_badge}</span>'
        f'<span class="umeta">Signed in via '
        f'{current_user.get("auth_provider","email").capitalize()}</span>'
        f'</div>',
        unsafe_allow_html=True
    )
with u_col2:
    if st.button("Sign Out", key="logout_btn", use_container_width=True):
        logout()
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# HOME — no project selected
# ══════════════════════════════════════════════════════════════════════════════
if not pid:
    st.markdown('<div class="section-header">Project Hub</div>',
                unsafe_allow_html=True)

    projects = get_all_projects(uid)

    # ── Create new project ────────────────────────────────────────────────────
    st.markdown("#### Create New Project")
    st.markdown('<div class="new-proj-box">', unsafe_allow_html=True)

    c1, c2 = st.columns([1, 2])
    with c1:
        new_name = st.text_input("Project name",
                                  placeholder="e.g. pCAMBIA1300_GFP",
                                  key="new_proj_name")
    with c2:
        new_file = st.file_uploader(
            "Upload vector sequence (FASTA or GenBank)",
            type=['fa','fasta','fna','gb','gbk','genbank'],
            key="new_proj_file"
        )

    if new_file and new_name:
        try:
            content_str = new_file.read().decode('utf-8', errors='ignore')
            fmt         = detect_format(new_file.name)
            seq_info    = parse_sequence(content_str, fmt)

            mc1, mc2, mc3 = st.columns(3)
            mc1.markdown(
                f'<div class="metric-card"><div class="value">{seq_info["length"]:,}</div>'
                f'<div class="label">Vector Length (bp)</div></div>',
                unsafe_allow_html=True
            )
            mc2.markdown(
                f'<div class="metric-card"><div class="value">'
                f'{len(seq_info["features"])}</div>'
                f'<div class="label">Features</div></div>',
                unsafe_allow_html=True
            )
            mc3.markdown(
                f'<div class="metric-card"><div class="value">{fmt.upper()}</div>'
                f'<div class="label">Format</div></div>',
                unsafe_allow_html=True
            )
            st.success(f"✅ Parsed: **{seq_info['name']}** — {seq_info['length']:,} bp")

            if st.button("🚀 Create Project", type="primary"):
                new_pid = save_project(
                    new_name, seq_info['name'], seq_info['length'], uid,
                    vector_sequence=seq_info['sequence'],
                    vector_features=json.dumps(seq_info.get('features', []))
                )
                st.session_state['project_id'] = new_pid
                st.session_state['seq_info']   = seq_info
                st.rerun()
        except Exception as e:
            st.error(f"Parse error: {e}")

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Existing projects ─────────────────────────────────────────────────────
    if projects:
        st.markdown("---")
        st.markdown("#### Open Existing Project")
        cols = st.columns(3)
        for i, proj in enumerate(projects):
            stats = get_project_stats(proj['id'])
            total = stats['total']
            done  = stats['done']
            pct   = int((done / total * 100) if total > 0 else 0)

            with cols[i % 3]:
                st.markdown(f"""
<div class="proj-card">
  <h3>📁 {proj['name']}</h3>
  <div class="meta">
    <strong>Vector:</strong> {proj.get('vector_name','—')}<br>
    <strong>Length:</strong> {proj.get('vector_length',0):,} bp<br>
    <strong>Created:</strong> {proj.get('created_at','—')[:16]}<br>
    <strong>Progress:</strong> {done}/{total} amplicons done ({pct}%)
  </div>
  <div class="prog-bar-wrap">
    <div class="prog-bar" style="width:{pct}%"></div>
  </div>
</div>""", unsafe_allow_html=True)

                if st.button("Open →", key=f"open_{proj['id']}"):
                    st.session_state['project_id'] = proj['id']
                    if proj.get('vector_sequence'):
                        st.session_state['seq_info'] = {
                            'name':     proj.get('vector_name', ''),
                            'sequence': proj.get('vector_sequence', ''),
                            'length':   proj.get('vector_length', 0),
                            'features': json.loads(proj.get('vector_features','[]')),
                        }
                    st.rerun()

                if st.button("🗑️ Delete", key=f"del_{proj['id']}"):
                    st.session_state[f'confirm_del_{proj["id"]}'] = True

                if st.session_state.get(f'confirm_del_{proj["id"]}'):
                    st.warning(f"Delete **{proj['name']}**? This cannot be undone.")
                    cy, cn = st.columns(2)
                    if cy.button("Yes", key=f"dy_{proj['id']}"):
                        delete_project(proj['id'], uid)
                        st.session_state.pop(f'confirm_del_{proj["id"]}', None)
                        st.rerun()
                    if cn.button("No", key=f"dn_{proj['id']}"):
                        st.session_state.pop(f'confirm_del_{proj["id"]}', None)
                        st.rerun()

    _render_footer()
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# PROJECT WORKSPACE
# ══════════════════════════════════════════════════════════════════════════════

# Guard: if project_id is set but doesn't belong to this user, reset
if not proj_rec:
    st.session_state.pop('project_id', None)
    st.session_state.pop('seq_info', None)
    st.rerun()

seq_info = st.session_state.get('seq_info')

# Active project banner
st.markdown(f"""
<div class="proj-banner">
  <div>
    <span class="pname">📂 {proj_rec.get('name','—')}</span>
    <span class="pmeta">
      &nbsp;·&nbsp; {proj_rec.get('vector_name','—')}
      &nbsp;·&nbsp; {proj_rec.get('vector_length',0):,} bp
      &nbsp;·&nbsp; Created {proj_rec.get('created_at','—')[:16]}
    </span>
  </div>
</div>
""", unsafe_allow_html=True)

if st.button("← Switch Project", key="switch_proj"):
    st.session_state.pop('project_id', None)
    st.session_state.pop('seq_info', None)
    st.rerun()

# ── Sidebar: PCR parameters ────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("#### ⚙️ PCR Parameters")
    max_amp  = st.slider("Max amplicon (bp)", 300, 500, 500, 50)
    min_over = st.slider("Min overlap (bp)",   50, 150,  50, 10)
    opt_tm   = st.slider("Optimal Tm (°C)",  55.0, 65.0, 60.0, 0.5)
    min_tm   = st.slider("Min Tm (°C)",      50.0, 60.0, 58.0, 0.5)
    max_tm   = st.slider("Max Tm (°C)",      60.0, 70.0, 62.0, 0.5)
    st.markdown("---")
    st.markdown(
        f"**Protocol Rules**  \n"
        f"Amp: {MIN_AMPLICON}–{MAX_AMPLICON} bp  \n"
        f"Primer: {MIN_PRIMER_LEN}–{MAX_PRIMER_LEN} bp  \n"
        f"Overlap ≥ 50 bp  \n"
        f"Amp 1 starts at base 1  \n"
        f"Full vector coverage"
    )

# ── Workspace tabs (Gel Upload tab removed) ───────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "🔬 Design Primers", "🗺️ Vector Map",
    "📊 Progress Tracker", "📥 Export"
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Design Primers
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown('<div class="section-header">Design Overlapping Primers</div>',
                unsafe_allow_html=True)

    if seq_info:
        st.markdown(
            f'<div class="upload-done">✅ <strong>Vector loaded:</strong> '
            f'{seq_info["name"]} — {seq_info["length"]:,} bp — '
            f'{len(seq_info.get("features",[]))} annotated features<br>'
            f'<small>Sequence is stored with this project.</small></div>',
            unsafe_allow_html=True
        )
    else:
        st.warning("Sequence not found. Re-open this project from Home.")

    if st.button("🚀 Design Primers", type="primary", disabled=not seq_info):
        params = {
            'PRIMER_OPT_SIZE': 20, 'PRIMER_MIN_SIZE': 18, 'PRIMER_MAX_SIZE': 25,
            'PRIMER_OPT_TM': opt_tm, 'PRIMER_MIN_TM': min_tm,
            'PRIMER_MAX_TM': max_tm,
            'PRIMER_MIN_GC': 40.0,  'PRIMER_MAX_GC': 60.0,
            'PRIMER_MAX_POLY_X': 4, 'PRIMER_SALT_MONOVALENT': 50.0,
            'PRIMER_DNA_CONC': 50.0,'PRIMER_NUM_RETURN': 5,
            'PRIMER_MAX_SELF_ANY': 12, 'PRIMER_MAX_SELF_END': 8,
            'PRIMER_PAIR_MAX_COMPL_ANY': 12, 'PRIMER_PAIR_MAX_COMPL_END': 8,
        }
        with st.spinner("Designing primers with Primer3…"):
            primers, violations = design_all_primers(
                seq_info['sequence'], max_amp, min_over, params
            )

        save_primers(pid, primers)
        st.session_state['primers'] = primers

        failed = sum(1 for p in primers if p['fp_sequence'] == 'DESIGN_FAILED')
        st.success(f"✅ Designed **{len(primers)}** primer pairs  |  ⚠️ {failed} failed")

        ov_v = [v for v in violations if 'Rule 3' in v or 'Rule 4' in v]
        ot_v = [v for v in violations if v not in ov_v]
        if ov_v:
            st.error("🚫 Overlap violations — affected amplicons require redesign:")
            for v in ov_v: st.error(v)
        for v in ot_v: st.warning(v)
        if not violations:
            st.success("✅ All protocol rules passed")

        df = pd.DataFrame(primers)
        if 'amplicon_name' not in df.columns:
            df['amplicon_name'] = df['amplicon_num'].apply(lambda n: f'Amplicon_{n}')
        df['overlap_prev'] = df['overlap_prev'].apply(fmt_ov)
        df['overlap_next'] = df['overlap_next'].apply(fmt_ov)
        display_cols = [
            'amplicon_num','amplicon_name',
            'fp_sequence','fp_tm','fp_gc','fp_hairpin_tm','fp_end_stability','fp_penalty',
            'rp_sequence','rp_tm','rp_gc','rp_hairpin_tm','rp_end_stability','rp_penalty',
            'pair_penalty','amplicon_length','overlap_prev','overlap_next','status'
        ]
        display_cols = [c for c in display_cols if c in df.columns]
        st.dataframe(df[display_cols], use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Vector Map
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown('<div class="section-header">Interactive Linear Vector Map</div>',
                unsafe_allow_html=True)
    primers = get_best_primers(get_primers_by_project(pid))
    if not seq_info:
        st.warning("Sequence not available — re-open project from Home.")
    elif not primers:
        st.info("No primers designed yet. Go to the Design Primers tab.")
    else:
        html_map = build_interactive_map(seq_info, primers)
        st.components.v1.html(html_map, height=440, scrolling=True)
        st.caption(
            "💡 Click any amplicon for details  |  ESC to close popup  |  "
            "Show Sequence → use Ctrl+F to search"
        )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Progress Tracker
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown('<div class="section-header">PCR Progress Dashboard</div>',
                unsafe_allow_html=True)
    all_p = get_primers_by_project(pid)
    best  = get_best_primers(all_p)

    total   = len(best)
    done    = sum(1 for p in best if p['status'] == 'Done')
    pending = sum(1 for p in best if p['status'] == 'Pending')
    failed  = sum(1 for p in best if p['status'] in ('Failed','Overlap Violation'))

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(
        f'<div class="metric-card"><div class="value">{total}</div>'
        f'<div class="label">Total Amplicons</div></div>',
        unsafe_allow_html=True
    )
    c2.markdown(
        f'<div class="metric-card metric-done"><div class="value">{done}</div>'
        f'<div class="label">Completed</div></div>',
        unsafe_allow_html=True
    )
    c3.markdown(
        f'<div class="metric-card metric-pending"><div class="value">{pending}</div>'
        f'<div class="label">Pending</div></div>',
        unsafe_allow_html=True
    )
    c4.markdown(
        f'<div class="metric-card metric-failed"><div class="value">{failed}</div>'
        f'<div class="label">Failed</div></div>',
        unsafe_allow_html=True
    )

    if total > 0:
        st.markdown(f"**Progress: {done}/{total} ({done/total*100:.0f}%)**")
        st.progress(done / total)
    st.markdown("---")

    for p in best:
        label = amp_label(p)
        with st.expander(
            f"{label}  |  v{p['version']}  |  "
            f"{p['amplicon_start']}–{p['amplicon_end']} bp  |  {p['status']}"
        ):
            new_name = st.text_input(
                "Amplicon name", value=label,
                key=f"aname_{p['id']}", placeholder="e.g. GFP_region_1"
            )
            if st.button("Rename", key=f"rename_{p['id']}"):
                update_amplicon_name(p['id'], new_name)
                st.success(f"Renamed to **{new_name}**")
                st.rerun()

            st.markdown("---")
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(
                    f'<div class="primer-code">FP: {p["fp_sequence"]}</div>',
                    unsafe_allow_html=True
                )
                st.caption(
                    f"**FP:** {p['fp_length']} bp | Tm {p['fp_tm']}°C | "
                    f"GC {p['fp_gc']}% | Hairpin {p.get('fp_hairpin_tm',0)}°C | "
                    f"3' Stab {p.get('fp_end_stability',0)} | "
                    f"Penalty {p.get('fp_penalty',0)}"
                )
                st.markdown(
                    f'<div class="primer-code rp">RP: {p["rp_sequence"]}</div>',
                    unsafe_allow_html=True
                )
                st.caption(
                    f"**RP:** {p['rp_length']} bp | Tm {p['rp_tm']}°C | "
                    f"GC {p['rp_gc']}% | Hairpin {p.get('rp_hairpin_tm',0)}°C | "
                    f"3' Stab {p.get('rp_end_stability',0)} | "
                    f"Penalty {p.get('rp_penalty',0)}"
                )
                st.markdown(
                    f"**Pair Penalty:** {p.get('pair_penalty',0)} &nbsp;|&nbsp; "
                    f"**Amp:** {p['amplicon_length']} bp &nbsp;|&nbsp; "
                    f"🔼 Upstream: {ov_badge(p.get('overlap_prev'))} &nbsp; "
                    f"🔽 Downstream: {ov_badge(p.get('overlap_next'))}",
                    unsafe_allow_html=True
                )
            with c2:
                valid_s = ['Pending','Done','Failed','Overlap Violation']
                cur     = p['status'] if p['status'] in valid_s else 'Pending'
                new_s   = st.selectbox(
                    "Status", valid_s,
                    index=valid_s.index(cur),
                    key=f"st_{p['id']}"
                )
                if st.button("Update", key=f"upd_{p['id']}"):
                    update_primer_status(p['id'], new_s)
                    st.rerun()

            if p['status'] in ('Failed', 'Overlap Violation'):
                _redesign_ui(p, pid)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Export
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown('<div class="section-header">Export Results</div>',
                unsafe_allow_html=True)
    primers  = get_primers_by_project(pid)
    pcr_runs = get_pcr_runs_by_project(pid)
    pname    = proj_rec.get('name', 'Project') if proj_rec else 'Project'

    c1, c2 = st.columns(2)
    with c1:
        if st.button("📊 Download Excel", type="primary"):
            xp = os.path.join(MAP_DIR, f"primers_{pid}.xlsx")
            export_primers_excel(primers, pname, xp)
            with open(xp, 'rb') as f:
                st.download_button(
                    "⬇️ Download Excel file", f.read(),
                    file_name=f"{pname}_primers.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    with c2:
        if st.button("📄 Generate PDF Report"):
            pp = os.path.join(MAP_DIR, f"report_{pid}.pdf")
            export_full_report_pdf(pname, primers, pcr_runs, None, pp)
            with open(pp, 'rb') as f:
                st.download_button(
                    "⬇️ Download PDF Report", f.read(),
                    file_name=f"{pname}_report.pdf",
                    mime="application/pdf"
                )

    history = get_redesign_history(pid)
    if history:
        st.markdown("#### 🔄 Redesign History")
        df = pd.DataFrame(history)
        hist_cols = [
            'amplicon_num','failure_type','attempt_num',
            'extension_left','extension_right',
            'upstream_overlap_result','downstream_overlap_result',
            'reason','redesign_date'
        ]
        show_cols = [c for c in hist_cols if c in df.columns]
        st.dataframe(df[show_cols], use_container_width=True)


_render_footer()
