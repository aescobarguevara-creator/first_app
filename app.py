import streamlit as st

# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(
    page_title="Progress Tracker",
    layout="wide"
)

# -----------------------------
# STYLING
# -----------------------------
st.markdown("""
<style>
.stApp {
    background-color: #ebb700;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# HEADER
# -----------------------------
col1, col2 = st.columns([6, 1])

with col1:
    st.title("QUANTITY PROGRESS TRACKER")

with col2:
    st.image("logo.png", width=140)

# -----------------------------
# HOME PAGE
# -----------------------------
st.markdown("---")

st.markdown("""
## Welcome

Use the sidebar to navigate between:

- **Input Data** → update progress, dates, and comments
- **View Report** → dashboards, charts, and metrics
""")

# Run local
# py -m streamlit run progress_v6.py

# Run on network
# py -m streamlit run progress_v6.py --server.address 0.0.0.0 --server.port 8501

# Push to GitHub
# git add .
# git commit -m "update"
# git push origin main