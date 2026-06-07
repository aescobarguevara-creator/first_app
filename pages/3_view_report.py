import streamlit as st
import pandas as pd
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.graph_objects as go


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

progress_sheet = (
    client
    .open("progress report - original")
    .worksheet("progress")
)

material_sheet = (
    client
    .open("progress report - original")
    .worksheet("material")
)

# -----------------------------
# LOAD DATA
# -----------------------------
@st.cache_data
def load_progress_data():

    data = progress_sheet.get_all_records()

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


@st.cache_data
def load_material_data():

    data = material_sheet.get_all_records()

    df = pd.DataFrame(data)

    # Comments
    df["Comments"] = df["Comments"].fillna("").astype(str)

    return df

df_progress = load_progress_data()
df_materials = load_material_data()


#-----------------------------
# Merging progress and material data
#-----------------------------

date_lookup = (
    df_progress[
        ["Key", "Rule of Credit", "Date"]
    ]
    .dropna(subset=["Date"])
    .drop_duplicates(
        subset=["Key", "Rule of Credit"]
    )
)

df_materials = df_materials.drop(columns=["Date"], errors="ignore")

df_materials = df_materials.merge(
    date_lookup,
    on=["Key", "Rule of Credit"],
    how="left"
)

# st.write(df_materials.columns)
# st.write(df_progress.columns)
# st.write(date_lookup.head())

df_materials["Date"] = pd.to_datetime(df_materials["Date"], errors="coerce")

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
    st.cache_data.clear()
    st.rerun()

# -----------------------------
# FILTERS FOR PROGRESS DATA
# -----------------------------
st.markdown("### Filters")

col1, col2, col3, col4 = st.columns(4)

projects = df_progress["Project"].dropna().unique()
project = col1.selectbox("Project", projects)

df1 = df_progress[df_progress["Project"] == project]

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

df_progress_filtered = df4[df4["LE - Cost code"].isin(cost_code)]

#-----------------------------
# Filters for materials data
#-----------------------------

df_materials_filtered = df_materials[
    (df_materials["Project"] == project) &
    (df_materials["Discipline"] == discipline) &
    (df_materials["Area"] == area) &
    (df_materials["Task"] == task)
    # (df_materials["M - Cost code"].isin(cost_code))
]

# Intermediate dfs are only needed to populate filter options, so we can clean them up to save memory

#------------------------------
# Date range filter
#------------------------------

min_date = df_progress_filtered["Date"].min()
max_date = df_progress_filtered["Date"].max()

date_range = st.slider(
    "Timeline",
    min_value=min_date.to_pydatetime(),
    max_value=max_date.to_pydatetime(),
    value=(
        min_date.to_pydatetime(),
        max_date.to_pydatetime()
    )
)

start_filter, end_filter = date_range

df_progress_filtered_time = df_progress_filtered[
    (df_progress_filtered["Date"] >= pd.to_datetime(start_filter)) &
    (df_progress_filtered["Date"] <= pd.to_datetime(end_filter))
]

df_materials_filtered_time = df_materials_filtered[
    (df_materials_filtered["Date"] >= pd.to_datetime(start_filter)) &
    (df_materials_filtered["Date"] <= pd.to_datetime(end_filter))
]

# -----------------------------
# BURNDOWN CURVE
# -----------------------------

st.markdown("### Burndown Curve")

# Preserve original ROC order
roc_order = (
    df_progress_filtered["Rule of Credit"]
    .drop_duplicates()
    .tolist()
)

# Keep only completed items with valid dates
df_burn = df_progress_filtered[
    (df_progress_filtered["Completed"] == True) &
    (df_progress_filtered["Date"].notna())
].copy()

if df_progress_filtered.empty:

    st.warning("No data available for selected filters.")

else:

    # -----------------------------
    # Calendar range
    # -----------------------------

    today = pd.Timestamp.today().normalize()
    start_date = df_progress_filtered["Date"].min()
    end_date = df_progress_filtered["Date"].max()

    # Fallback if no dates exist yet
    if pd.isna(start_date) or pd.isna(end_date):

        st.warning("No dates available yet.")

    else:

        # -----------------------------
        # Calendar table
        # -----------------------------
        calendar_df = pd.DataFrame({
            "Date": pd.date_range(
                start=start_date,
                end=end_date,
                freq="D"
            )
        })

        # -----------------------------
        # Rule of credit list
        # -----------------------------
        roc_list = roc_order[::-1]

        # -----------------------------
        # Create binary daily columns
        # -----------------------------
        for roc in roc_list:

            # Daily counts
            counts = (
                df_burn[
                    df_burn["Rule of Credit"] == roc
                ]
                .groupby("Date")
                .size()
                .reset_index(name=roc)
            )

            # Merge into calendar
            calendar_df = calendar_df.merge(
                counts,
                on="Date",
                how="left"
            )

            # Fill missing days
            calendar_df[roc] = (
                calendar_df[roc]
                .fillna(0)
                .astype(int)
            )

        # -----------------------------
        # Accumulated progress
        # -----------------------------
        for roc in roc_list:

            calendar_df[f"{roc}_acc"] = (
                calendar_df[roc]
                .cumsum()
            )

        # -----------------------------
        # Remaining quantities
        # -----------------------------
        for roc in roc_list:

            # Total planned scope
            total = (
                df_progress_filtered[
                    df_progress_filtered["Rule of Credit"] == roc
                ]
                .shape[0]
            )

            # Remaining work
            calendar_df[f"{roc}_remaining"] = (
                total -
                calendar_df[f"{roc}_acc"]
            )

        # -----------------------------
        # Chart dataframe
        # -----------------------------
        remaining_cols = [
            f"{roc}_remaining"
            for roc in roc_list
        ]

        chart_df = calendar_df[
            ["Date"] + remaining_cols
        ].copy()

        # Clean names
        rename_dict = {
            f"{roc}_remaining": roc
            for roc in roc_list
        }

        chart_df = chart_df.rename(
            columns=rename_dict
        )

        # -----------------------------
        # Area chart
        # -----------------------------

        y_max = chart_df.drop(columns="Date").max().max()

        chart_df_plot = chart_df[
            (chart_df["Date"] >= pd.to_datetime(start_filter)) &
            (chart_df["Date"] <= pd.to_datetime(end_filter))
            ]
        
        plot_cols = ["Date"] + list(chart_df_plot.columns[1:][::-1])

        chart_df_plot_reordered = chart_df_plot[plot_cols]

        fig = go.Figure()

        for roc in roc_list:

            fig.add_trace(
                go.Scatter(
                    x=chart_df_plot["Date"],
                    y=chart_df_plot[roc],
                    mode="lines",
                    name=roc,
                    fill="tozeroy"
                )
            )

        fig.update_xaxes(
            range=[
                pd.to_datetime(min_date),
                pd.to_datetime(max_date)
            ]
        )

        fig.update_yaxes(
            range=[0, y_max]
        )

        fig.update_layout(
            legend=dict(
                orientation="h",
                x=0.5,
                xanchor="center",
                y=-0.3,
                yanchor="bottom"
            )
        )

        st.plotly_chart(
            fig,
            width="stretch"
        )

        # -----------------------------
        # Define final roc
        # -----------------------------

        final_roc = roc_order[-1]
        df_final_total = df_progress_filtered[
            df_progress_filtered["Rule of Credit"] == final_roc
        ]

        df_final_time = df_progress_filtered_time[
            df_progress_filtered_time["Rule of Credit"] == final_roc
        ]

        #-----------------------------
        # Calculate metrics
        #-----------------------------

        total_widgets = df_final_total["Work Unit"].nunique()

        completed_widgets = (
            df_final_time[df_final_time["Completed"] == True]["Work Unit"]
            .nunique()
        )

        remaining_widgets = total_widgets - completed_widgets

        progress_percent = (
            completed_widgets / total_widgets * 100
            if total_widgets > 0 else 0
        )

        total_days = (end_filter - start_filter).days + 1

        production_to_date = (
            completed_widgets / (total_days / 7)
            if total_days > 0 else 0
        )

        st.markdown("### Progress metrics")

        #-----------------------------
        # Display metrics
        #-----------------------------

        # first row
        col1, col2, col3 = st.columns(3)

        col1.metric(
            label="Total Work Units",
            value=total_widgets
        )

        col2.metric(
            label="Completed Work Units",
            value=completed_widgets
        )

        col3.metric(
            label="Remaining Work Units",
            value=remaining_widgets
        )


        # Second row
        col4, col5, col6 = st.columns(3)

        col4.metric(
            label="Progress",
            value=f"{progress_percent:.1f}%"
        )

        col5.metric(
            label="To-Date Production",
            value=f"{production_to_date:.1f} work units/week"
        )

        # col6.metric(
        #     label="Last Week Speed",
        #     value=f"{speed_last_week} work units/week"
        # )


        # -----------------------------
        # Optional table
        # -----------------------------
        with st.expander("View Burndown Data"):

            st.dataframe(
                chart_df,
                width="stretch"
            )

# ------------------------------
# MATERIAL USAGE ANALYSIS
# -------------------------------

st.markdown("### Material usage")

summary = df_materials_filtered.groupby("Material").agg({
    "Units": "first",
    "Estimated Quantity": "sum",
    "Actual Quantity": "sum"
}).reset_index()

to_date = df_materials_filtered_time.groupby("Material").agg({
    "Actual Quantity": "sum"
}).reset_index()

summary = summary.merge(to_date, on="Material", how="left")

summary = summary.rename(columns={
    "Actual Quantity_x": "Actual Total",
    "Actual Quantity_y": "Actual To Date"
})

summary["Actual To Date"] = summary["Actual To Date"].fillna(0)

summary["Remaining"] = (
    summary["Actual Total"] - summary["Actual To Date"]
)

summary["% Difference"] = (
    (summary["Actual Total"] - summary["Estimated Quantity"]) / summary["Estimated Quantity"] * 100
)

# ------------------------------
# PLOTTING MATERIAL USAGE ANALYSIS
# -------------------------------

cols = st.columns(3)  # grid layout

for i, row in summary.iterrows():

    material = row["Material"]
    actual_total = row["Actual Total"]
    actual_to_date = row["Actual To Date"]
    estimate = row["Estimated Quantity"]
    remaining = row["Remaining"]
    units = row["Units"]
    pct_diff = row["% Difference"]

    col = cols[i % 3]

    gauge_max = max(estimate, actual_total,1)

    with col:

        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=actual_to_date,
            title={
                "text": (
                    f"<b>{material}</b><br>"
                    f"<span style='font-size:9px;color:gray'>{units}</span>"
                )
            },
            gauge={
                "axis": {
                    "range": [0, max(gauge_max, 1)],
                    "tickmode": "array",
                    "tickvals": [0, gauge_max*0.3,gauge_max * 0.7, gauge_max]
                },
                "bar": {"color": "royalblue"},
                "steps": [
                    {"range": [0, gauge_max * 0.7], "color": "#f7f7f7"},
                    {"range": [gauge_max * 0.7, gauge_max], "color": "#d9f2ff"},
                ],
                "threshold": {
                    "line": {"color": "red", "width": 3},
                    "thickness": 0.75,
                    "value": estimate
                }
            }
        ))

        fig.update_layout(height=280, margin=dict(l=30, r=30, t=80, b=10))

        st.metric(
            label="Estimate vs Actual",
            value=f"{pct_diff:.1f}%"
        )

        st.plotly_chart(fig, use_container_width=True)

st.write(summary)


# Run local
# py -m streamlit run progress_v6.py

# Run on network
# py -m streamlit run progress_v6.py --server.address 0.0.0.0 --server.port 8501

# Push to GitHub
# git add .
# git commit -m "update"
# git push origin main