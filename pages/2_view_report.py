import streamlit as st
import pandas as pd
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials


# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(
    page_title="Quantity Progress Report",
    layout="wide"
)



# Run local
# py -m streamlit run progress_v6.py

# Run on network
# py -m streamlit run progress_v6.py --server.address 0.0.0.0 --server.port 8501

# Push to GitHub
# git add .
# git commit -m "update"
# git push origin main