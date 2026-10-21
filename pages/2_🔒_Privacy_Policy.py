import streamlit as st

st.set_page_config(page_title="Privacy Policy", page_icon="🔒")

st.markdown("""
### Privacy Policy
BioSafe Primer does not collect, store, or transmit any personal data.

- No user accounts, logins, or personal identifiers are required or collected.
- No cookies or third-party trackers/analytics are used within the application.
- No usage data is logged or sent to any external server by this application.
- All uploaded sequences, primers, gel images, and project data are processed only in
  your active browser session and are never transmitted to or stored on our servers.

GE-EDIT is an independent tool developed entirely by the research team of the Division of Plant Physiology, ICAR-Indian Agricultural Research Institute. It is not part of, affiliated with, endorsed by, or linked to the Department of Biotechnology (DBT), Ministry of Science and Technology, Government of India. The tool is designed on the basis of the guidelines issued by the DBT. Users are requested to verify the current official guidelines and cross-check the tool’s outputs against them before use or submission.

**Note on hosting:** Depending on where this application is deployed or accessed from,
the underlying hosting platform (e.g. a web server) may generate standard technical
access logs (such as IP address and timestamp) outside of this application's control,
as is common for any web-hosted service. BioSafe Primer itself does not access, use, or
store this information.

Because nothing is retained by the application after your session ends, there is nothing
for us to access, share, or delete — your data simply exists temporarily in your browser
session and disappears when it ends.
""")