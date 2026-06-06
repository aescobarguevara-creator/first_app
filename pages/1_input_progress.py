from xmlrpc import client

import streamlit as st
import pandas as pd
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials


# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(
    page_title="Input Progress Data",
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


# -----------------------------
# LOAD DATA
# -----------------------------

client = init_connection()

sheet = client.open("progress report - original").worksheet("progress")

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
    df["Key"] = (df["Work Unit"] != df["Work Unit"].shift()).cumsum()

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
    st.image("logo_ferrovial.jpg", width=140)

# -----------------------------
# REFRESH BUTTON
# -----------------------------
if st.button("🔄 Refresh Data"):
    load_data.clear()
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

tasks = df3["Task"].dropna().unique()
task = col4.selectbox("Task", tasks)

df4 = df3[df3["Task"] == task]

col5, col6, col7, col8 = st.columns(4)

cost_codes_options = df4["LE - Cost code"].dropna().unique()

cost_code = col5.multiselect(
    "LE Cost Code",
    options=cost_codes_options,
    default=cost_codes_options,
    placeholder = 'Multiple Selection allowed'
)

df_filtered = df4[df4["LE - Cost code"].isin(cost_code)]

# -----------------------------
# PROGRESS TABLE
# -----------------------------
st.markdown("## Progress Tracking")

roc_order = df_filtered["Rule of Credit"].drop_duplicates().tolist()

df_filtered["Rule of Credit"] = pd.Categorical(
    df_filtered["Rule of Credit"],
    categories=roc_order,
    ordered=True
)

df_pivot = df_filtered.pivot_table(
    index=["Key", "Work Unit"],
    columns="Rule of Credit",
    values="Completed",
    aggfunc="max",
    fill_value=False
).reset_index()

df_pivot.columns.name = None

exclude_cols = ["Key", "Work Unit"]

roc_cols = [c for c in df_pivot.columns if c not in exclude_cols]

df_pivot[roc_cols] = df_pivot[roc_cols].astype(bool)

column_config = {
    col: st.column_config.CheckboxColumn(col)
    for col in roc_cols
}

# -----------------------------
# FORM 1 - SAVE PROGRESS
# -----------------------------
with st.form("progress_form"):

    edited_df = st.data_editor(
        df_pivot,
        width="stretch",
        hide_index=True,
        column_config=column_config,
        num_rows="fixed"
    )

    save_progress = st.form_submit_button("Save Progress")

# -----------------------------
# SAVE PROGRESS LOGIC
# -----------------------------
if save_progress:

    df_updated = df.copy()

    today = pd.Timestamp.today().normalize()

    # Unpivot
    df_melted = edited_df.melt(
        id_vars=["Key", "Work Unit"],
        value_vars=roc_cols,
        var_name="Rule of Credit",
        value_name="Completed"
    )

    df_melted["Completed"] = df_melted["Completed"].astype(bool)

    for _, row in df_melted.iterrows():

        mask = (
            (df_updated["Key"] == row["Key"]) &
            (df_updated["Rule of Credit"] == row["Rule of Credit"])
        )

        # st.write(mask.sum())

        old_value = bool(df.loc[mask, "Completed"].iloc[0])
        new_value = bool(row["Completed"])

        # Update completed
        df_updated.loc[mask, "Completed"] = new_value

        # Auto date logic
        if (old_value is False) and (new_value is True):
            df_updated.loc[mask, "Date"] = today

        elif (old_value is True) and (new_value is False):
            df_updated.loc[mask, "Date"] = pd.NaT

    # Format dates
    df_updated["Date"] = pd.to_datetime(df_updated["Date"])
    df_updated["Date"] = df_updated["Date"].dt.strftime("%Y-%m-%d")
    df_updated["Date"] = df_updated["Date"].fillna("")

    # Push to sheet
    sheet.update(
        [df_updated.columns.values.tolist()] +
        df_updated.values.tolist()
    )

    st.toast("Progress updated!", icon="✅")

    time.sleep(1)

    st.cache_data.clear()
    st.rerun()

# =========================================================
# DETAIL EDITOR
# =========================================================

st.markdown("---")
st.markdown("## Detail Editor")

work_units = df_filtered["Work Unit"].dropna().unique()

selected_work_unit = st.selectbox(
    "Select Work Unit",
    options=work_units,
    index=None,
    placeholder="Choose a work unit..."
)

# -----------------------------
# SHOW NOTHING IF NO SELECTION
# -----------------------------
if selected_work_unit:

    match = df_filtered[df_filtered["Work Unit"] == selected_work_unit]

    selected_key = match["Key"].iloc[0]

    detail_df = df[
        df["Key"] == selected_key
    ][
        ["Rule of Credit", "Completed", "Date", "Comments"]
    ].copy()

    # -----------------------------
    # FORM 2 - DETAIL EDITOR
    # -----------------------------
    with st.form("detail_form"):

        edited_detail_df = st.data_editor(
            detail_df,
            width="stretch",
            hide_index=True,
            num_rows="fixed",
            column_config={
                "Completed": st.column_config.CheckboxColumn(
                    "Completed"
                ),
                "Date": st.column_config.DateColumn(
                    "Date",
                    format="YYYY-MM-DD"
                ),
                "Comments": st.column_config.TextColumn(
                    "Comments"
                )
            }
        )

        save_details = st.form_submit_button("Save Details")

    # -----------------------------
    # SAVE DETAIL LOGIC
    # -----------------------------
    if save_details:

        df_updated = df.copy()

        for _, row in edited_detail_df.iterrows():

            mask = (
                (df_updated["Key"] == selected_key) &
                (
                    df_updated["Rule of Credit"]
                    == row["Rule of Credit"]
                )
            )

            new_completed = bool(row["Completed"])
            new_date = pd.to_datetime(row["Date"], errors="coerce")
            new_comment = str(row["Comments"])

            # Business rule enforcement
            if pd.notna(new_date):
                new_completed = True

            if new_completed is False:
                new_date = pd.NaT

            df_updated.loc[mask, "Completed"] = new_completed
            df_updated.loc[mask, "Date"] = new_date
            df_updated.loc[mask, "Comments"] = new_comment

        # Format dates
        df_updated["Date"] = pd.to_datetime(df_updated["Date"])
        df_updated["Date"] = df_updated["Date"].dt.strftime("%Y-%m-%d")
        df_updated["Date"] = df_updated["Date"].fillna("")

        # Push to Google Sheets
        sheet.update(
            [df_updated.columns.values.tolist()] +
            df_updated.values.tolist()
        )

        st.toast("Details updated!", icon="✅")

        time.sleep(1)

        st.cache_data.clear()
        st.rerun()

# Run local
# py -m streamlit run progress_v6.py

# Run on network
# py -m streamlit run progress_v6.py --server.address 0.0.0.0 --server.port 8501

# Push to GitHub
# git add .
# git commit -m "update"
# git push origin main