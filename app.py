import streamlit as st
import pandas as pd
import time
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials


# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(
    page_title="Progress Tracker",
    layout="wide"
)

# -----------------------------
# CONNECTING TO GOOGHE SHEETS
# -----------------------------
@st.cache_resource
def init_connection():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_name(
        "credentials.json", scope
    )

    client = gspread.authorize(creds)
    return client

client = init_connection()
sheet = client.open("progress report - original").sheet1

# -----------------------------
# LOAD DATA
# -----------------------------
@st.cache_data
def load_data(sheet):
    data = sheet.get_all_records()
    df = pd.DataFrame(data)

    df["Completed"] = df["Completed"].fillna(0).astype(bool)
    df["Comments"] = df["Comments"].fillna("").astype(str)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    # Create key
    df["Key"] = (df["Widget"] != df["Widget"].shift()).cumsum()

    return df


df = load_data(sheet)

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
# HEADER + LOGO
# -----------------------------
col_title, col_logo = st.columns([6, 1], vertical_alignment="center")

with col_title:
    st.title("QUANTITY PROGRESS TRACKER")

with col_logo:
    st.image("logo.png", width=140)

# 🔄 Refresh button (put here)
if st.button("🔄 Refresh data"):
    st.cache_data.clear()
    st.rerun()

# -----------------------------
# TOP CASCADING FILTERS
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

cost_codes = df3["Cost code"].dropna().unique()
cost_code = col4.selectbox("Cost Code", cost_codes)

df4 = df3[df3["Cost code"] == cost_code]

# -----------------------------
# LEFT TASK LIST
# -----------------------------
st.sidebar.markdown("### Tasks")

tasks = df4["Task"].dropna().unique()

selected_tasks = st.sidebar.multiselect(
    "Select Tasks",
    options=tasks,
    default=list(tasks)
)

df_filtered = df4[df4["Task"].isin(selected_tasks)]


# -----------------------------
# Pivoting table
# -----------------------------

df_pivot = df_filtered.pivot_table(
    index=["Key","Widget"],
    columns="Rule of credit",
    values="Completed",
    aggfunc="sum",
    fill_value = False
).reset_index()

# flatten columns
df_pivot.columns.name = None

# Convert all Rule of Credit columns to bool
exclude_cols = ["Widget", "Key"]  # add any key columns here

roc_cols = [col for col in df_pivot.columns if col not in exclude_cols]

df_pivot[roc_cols] = df_pivot[roc_cols].astype(bool)

# -----------------------------
# MAIN TABLE (NO IMAGES)
# -----------------------------
st.markdown("### Work Items")

column_config = {
    col: st.column_config.CheckboxColumn(col)
    for col in roc_cols
}

edited_df = st.data_editor(
    df_pivot,
    width="stretch",
    num_rows="dynamic",
    column_config=column_config
)

# ----------------------
# MASTER - DETAIL FORM
# ----------------------

widgets = df_filtered["Widget"].dropna().unique()

selected_widget = st.selectbox(
    "Select Widget",
    options = widgets,
    index = None,
    placeholder = 'Choose a widget...'
)

edit_mode = st.radio(
    "Edit Mode",
    ["View", "Edit"],
    horizontal=True
)

is_editable = edit_mode == "Edit"

updated_rows = []

if selected_widget:

    match = df_filtered[df_filtered["Widget"] == selected_widget]

    if match.empty:
        st.warning("No data found for this widget")
        st.stop()

    selected_key = match["Key"].iloc[0]

    df_widget = df[df["Key"] == selected_key]

    display_df = df_widget[["Rule of credit", "Date", "Comments"]]

    st.markdown("### Details")

    for i, row in display_df.iterrows():

        st.markdown(f"**{row['Rule of credit']}**")

        col1, col2 = st.columns([1, 2])

        with col1:
            new_date = st.date_input(
                f"Date_{i}",
                value=row["Date"] if pd.notna(row["Date"]) else None,
                disabled=not is_editable,
                key=f"date_{i}"
            )

        with col2:
            new_comment = st.text_area(
                f"Comment_{i}",
                value=row["Comments"],
                disabled=not is_editable,
                key=f"comment_{i}"
            )

        updated_rows.append((row["Rule of credit"], new_date, new_comment))
        
else:
    # st.info("Please select a widget to view details.")
    st.markdown(
    "<span style='color:#2b2b2b;'>Please select a widget to view details.</span>",
    unsafe_allow_html=True
)



# -----------------------------
# SAVE CHANGES
# -----------------------------

if st.button("Save Changes"):

    # Identify Rule of Credit columns
    roc_cols = [col for col in edited_df.columns if col not in exclude_cols]

    # -----------------------------
    # 1. UNPIVOT (melt)
    # -----------------------------
    df_melted = edited_df.melt(
        id_vars=["Key","Widget"],
        value_vars=roc_cols,
        var_name="Rule of credit",
        value_name="Completed"
    )

    # Ensure boolean type
    df_melted["Completed"] = df_melted["Completed"].astype(bool)

    # -----------------------------
    # 2. MERGE BACK WITH ORIGINAL DATA
    # -----------------------------
    df_updated = df.copy()

    for _, row in df_melted.iterrows():
        mask = (
            (df_updated["Key"] == row["Key"]) &
            (df_updated["Rule of credit"] == row["Rule of credit"])
        )

        df_updated.loc[mask, "Completed"] = row["Completed"]



    for roc, date, comment in updated_rows:

            mask = (
                (df_updated["Key"] == selected_key) &
                (df_updated["Rule of credit"] == roc)
            )

            df_updated.loc[mask, "Date"] = date
            df_updated.loc[mask, "Comments"] = comment


    # -----------------------------
    # 3. GOOGLE SHEET SAVE
    # -----------------------------

    df_updated["Date"] = df_updated["Date"].dt.strftime("%Y-%m-%d")
    df_updated["Date"] = df_updated["Date"].fillna("")

    # sheet.clear()
    sheet.update([df_updated.columns.values.tolist()] + df_updated.values.tolist())

    # st.success(f"Saved successfully to: {new_path}")
    st.toast("Saved successfully!", icon="✅")

    # ⏳ Wait so user can see message
    time.sleep(2)

    # 🔄 Force refresh
    st.cache_data.clear()
    st.rerun()

# Run local
# py -m streamlit run progress_v6.py

# Run on network
# py -m streamlit run progress_v6.py --server.address 0.0.0.0 --server.port 8501