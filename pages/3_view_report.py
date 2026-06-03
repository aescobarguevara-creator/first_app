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

#------------------------------
# Date range filter
#------------------------------

min_date = df["Date"].min()
max_date = df["Date"].max()

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

# -----------------------------
# BURNDOWN CURVE
# -----------------------------

st.markdown("### Burndown Curve")

# Preserve original ROC order
roc_order = (
    df_filtered["Rule of credit"]
    .drop_duplicates()
    .tolist()
)

# Keep only completed items with valid dates
df_burn = df_filtered[
    (df_filtered["Completed"] == True) &
    (df_filtered["Date"].notna())
].copy()

if df_filtered.empty:

    st.warning("No data available for selected filters.")

else:

    # -----------------------------
    # Calendar range
    # -----------------------------

    today = pd.Timestamp.today().normalize()
    start_date = df_filtered["Date"].min()
    end_date = df_filtered["Date"].max()

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
                    df_burn["Rule of credit"] == roc
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
                df_filtered[
                    df_filtered["Rule of credit"] == roc
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
        df_final = df_filtered[
            df_filtered["Rule of credit"] == final_roc
        ]

        #-----------------------------
        # Calculate metrics
        #-----------------------------

        total_widgets = df_final["Work Unit"].nunique()

        completed_widgets = (
            df_final[df_final["Completed"] == True]["Work Unit"]
            .nunique()
        )

        remaining_widgets = total_widgets - completed_widgets

        progress_percent = (
            completed_widgets / total_widgets * 100
            if total_widgets > 0 else 0
        )

        total_days = (end_date - start_date).days + 1

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


        st.markdown("### Material usage")

# Run local
# py -m streamlit run progress_v6.py

# Run on network
# py -m streamlit run progress_v6.py --server.address 0.0.0.0 --server.port 8501

# Push to GitHub
# git add .
# git commit -m "update"
# git push origin main