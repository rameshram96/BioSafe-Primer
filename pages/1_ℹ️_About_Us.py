import base64
import mimetypes
from html import escape
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="About GE-EDIT",
    page_icon="ℹ️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Project root = parent of the "pages" folder (images/ lives next to app.py)
ROOT = Path(__file__).resolve().parent.parent

# ---------- Custom CSS ----------
st.markdown("""
<style>
/* Same as the main app: sidebar hidden, navigation via page links */
[data-testid="stSidebar"] { display: none; }
[data-testid="collapsedControl"] { display: none; }

.about-container { text-align: left; padding: 10px 0 25px 0; }

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
.section-heading { text-align: left; margin: 35px 0 25px 0; color: #166534; }
</style>
""", unsafe_allow_html=True)

st.page_link("app.py", label="← Back to GE-EDIT")


# ---------- Helpers ----------
@st.cache_data(show_spinner=False)
def image_data_uri(rel_path: str):
    """
    Return the image as a base64 data URI, or None if it cannot be found.
    Relative <img src="images/..."> paths do NOT work inside st.markdown HTML
    (the browser requests them from the Streamlit server root), so the image
    is embedded directly. If the exact file is missing, the same name with
    another common extension (jpg / jpeg / png) is tried.
    """
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
    # No leading indentation, so Markdown cannot treat it as a code block
    return (
        '<div class="developer-card">'
        f'{avatar}'
        f'<div class="developer-name">{name}</div>'
        f'<div class="developer-role">{escape(dev["role"])}</div>'
        f'<div class="developer-details">{escape(dev["details"])}</div>'
        '</div>'
    )


# ---------- About GE-EDIT ----------
st.markdown("""
<div class="about-container">
<h1>About GE-EDIT</h1>
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


# ---------- Developer Information ----------
st.markdown('<h2 class="section-heading">Meet the Developers</h2>',
            unsafe_allow_html=True)

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


# ---------- Contact ----------
st.markdown("---")
st.markdown("""
<div class="about-container">
<h3>Contact Us</h3>
<p class="about-description">
For questions, feedback, or collaboration, please contact the
Division of Plant Physiology, ICAR-IARI, New Delhi.
</p>
</div>
""", unsafe_allow_html=True)