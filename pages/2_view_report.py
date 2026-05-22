import streamlit as st
import pandas as pd
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials


# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(
    page_title="View Progress Report",
    layout="wide"
)

# -----------------------------
# CONNECT TO GOOGLE SHEETS
# -----------------------------
@st.cache_resource
def init_connection():

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds_dict = dict(st.secrets["gcp_service_account"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        creds_dict,
        scope
    )

    client = gspread.authorize(creds)

    return client


client = init_connection()

sheet = client.open("progress report - original").sheet1


# -----------------------------
# LOAD DATA
# -----------------------------
@st.cache_data
def load_data():

    data = sheet.get_all_records()

    df = pd.DataFrame(data)

    # Boolean cleanup
    df["Completed"] = (
        df["Completed"]
        .astype(str)
        .str.strip()
        .str.lower()
        .map({"true": True, "false": False})
        .fillna(False)
        .astype(bool)
    )

    # Comments
    df["Comments"] = df["Comments"].fillna("").astype(str)

    # Dates
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    # Unique group key
    df["Key"] = (df["Widget"] != df["Widget"].shift()).cumsum()

    return df


df = load_data()

# -----------------------------
# BACKGROUND COLOR
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
col_title, col_logo = st.columns([6, 1], vertical_alignment="center")

with col_title:
    st.title("QUANTITY PROGRESS TRACKER")

with col_logo:
    st.image("logo.png", width=140)

# -----------------------------
# REFRESH BUTTON
# -----------------------------
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# -----------------------------
# FILTERS
# -----------------------------
st.markdown("### Filters")

col1, col2, col3, col4 = st.columns(4)

projects = df["Project"].dropna().unique()
project = col1.selectbox("Project", projects)

df1 = df[df["Project"] == project]

disciplines = df1["Discipline"].dropna().unique()
discipline = col2.selectbox("Discipline", disciplines)

df2 = df1[df1["Discipline"] == discipline]

areas = df2["Area"].dropna().unique()
area = col3.selectbox("Area", areas)

df3 = df2[df2["Area"] == area]

cost_codes = df3["LE - Cost code"].dropna().unique()
cost_code = col4.selectbox("Cost Code", cost_codes)

df4 = df3[df3["LE - Cost code"] == cost_code]

tasks = df4["Task"].dropna().unique()
task = st.selectbox("Task", tasks)

df_filtered = df4[df4["Task"] == task]

# -----------------------------
# PROGRESS TABLE
# -----------------------------



# Run local
# py -m streamlit run progress_v6.py

# Run on network
# py -m streamlit run progress_v6.py --server.address 0.0.0.0 --server.port 8501

# Push to GitHub
# git add .
# git commit -m "update"
# git push origin main