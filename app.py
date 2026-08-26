from pathlib import Path
import duckdb
import pandas as pd
import streamlit as st

# ---------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------
st.set_page_config(
    page_title="retail_data",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 12 Target Core Tables
TARGET_TABLES = [
    "employees",
    "returns",
    "products",
    "suppliers",
    "categories",
    "promotions",
    "stores",
    "customers",
    "payments",
    "orders",
    "order_items",
    "shipments",
]

# Database Path Resolution (อยู่โฟลเดอร์เดียวกับ app.py)
PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = str(PROJECT_ROOT / "dev.duckdb")


# ---------------------------------------------------------
# Database Helper Functions
# ---------------------------------------------------------
@st.cache_resource
def get_connection():
    if not Path(DB_PATH).exists():
        return None
    return duckdb.connect(DB_PATH, read_only=True)


def run_query(query):
    conn = get_connection()
    if conn is None:
        return pd.DataFrame()
    try:
        return conn.execute(query).fetch_df()
    except Exception as e:
        st.error(f"Error running query: {e}")
        return pd.DataFrame()


# ---------------------------------------------------------
# Header & UI Styling
# ---------------------------------------------------------
st.markdown(
    """
    <style>
    .main-title { font-size: 2.2rem; font-weight: 700; color: #1F2937; margin-bottom: 0.2rem; }
    .subtitle { font-size: 1rem; color: #4B5563; margin-bottom: 1.5rem; }
    </style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="main-title">📊 retail_data</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="subtitle">Inspect and preview 12 core tables in dev.duckdb</div>',
    unsafe_allow_html=True,
)

# Check database existence
if not Path(DB_PATH).exists():
    st.error(f"❌ ไม่พบไฟล์ฐานข้อมูลที่: `{DB_PATH}` กรุณาตรวจสอบการสร้างไฟล์ dev.duckdb")
    st.stop()

# ---------------------------------------------------------
# Table Processing & Filtering
# ---------------------------------------------------------
tables_df = run_query(
    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
)
db_tables = (
    tables_df["table_name"].str.lower().tolist() if not tables_df.empty else []
)

# Filter for 12 target tables (including potential stg_ prefix)
available_tables = []
for target in TARGET_TABLES:
    if target in db_tables:
        available_tables.append(target)
    elif f"stg_{target}" in db_tables:
        available_tables.append(f"stg_{target}")

if not available_tables:
    st.warning("⚠️ ไม่พบตารางเป้าหมายในฐานข้อมูล กรุณาตรวจสอบว่ามีตารางอยู่ใน Schema main")
else:
    # Gather Row Counts
    table_stats = []
    for t in available_tables:
        count_df = run_query(f"SELECT COUNT(*) as count FROM main.{t}")
        count = count_df["count"].iloc[0] if not count_df.empty else 0
        table_stats.append({"table_name": t, "row_count": count})

    stats_df = pd.DataFrame(table_stats)

    # Sidebar Navigation
    st.sidebar.title("🗂️ Table Browser")
    selected_table = st.sidebar.selectbox(
        "Select a table to inspect", available_tables
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("Quick Stats")
    st.sidebar.markdown(f"**Found Target Tables:** {len(available_tables)} / 12")
    st.sidebar.markdown(f"**Total Rows:** {stats_df['row_count'].sum():,}")

    # Tabs
    tab1, tab2 = st.tabs(
        ["📋 Database Schema & Overview", "🔍 Data Viewer & Metadata"]
    )

    # ---------------------------------------------------------
    # Tab 1: Overview
    # ---------------------------------------------------------
    with tab1:
        st.subheader("Database Tables Overview (12 Core Tables)")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Tables Found", f"{len(available_tables)} / 12")
        with col2:
            st.metric(
                "Total Records Across Tables", f"{stats_df['row_count'].sum():,}"
            )

        st.markdown("### Table List & Record Counts")
        st.dataframe(
            stats_df.rename(
                columns={"table_name": "Table Name", "row_count": "Row Count"}
            ),
            use_container_width=True,
            hide_index=True,
        )

        # Missing tables warning
        found_base = [t.replace("stg_", "") for t in available_tables]
        missing = set(TARGET_TABLES) - set(found_base)
        if missing:
            st.warning(
                f"⚠️ **Missing Tables ({len(missing)}):** {', '.join(sorted(missing))}"
            )

    # ---------------------------------------------------------
    # Tab 2: Data Viewer & Metadata
    # ---------------------------------------------------------
    with tab2:
        st.subheader(f"Table Details: `{selected_table}`")

        cols_df = run_query(f"PRAGMA table_info('main.{selected_table}')")

        col1, col2 = st.columns([1, 3])
        with col1:
            st.write("**Table Summary**")
            row_cnt = stats_df[stats_df["table_name"] == selected_table][
                "row_count"
            ].values[0]
            st.write(f"- **Rows**: `{row_cnt:,}`")
            st.write(f"- **Columns**: `{len(cols_df)}`")

            st.markdown("---")
            st.write("**Columns & Types**")
            st.dataframe(
                cols_df[["name", "type"]].rename(
                    columns={"name": "Column", "type": "Type"}
                ),
                use_container_width=True,
                hide_index=True,
            )

        with col2:
            st.write("**Data Preview (First 100 rows)**")
            data_df = run_query(f"SELECT * FROM main.{selected_table} LIMIT 100")
            st.dataframe(data_df, use_container_width=True, hide_index=True)

            if not data_df.empty:
                csv_data = data_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label=f"📥 Download `{selected_table}` as CSV",
                    data=csv_data,
                    file_name=f"{selected_table}_preview.csv",
                    mime="text/csv",
                )