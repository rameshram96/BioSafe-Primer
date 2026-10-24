import base64
import mimetypes
from html import escape
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="GE-EDIT · About & Policies",
    page_icon="ℹ️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Project root = parent of the "pages" folder (images/ lives next to app.py)
ROOT = Path(__file__).resolve().parent.parent

# ---------- Custom CSS ----------
st.markdown("""
<style>
[data-testid="stSidebar"] { display: none; }
[data-testid="collapsedControl"] { display: none; }

.about-container { text-align: left; padding: 10px 0 25px 0; }

.nav a {
    display: inline-block; margin: 0 10px 8px 0; padding: 5px 14px;
    border-radius: 999px; background: #ecfdf5; color: #166534;
    font-weight: 600; font-size: 14px; text-decoration: none;
    border: 1px solid #d1fae5;
}
.nav a:hover { background: #d1fae5; }

.developer-card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 16px;
    padding: 25px 15px;
    text-align: center;
    min-height: 290px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.developer-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 8px 22px rgba(0,0,0,0.10);
}
.profile-image {
    width: 125px; height: 125px; border-radius: 50%;
    object-fit: cover; border: 4px solid #d1fae5;
    margin: 0 auto 15px auto; display: block;
}
.profile-placeholder {
    width: 125px; height: 125px; border-radius: 50%;
    border: 4px solid #d1fae5; background: #ecfdf5; color: #166534;
    font-size: 40px; font-weight: 700;
    margin: 0 auto 15px auto;
    display: flex; align-items: center; justify-content: center;
}
.developer-name { font-size: 19px; font-weight: 700; color: #166534; margin-bottom: 5px; }
.developer-role { font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 10px; }
.developer-details { font-size: 13px; line-height: 1.6; color: #6b7280; }
.about-description { font-size: 16px; line-height: 1.8; color: #4b5563; }
.section-heading { text-align: left; margin: 25px 0 20px 0; color: #166534; }
.callout {
    background: #FCF3E3; border-left: 3px solid #B4790F;
    border-radius: 6px; padding: 10px 14px; font-size: 14px; margin: 10px 0 16px;
}
</style>
""", unsafe_allow_html=True)

st.page_link("app.py", label="← Back to GE-EDIT")
st.markdown(
    '<div class="nav">'
    '<a href="#about-ge-edit">ℹ️ About</a>'
    '<a href="#meet-the-developers">👥 Developers</a>'
    '<a href="#privacy-policy">🔒 Privacy Policy</a>'
    '<a href="#data-storage-disclosure">💾 Data Storage Disclosure</a>'
    '<a href="#contact-us">✉️ Contact</a>'
    '</div>',
    unsafe_allow_html=True,
)


# ---------- Helpers ----------
@st.cache_data(show_spinner=False)
def image_data_uri(rel_path: str):
    """Return the image as a base64 data URI, or None if it cannot be found.
    Relative <img src> paths do not work inside st.markdown HTML, so the image
    is embedded directly. If the exact file is missing, the same name with
    another common extension (jpg / jpeg / png) is tried."""
    base = ROOT / rel_path
    candidates = [base] + [base.with_suffix(ext) for ext in (".jpg", ".jpeg", ".png")]
    for path in candidates:
        if path.is_file():
            mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
            return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()
    return None


def initials(name: str) -> str:
    words = [w for w in name.replace(".", ". ").split() if w.lower() not in ("dr", "dr.")]
    return "".join(w[0] for w in words[:2]).upper() or "?"


def developer_card(dev: dict) -> str:
    name = escape(dev["name"])
    uri = image_data_uri(dev["image"])
    if uri:
        avatar = f'<img src="{uri}" class="profile-image" alt="{name}">'
    else:
        avatar = f'<div class="profile-placeholder">{escape(initials(dev["name"]))}</div>'
    return (
        '<div class="developer-card">'
        f'{avatar}'
        f'<div class="developer-name">{name}</div>'
        f'<div class="developer-role">{escape(dev["role"])}</div>'
        f'<div class="developer-details">{escape(dev["details"])}</div>'
        '</div>'
    )


# ══════════════════════════════════════════════════════════════════════════════
# ABOUT
# ══════════════════════════════════════════════════════════════════════════════
st.header("About GE-EDIT", anchor="about-ge-edit", divider="green")
st.markdown("""
<div class="about-container">
<p class="about-description">
GE-EDIT is a tool for designing overlapping PCR primers across full
plasmid/vector sequences, built to support regulatory exemption workflows
for genome-edited plants and general vector verification in plant
molecular biology.
</p>
<p class="about-description">
It automates primer design using Primer3, overlap validation,
circular vector closure, PCR progress tracking, and report generation,
replacing manual spreadsheet-based primer design workflows.
</p>
<p class="about-description">
<b>Developed and maintained by:</b><br>
Division of Plant Physiology, ICAR–Indian Agricultural Research
Institute (ICAR-IARI), New Delhi.
</p>
</div>
""", unsafe_allow_html=True)

# ---------- Developers ----------
st.subheader("Meet the Developers", anchor="meet-the-developers")

developers = [
    {
        "name": "Ramesh Ramasamy",
        "role": "Lead Developer",
        "details": "PhD Scholar, Division of Plant Physiology, ICAR-IARI, New Delhi",
        "image": "images/developer1.jpg",
    },
    {
        "name": "Dr. Soham Ray",
        "role": "Co-Developer",
        "details": "Senior Scientist, Division of Plant Physiology, ICAR-IARI, New Delhi",
        "image": "images/developer2.jpg",
    },
    {
        "name": "Dr. Joshitha Vijayan",
        "role": "Molecular Biology Specialist",
        "details": "Scientist (Senior Scale), ICAR-National Institute for Plant Biotechnology (NIPB), New Delhi",
        "image": "images/developer3.jpg",
    },
    {
        "name": "Dr. Viswanathan Chinnusamy",
        "role": "Research Support",
        "details": "JD (R), Principal Scientist, Division of Plant Physiology, ICAR-IARI, New Delhi",
        "image": "images/developer4.png",
    },
]

columns = st.columns(4, gap="medium")
for col, dev in zip(columns, developers):
    with col:
        st.markdown(developer_card(dev), unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PRIVACY POLICY
# ══════════════════════════════════════════════════════════════════════════════
st.write("")
st.header("Privacy Policy", anchor="privacy-policy", divider="green")
st.markdown("""
GE-EDIT does not collect, store, or transmit any personal data.

- No user accounts, logins, or personal identifiers are required or collected.
- No third-party trackers or analytics are used within the application. (The Streamlit
  framework itself may use technical cookies that are needed for the app to function.)
- No usage data is logged or sent to any external server by this application.
- All uploaded sequences, primers, gel images, and project data are processed only for your
  active session. They are not written to a database or permanent storage and are not shared
  with anyone (see *Data Storage Disclosure* below).

GE-EDIT is an independent tool developed entirely by the research team of the Division of Plant
Physiology, ICAR-Indian Agricultural Research Institute. It is not part of, affiliated with,
endorsed by, or linked to the Department of Biotechnology (DBT), Ministry of Science and
Technology, Government of India. The tool is designed on the basis of the guidelines issued by
the DBT. Users are requested to verify the current official guidelines and cross-check the
tool's outputs against them before use or submission.

**Note on hosting and fonts:** Depending on where this application is deployed or accessed from,
the underlying hosting platform (e.g. a web server) may generate standard technical access logs
(such as IP address and timestamp) outside of this application's control, as is common for any
web-hosted service. GE-EDIT itself does not access, use, or store this information. In addition,
the interface loads the IBM Plex fonts from Google Fonts, so your browser makes a request to
Google's servers when the page loads.

Because nothing is retained by the application after your session ends, there is nothing for us
to access, share, or delete.
""")

# ══════════════════════════════════════════════════════════════════════════════
# DATA STORAGE DISCLOSURE
# ══════════════════════════════════════════════════════════════════════════════
st.header("Data Storage Disclosure", anchor="data-storage-disclosure", divider="green")
st.markdown("""
<div class="callout">⚠️ <strong>No auto-save.</strong> GE-EDIT does not save your project to any
database or user account. If the page refreshes, disconnects or times out, unsaved work is lost.
Download your <strong>.gedit</strong> project file often.</div>
""", unsafe_allow_html=True)

st.markdown("""
| Data | Where it lives | How long |
|---|---|---|
| Vector sequence, primers, PCR runs, control primers, redesign history, gel images | Temporary **session memory** while your session is open | Until you close or refresh the page, or the session times out |
| Project file (`.gedit`) | **Your own computer**, only when you click download | Until you delete it. You control it |
| Excel / CSV / GenBank / Word / PDF exports | Generated on request and sent to your browser for download | Not retained by the app after download |

- The `.gedit` file is a plain JSON file containing *everything*: the full vector sequence, primers,
  run log, control primers, and gel images (embedded). Treat it as confidential if your data are.
- To resume work, upload your `.gedit` file on the Project Hub.
- While your session is active, the data is held in the memory of the server process running
  the app, and it is discarded when the session ends. The app does not write it to a database
  or permanent storage.
- Using **← Close Project** removes the project from the session.
""")

# ══════════════════════════════════════════════════════════════════════════════
# CONTACT
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("Contact Us", anchor="contact-us")
st.markdown("""
<div class="about-container">
<p class="about-description">
For questions, feedback, or collaboration, please contact the
Division of Plant Physiology, ICAR-IARI, New Delhi.
</p>
</div>
""", unsafe_allow_html=True)

st.page_link("app.py", label="← Back to GE-EDIT")