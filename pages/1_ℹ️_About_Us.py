import streamlit as st

st.set_page_config(page_title="About Us", page_icon="ℹ️")

st.markdown("""
### About BioSafe Primer
BioSafe Primer is a tool for designing overlapping PCR primers across full plasmid/vector
sequences, built to support GMO regulatory exemption workflows and general vector
verification in plant molecular biology.

It automates primer design (via Primer3), overlap validation, circular vector closure,
PCR progress tracking, and report generation — replacing manual spreadsheet-based primer
design workflows.

**Developed and maintained by:** Division of Plant Physiology, ICAR–Indian Agricultural
Research Institute (ICAR-IARI).

For questions or feedback, please contact the Division of Plant Physiology, ICAR-IARI.
""")