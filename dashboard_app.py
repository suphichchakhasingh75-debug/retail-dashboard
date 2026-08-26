import os
from pathlib import Path
import duckdb
import pandas as pd
import streamlit as st
import altair as alt

# --- Page Config & Modern Styling ---
st.set_page_config(
    page_title="Retail Enterprise Dashboard",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.95));
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 12px;
        padding: 16px 18px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
        backdrop-filter: blur(8px);
    }
    div[data-testid="stMetricLabel"] > label {
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        color: #94a3b8 !important;
        letter-spacing: 0.5px;
    }
    div[data-testid="stMetricValue"] > div {
        font-size: 1.35rem !important;
        font-weight: 700 !important;
        color: #f8fafc !important;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    button[data-baseweb="tab"] {
        font-weight: 600 !important;
        border-radius: 8px 8px 0 0 !important;
        padding: 8px 20px !important;
    }
    .main .block-container { 
        padding-top: 2rem; 
        max-width: 95%;
    }
</style>
""", unsafe_allow_html=True)

PROJECT_ROOT = Path(__file__).resolve().parent
WEEKDAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def get_dataset_dir():
    candidates = [
        PROJECT_ROOT / "retail_data" / "datasets",
        PROJECT_ROOT / "datasets",
        PROJECT_ROOT,
        Path.cwd() / "datasets",
        Path.cwd(),
    ]
    for candidate in candidates:
        if candidate.exists() and (candidate / "orders.csv").exists():
            return candidate
    return None


@st.cache_data
def load_full_dataset():
    dataset_dir = get_dataset_dir()
    if not dataset_dir:
        return pd.DataFrame(), pd.DataFrame()

    con = duckdb.connect(":memory:")

    def get_source(filename, fallback_sql):
        file_path = dataset_dir / filename
        if file_path.exists():
            p_str = str(file_path).replace("\\", "/")
            return f"read_csv_auto('{p_str}')"
        return f"({fallback_sql})"

    try:
        orders_src = get_source("orders.csv", "SELECT NULL::INT AS order_id, NULL::DATE AS order_date, NULL::INT AS customer_id, NULL::INT AS store_id, NULL::INT AS promotion_id WHERE 1=0")
        items_src = get_source("order_items.csv", "SELECT NULL::INT AS order_item_id, NULL::INT AS order_id, NULL::INT AS product_id, 0 AS qty, 0.0 AS price WHERE 1=0")
        products_src = get_source("products.csv", "SELECT NULL::INT AS product_id, NULL::INT AS category_id, NULL::INT AS supplier_id, 0.0 AS price WHERE 1=0")
        categories_src = get_source("categories.csv", "SELECT NULL::INT AS category_id, 'Uncategorized' AS category_name WHERE 1=0")
        suppliers_src = get_source("suppliers.csv", "SELECT NULL::INT AS supplier_id, 'Unknown Country' AS country WHERE 1=0")
        customers_src = get_source("customers.csv", "SELECT NULL::INT AS customer_id, 'Unknown Customer City' AS city, NULL::DATE AS signup_date WHERE 1=0")
        stores_src = get_source("stores.csv", "SELECT NULL::INT AS store_id, 'Unknown Store City' AS city WHERE 1=0")
        promos_src = get_source("promotions.csv", "SELECT NULL::INT AS promotion_id, 0.0 AS discount WHERE 1=0")
        returns_src = get_source("returns.csv", "SELECT NULL::INT AS order_item_id, 0.0 AS refund WHERE 1=0")
        shipments_src = get_source("shipments.csv", "SELECT NULL::INT AS order_id, 'Pending' AS status WHERE 1=0")
        payments_src = get_source("payments.csv", "SELECT NULL::INT AS order_id, 0.0 AS amount WHERE 1=0")
        employees_src = get_source("employees.csv", "SELECT NULL::INT AS employee_id, NULL::INT AS store_id, 0.0 AS salary WHERE 1=0")

        # 1. Main Order-Items Transaction Data
        query_main = f"""
            WITH base_promos AS (
                SELECT 
                    promotion_id,
                    CASE 
                        WHEN discount > 1 THEN discount / 100.0 
                        ELSE COALESCE(discount, 0.0) 
                    END AS norm_discount
                FROM {promos_src}
            )
            SELECT 
                o.order_id,
                CAST(o.order_date AS DATE) AS order_date,
                o.store_id,
                oi.order_item_id,
                oi.product_id,
                'Product #' || CAST(COALESCE(oi.product_id, 0) AS VARCHAR) AS product_name,
                COALESCE(c.category_name, 'Uncategorized') AS category_name,
                COALESCE(sup.country, 'Unknown Country') AS supplier_country,
                COALESCE(st.city, 'Unknown Store City') AS store_city,
                COALESCE(cust.city, 'Unknown Customer City') AS customer_city,
                CAST(cust.signup_date AS DATE) AS customer_signup_date,
                'Customer #' || CAST(o.customer_id AS VARCHAR) AS customer_label,
                COALESCE(oi.qty, 0) AS quantity,
                COALESCE(oi.price, 0.0) AS unit_price,
                COALESCE(pro.norm_discount, 0.0) AS discount_rate,
                (COALESCE(oi.qty, 0) * COALESCE(oi.price, 0.0) * (1 - COALESCE(pro.norm_discount, 0.0))) AS revenue,
                (COALESCE(oi.qty, 0) * COALESCE(oi.price, 0.0) * COALESCE(pro.norm_discount, 0.0)) AS discount_amount,
                COALESCE(pay.total_payment, 0.0) AS total_payment,
                COALESCE(ret.return_count, 0) > 0 AS is_returned,
                COALESCE(ret.refund_total, 0.0) AS refund_amount,
                COALESCE(shp.status, 'Pending') AS shipment_status
            FROM {orders_src} o
            LEFT JOIN {items_src} oi ON o.order_id = oi.order_id
            LEFT JOIN {products_src} prod ON oi.product_id = prod.product_id
            LEFT JOIN {categories_src} c ON prod.category_id = c.category_id
            LEFT JOIN {suppliers_src} sup ON prod.supplier_id = sup.supplier_id
            LEFT JOIN {customers_src} cust ON o.customer_id = cust.customer_id
            LEFT JOIN {stores_src} st ON o.store_id = st.store_id
            LEFT JOIN base_promos pro ON o.promotion_id = pro.promotion_id
            LEFT JOIN (
                SELECT order_item_id, COUNT(*) AS return_count, SUM(refund) AS refund_total
                FROM {returns_src}
                GROUP BY order_item_id
            ) ret ON oi.order_item_id = ret.order_item_id
            LEFT JOIN (
                SELECT order_id, status
                FROM (
                    SELECT order_id, status, ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY order_id) AS rn
                    FROM {shipments_src}
                ) WHERE rn = 1
            ) shp ON o.order_id = shp.order_id
            LEFT JOIN (
                SELECT order_id, SUM(amount) AS total_payment 
                FROM {payments_src} 
                GROUP BY order_id
            ) pay ON o.order_id = pay.order_id
        """

        # 2. Employee HR Summary Table
        query_employees = f"""
            SELECT 
                e.employee_id,
                e.store_id,
                e.salary,
                COALESCE(st.city, 'Unknown Store City') AS store_city
            FROM {employees_src} e
            LEFT JOIN {stores_src} st ON e.store_id = st.store_id
        """

        df_main = con.execute(query_main).fetchdf()
        df_emp = con.execute(query_employees).fetchdf()

        return process_dataframe(df_main), df_emp
    except Exception as e:
        st.error(f"Error executing DuckDB Query: {e}")
        return pd.DataFrame(), pd.DataFrame()
    finally:
        con.close()


def process_dataframe(df):
    if df.empty:
        return df
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    df = df.dropna(subset=["order_date"]).copy()
    df["year"] = df["order_date"].dt.year
    df["quarter_label"] = df["order_date"].dt.year.astype(str) + "-Q" + df["order_date"].dt.quarter.astype(str)
    df["month_name"] = df["order_date"].dt.strftime("%Y-%m (%B)")
    df["date_label"] = df["order_date"].dt.strftime("%Y-%m-%d")
    df["day_name"] = df["order_date"].dt.strftime("%A")
    if "customer_signup_date" in df.columns:
        df["signup_year"] = pd.to_datetime(df["customer_signup_date"], errors="coerce").dt.year.fillna(0).astype(int)
    if "shipment_status" in df.columns:
        df["shipment_status"] = df["shipment_status"].astype(str).str.title()
    return df


def main():
    st.title("🛍️ Retail Enterprise Dashboard")
    st.caption("ระบบวิเคราะห์ข้อมูลการขายและทรัพยากรบุคคล (OLAP + HR Analytics)")

    df, df_emp = load_full_dataset()
    if df.empty:
        st.warning("⚠️ ไม่พบข้อมูลไฟล์ CSV ในโฟลเดอร์ที่กำหนด")
        return

    st.sidebar.header("🔍 ตัวกรองข้อมูล (Filters)")
    min_d, max_d = df["order_date"].min().date(), df["order_date"].max().date()

    date_range = st.sidebar.date_input(
        "ช่วงวันที่", [min_d, max_d], min_value=min_d, max_value=max_d
    )
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        start_d, end_d = date_range
    elif isinstance(date_range, (list, tuple)) and len(date_range) == 1:
        start_d = end_d = date_range[0]
    else:
        start_d = end_d = date_range

    cities = st.sidebar.multiselect(
        "สาขาตามเมือง (Store City)",
        options=sorted(df["store_city"].dropna().unique()),
        default=df["store_city"].dropna().unique(),
    )
    categories = st.sidebar.multiselect(
        "หมวดหมู่สินค้า",
        options=sorted(df["category_name"].dropna().unique()),
        default=df["category_name"].dropna().unique(),
    )

    df_filtered = df[
        (df["order_date"].dt.date >= start_d)
        & (df["order_date"].dt.date <= end_d)
        & (df["store_city"].isin(cities))
        & (df["category_name"].isin(categories))
    ]

    if df_filtered.empty:
        st.info("ไม่มีข้อมูลตรงกับเงื่อนไขตัวกรองที่เลือก")
        return

    # Filtered Employee Data based on selected Store Cities
    df_emp_filtered = df_emp[df_emp["store_city"].isin(cities)] if not df_emp.empty else pd.DataFrame()

    rev = df_filtered["revenue"].sum()
    orders = df_filtered["order_id"].nunique()
    qty = df_filtered["quantity"].sum()
    refunds = df_filtered["refund_amount"].sum()
    disc_val = df_filtered["discount_amount"].sum()
    
    total_emp = len(df_emp_filtered)
    total_payroll = df_emp_filtered["salary"].sum() if not df_emp_filtered.empty else 0
    rev_per_emp = (rev / total_emp) if total_emp > 0 else 0

    # Key Performance Indicators
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("ยอดขายรวม (Revenue)", f"${rev:,.0f}")
    k2.metric("จำนวนออเดอร์", f"{orders:,.0f}")
    k3.metric("สินค้าที่ขายได้", f"{qty:,.0f} ชิ้น")
    k4.metric("ยอดคืนเงิน (Refunds)", f"${refunds:,.0f}")
    k5.metric("ส่วนลดรวม (Discounts)", f"${disc_val:,.0f}")
    k6.metric("ยอดขาย/พนักงาน", f"${rev_per_emp:,.0f}")

    st.markdown("---")

    t1, t2, t3, t4, t5 = st.tabs([
        "📈 ยอดขาย & เวลา",
        "📦 การคืนสินค้า & ขนส่ง",
        "🎟️ โปรโมชัน & ชำระเงิน",
        "🏬 สาขา & ซัพพลายเออร์ (HR)",
        "👤 พฤติกรรมลูกค้า",
    ])

    # --- TAB 1: ยอดขาย & เวลา ---
    with t1:
        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader("แนวโน้มยอดขายตามช่วงเวลา")
            t_level = st.selectbox(
                "มุมมองเวลา", ["date_label", "month_name", "quarter_label", "day_name"], index=0
            )
            t_df = df_filtered.groupby(t_level, as_index=False)["revenue"].sum()
            x_sort = WEEKDAY_ORDER if t_level == "day_name" else None

            chart = alt.Chart(t_df).mark_line(point=True, color="#38bdf8", strokeWidth=3).encode(
                x=alt.X(f"{t_level}:N", title="ช่วงเวลา", sort=x_sort),
                y=alt.Y("revenue:Q", title="ยอดขาย ($)"),
                tooltip=[t_level, alt.Tooltip("revenue:Q", format="$,.2f")],
            ).properties(height=340)
            st.altair_chart(chart, use_container_width=True)

        with c2:
            st.subheader("ยอดขายตามหมวดหมู่สินค้า")
            cat_df = (
                df_filtered.groupby("category_name", as_index=False)["revenue"]
                .sum()
                .sort_values("revenue", ascending=False)
            )
            cat_chart = alt.Chart(cat_df).mark_bar(cornerRadiusEnd=6, color="#10b981").encode(
                x=alt.X("revenue:Q", title="ยอดขาย ($)"),
                y=alt.Y("category_name:N", sort="-x", title="หมวดหมู่"),
                tooltip=["category_name", alt.Tooltip("revenue:Q", format="$,.2f")],
            ).properties(height=340)
            st.altair_chart(cat_chart, use_container_width=True)

    # --- TAB 2: การคืนสินค้า & ขนส่ง ---
    with t2:
        r1, r2 = st.columns(2)
        with r1:
            st.subheader("ยอดเงินคืน (Refunds) ตามหมวดหมู่")
            ret_df = (
                df_filtered[df_filtered["is_returned"] == True]
                .groupby("category_name", as_index=False)["refund_amount"]
                .sum()
            )
            ret_chart = alt.Chart(ret_df).mark_bar(cornerRadiusEnd=6, color="#f43f5e").encode(
                x=alt.X("refund_amount:Q", title="มูลค่าเงินคืน ($)"),
                y=alt.Y("category_name:N", sort="-x", title="หมวดหมู่"),
                tooltip=["category_name", alt.Tooltip("refund_amount:Q", format="$,.2f")],
            ).properties(height=300)
            st.altair_chart(ret_chart, use_container_width=True)

        with r2:
            st.subheader("สัดส่วนสถานะการจัดส่ง (Shipment Status)")
            shp_df = df_filtered.groupby("shipment_status", as_index=False)["order_id"].nunique()
            shp_chart = alt.Chart(shp_df).mark_arc(innerRadius=45, cornerRadius=4).encode(
                theta=alt.Theta("order_id:Q"),
                color=alt.Color("shipment_status:N", scale=alt.Scale(scheme="tableau10"), title="สถานะ"),
                tooltip=["shipment_status", alt.Tooltip("order_id:Q", title="จำนวนออเดอร์", format=",d")],
            ).properties(height=300)
            st.altair_chart(shp_chart, use_container_width=True)

    # --- TAB 3: โปรโมชัน & ชำระเงิน ---
    with t3:
        p1, p2 = st.columns(2)
        with p1:
            st.subheader("ผลกระทบของส่วนลดต่อยอดขาย")
            df_filtered_promo = df_filtered.copy()
            df_filtered_promo["discount_percent_val"] = (df_filtered_promo["discount_rate"] * 100).round(0).astype(int)
            
            promo_df = df_filtered_promo.groupby("discount_percent_val", as_index=False).agg(
                total_revenue=("revenue", "sum"),
                total_orders=("order_id", "nunique"),
            )
            promo_df["discount_percent"] = promo_df["discount_percent_val"].astype(str) + "%"
            promo_df = promo_df.sort_values("discount_percent_val")

            p_chart = alt.Chart(promo_df).mark_bar(cornerRadiusEnd=6, color="#f59e0b").encode(
                x=alt.X("discount_percent:N", title="อัตราส่วนลด", sort=list(promo_df["discount_percent"])),
                y=alt.Y("total_revenue:Q", title="ยอดขายรวม ($)"),
                tooltip=["discount_percent", alt.Tooltip("total_revenue:Q", format="$,.2f"), "total_orders"],
            ).properties(height=320)
            st.altair_chart(p_chart, use_container_width=True)

        with p2:
            st.subheader("ยอดการชำระเงินเทียบกับยอดขาย")
            actual_payments = df_filtered.drop_duplicates("order_id")["total_payment"].sum()

            pay_df = pd.DataFrame({
                "Category": ["Gross Sales", "Payments Received", "Discounts Given"],
                "Amount": [rev, actual_payments, disc_val],
            })
            pay_chart = alt.Chart(pay_df).mark_bar(cornerRadiusEnd=6, color="#8b5cf6").encode(
                x=alt.X("Amount:Q", title="มูลค่า ($)"),
                y=alt.Y("Category:N", sort="-x", title="รายการ"),
                tooltip=["Category", alt.Tooltip("Amount:Q", format="$,.2f")],
            ).properties(height=320)
            st.altair_chart(pay_chart, use_container_width=True)

    # --- TAB 4: สาขา, ซัพพลายเออร์ & HR ---
    with t4:
        s1, s2 = st.columns(2)
        with s1:
            st.subheader("ยอดขาย & จำนวนพนักงานตามเมือง")
            st_df = (
                df_filtered.groupby("store_city", as_index=False)["revenue"]
                .sum()
                .sort_values("revenue", ascending=False)
            )
            st.altair_chart(
                alt.Chart(st_df).mark_bar(cornerRadiusEnd=6, color="#6366f1").encode(
                    x=alt.X("revenue:Q", title="ยอดขาย ($)"),
                    y=alt.Y("store_city:N", sort="-x", title="เมืองที่ตั้งสาขา"),
                    tooltip=["store_city", alt.Tooltip("revenue:Q", format="$,.2f")],
                ).properties(height=280),
                use_container_width=True,
            )

        with s2:
            st.subheader("ยอดขายแบ่งตามประเทศซัพพลายเออร์")
            sup_df = (
                df_filtered.groupby("supplier_country", as_index=False)["revenue"]
                .sum()
                .sort_values("revenue", ascending=False)
            )
            st.altair_chart(
                alt.Chart(sup_df).mark_bar(cornerRadiusEnd=6, color="#06b6d4").encode(
                    x=alt.X("revenue:Q", title="ยอดขาย ($)"),
                    y=alt.Y("supplier_country:N", sort="-x", title="ประเทศ"),
                    tooltip=["supplier_country", alt.Tooltip("revenue:Q", format="$,.2f")],
                ).properties(height=280),
                use_container_width=True,
            )

        if not df_emp_filtered.empty:
            st.subheader("📊 สถิติด้านทรัพยากรบุคคล (HR & Staffing Analysis)")
            hr_city = df_emp_filtered.groupby("store_city", as_index=False).agg(
                headcount=("employee_id", "count"),
                total_payroll=("salary", "sum"),
                avg_salary=("salary", "mean"),
            )
            hr_city = pd.merge(st_df, hr_city, on="store_city", how="outer").fillna(0)
            
            hr_city["revenue_per_emp"] = hr_city.apply(
                lambda x: x["revenue"] / x["headcount"] if x["headcount"] > 0 else 0, axis=1
            )
            hr_city["payroll_to_revenue_%"] = hr_city.apply(
                lambda x: (x["total_payroll"] / x["revenue"]) * 100 if x["revenue"] > 0 else 0, axis=1
            )

            st.dataframe(
                hr_city.style.format({
                    "headcount": "{:,.0f}",
                    "total_payroll": "${:,.2f}",
                    "avg_salary": "${:,.2f}",
                    "revenue": "${:,.2f}",
                    "revenue_per_emp": "${:,.2f}",
                    "payroll_to_revenue_%": "{:.2f}%",
                }),
                use_container_width=True,
            )

    # --- TAB 5: พฤติกรรมลูกค้า ---
    with t5:
        u1, u2 = st.columns([1.5, 1])
        with u1:
            st.subheader("Top ลูกค้าที่มียอดซื้อสูงสุด")
            cust_df = (
                df_filtered.groupby(["customer_label", "customer_city"], as_index=False)
                .agg(
                    total_spend=("revenue", "sum"),
                    orders_count=("order_id", "nunique"),
                    items_bought=("quantity", "sum"),
                )
                .sort_values("total_spend", ascending=False)
                .head(10)
            )

            st.dataframe(
                cust_df.style.format({
                    "total_spend": "${:,.2f}",
                    "orders_count": "{:,}",
                    "items_bought": "{:,}",
                }),
                use_container_width=True,
            )

        with u2:
            st.subheader("ยอดขายตามปีที่ลูกค้าสมัครสมาชิก")
            if "signup_year" in df_filtered.columns:
                cohort_df = df_filtered[df_filtered["signup_year"] > 0].groupby("signup_year", as_index=False)["revenue"].sum()
                
                if not cohort_df.empty:
                    cohort_chart = alt.Chart(cohort_df).mark_bar(cornerRadiusEnd=6, color="#ec4899").encode(
                        x=alt.X("signup_year:O", title="ปีที่สมัครสมาชิก"),
                        y=alt.Y("revenue:Q", title="ยอดขายรวม ($)"),
                        tooltip=["signup_year", alt.Tooltip("revenue:Q", format="$,.2f")],
                    ).properties(height=300)
                    st.altair_chart(cohort_chart, use_container_width=True)
                else:
                    st.info("ไม่มีข้อมูลปีที่สมัครสมาชิกของลูกค้าในช่วงเวลานี้")

if __name__ == "__main__":
    main()