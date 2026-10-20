import streamlit as st

st.set_page_config(page_title="Data Storage Disclosure", page_icon="💾")

st.markdown("""
### Data Storage Disclosure
**What is stored:** Nothing, on our end. BioSafe Primer performs all computation (primer
design, validation, map rendering, report generation) in-memory during your active
session only.

**What this means practically:**
- Refreshing the page, closing the browser tab, or a session timeout will permanently
  erase all unsaved project data (primers, gel images, PCR run logs, redesign history).
- The only way to persist your work is to download the **.bsp project file**
  (💾 Save Project), which contains your complete project state, and re-upload it in a
  future session to resume.
- Exported files (Excel, PDF, GenBank, CSV) are generated on demand and are not retained
  after download.

**Uploaded files:** FASTA/GenBank sequence files and gel images you upload are held only
in memory for the duration of your session and are discarded when the session ends —
they are not saved to any server or database.
""")