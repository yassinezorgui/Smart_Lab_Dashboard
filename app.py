import streamlit as st
import psycopg2
import pandas as pd
import numpy as np
from dotenv import dotenv_values
from datetime import datetime, timedelta

# ==================== CONFIG ====================
st.set_page_config(
    page_title="Smart Lab Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional styling
st.markdown("""
    <style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .metric-value {
        font-size: 28px;
        font-weight: bold;
        margin: 10px 0;
    }
    .metric-label {
        font-size: 12px;
        opacity: 0.9;
    }
    .result-normal {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        padding: 12px;
        border-radius: 4px;
        margin: 8px 0;
    }
    .result-high {
        background-color: #f8d7da;
        border-left: 4px solid #dc3545;
        padding: 12px;
        border-radius: 4px;
        margin: 8px 0;
    }
    .result-low {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 12px;
        border-radius: 4px;
        margin: 8px 0;
    }
    </style>
""", unsafe_allow_html=True)

# ==================== DB CONNECTION ====================
@st.cache_resource
def get_connection():
    config = dotenv_values(".env")
    try:
        conn = psycopg2.connect(
            dbname=config.get("DB_NAME"),
            user=config.get("DB_USER"),
            password=config.get("DB_PASSWORD"),
            host=config.get("DB_HOST"),
            port=config.get("DB_PORT")
        )
        return conn
    except Exception as e:
        st.error(f"❌ Database connection failed: {e}")
        st.stop()

conn = get_connection()

# ==================== LOAD DATA ====================
@st.cache_data
def load_patients():
    try:
        query = 'SELECT "Code", "Nom", "Prenom" FROM "Patient" ORDER BY "Nom", "Prenom"'
        df = pd.read_sql(query, conn)
        return df
    except Exception as e:
        st.error(f"❌ Error loading patients: {e}")
        return pd.DataFrame()

patients = load_patients()

if patients.empty:
    st.error("No patients found in database.")
    st.stop()

patient_dict = {
    f"{row.Nom} {row.Prenom}": row.Code
    for _, row in patients.iterrows()
}

# ==================== HEADER ====================
col1, col2 = st.columns([0.7, 0.3])
with col1:
    st.title("Smart Lab Analytics")
    st.markdown("**Professional Medical Analysis Dashboard**")
with col2:
    st.markdown("")
    st.markdown(f"**Total Patients:** {len(patients)}")

st.markdown("---")

# ==================== SIDEBAR FILTERS ====================
with st.sidebar:
    st.header("Filters")

    selected_patient_name = st.selectbox(
        "Select Patient",
        list(patient_dict.keys()),
        index=0
    )

    selected_patient = patient_dict[selected_patient_name]

    # Date range with defaults
    start_date = datetime.now() - timedelta(days=365)
    end_date = datetime.now()

    date_range = st.date_input(
        "Select Period",
        value=(start_date.date(), end_date.date()),
        max_value=end_date.date()
    )

    st.markdown("---")
    st.caption("💡 Select a patient and adjust the date range to filter results")

# ==================== LOAD ANALYSIS DATA ====================
try:
    query_specialist = """
    SELECT
        d."DatePrelevement",
        a."Libelle",
        dad."Resultat",
        dad."ValeurUsuelle",
        dad."FlagResult"
    FROM "DossierAnalyse" d
    JOIN "DossierAnalyseDetail" dad ON d."NEnreg" = dad."NumDossier"
    JOIN "Analyse" a ON dad."NumAnalyse" = a."Num"
    WHERE d."CodePatient" = %s
    ORDER BY d."DatePrelevement" DESC
    """

    df_spec = pd.read_sql(query_specialist, conn, params=(selected_patient,))

    # Convert DatePrelevement to datetime
    df_spec["DatePrelevement"] = pd.to_datetime(df_spec["DatePrelevement"])

    # Apply date filtering
    if len(date_range) == 2:
        start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
        df_spec = df_spec[
            (df_spec["DatePrelevement"] >= start) &
            (df_spec["DatePrelevement"] <= end)
        ]

    # ==================== SUMMARY METRICS ====================
    if not df_spec.empty:
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "📊 Total Tests",
                len(df_spec),
                delta=f"{df_spec['Libelle'].nunique()} analyses"
            )

        with col2:
            normal_count = len(df_spec[df_spec["FlagResult"] == "N"])
            st.metric(
                "🟢 Normal",
                normal_count,
                delta=f"{round(100*normal_count/len(df_spec), 1)}%"
            )

        with col3:
            high_count = len(df_spec[df_spec["FlagResult"] == "H"])
            st.metric(
                "🔴 High",
                high_count,
                delta=f"{round(100*high_count/len(df_spec), 1)}%"
            )

        with col4:
            low_count = len(df_spec[df_spec["FlagResult"] == "L"])
            st.metric(
                "🟠 Low",
                low_count,
                delta=f"{round(100*low_count/len(df_spec), 1)}%"
            )

        st.markdown("---")

        # ==================== TABS ====================
        tab1, tab2, tab3 = st.tabs(["📈 Trends & Data", "📋 Detailed Report", "📑 Export"])

        # TAB 1: TRENDS
        with tab1:
            col_chart, col_filter = st.columns([3, 1])

            with col_chart:
                st.subheader("Results Over Time")
                df_spec_chart = df_spec.copy()
                pivot_data = df_spec_chart.pivot_table(
                    index="DatePrelevement",
                    columns="Libelle",
                    values="Resultat",
                    aggfunc='first'
                )

                if not pivot_data.empty:
                    st.line_chart(pivot_data, height=400)

            with col_filter:
                st.markdown("### 📊 Analysis Types")
                analysis_counts = df_spec['Libelle'].value_counts()
                for analysis, count in analysis_counts.items():
                    st.write(f"**{analysis}**: {count}")

            st.markdown("---")

            st.subheader("Raw Data")
            display_df = df_spec.copy()
            display_df["DatePrelevement"] = display_df["DatePrelevement"].dt.strftime("%Y-%m-%d")
            display_df = display_df[["DatePrelevement", "Libelle", "Resultat", "ValeurUsuelle", "FlagResult"]]
            display_df = display_df.rename(columns={
                "DatePrelevement": "Date",
                "Libelle": "Analysis",
                "Resultat": "Result",
                "ValeurUsuelle": "Normal Range",
                "FlagResult": "Status"
            })
            st.dataframe(display_df, use_container_width=True, hide_index=True)

        # TAB 2: DETAILED REPORT
        with tab2:
            st.subheader("📄 Detailed Patient Report")

            grouped = df_spec.groupby("Libelle")

            for analysis, group in grouped:
                # Count results by flag
                flags = group["FlagResult"].value_counts()

                with st.expander(f"**{analysis}** • {len(group)} tests", expanded=False):
                    # Mini metrics for this analysis
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        normal = len(group[group["FlagResult"] == "N"])
                        st.metric("Normal", normal, label_visibility="collapsed")
                    with col2:
                        high = len(group[group["FlagResult"] == "H"])
                        st.metric("High", high, label_visibility="collapsed")
                    with col3:
                        low = len(group[group["FlagResult"] == "L"])
                        st.metric("Low", low, label_visibility="collapsed")

                    st.markdown("---")

                    # Results
                    for _, row in group.iterrows():
                        date_str = row["DatePrelevement"].strftime("%Y-%m-%d")
                        result = row["Resultat"]
                        normal_range = row["ValeurUsuelle"]
                        flag = row["FlagResult"]

                        if flag == "H":
                            status_icon = "🔴"
                            status_text = "HIGH"
                            css_class = "result-high"
                        elif flag == "L":
                            status_icon = "🟠"
                            status_text = "LOW"
                            css_class = "result-low"
                        else:
                            status_icon = "🟢"
                            status_text = "NORMAL"
                            css_class = "result-normal"

                        st.markdown(f"""
                        <div class="{css_class}">
                            <b>{date_str}</b> • {status_icon} {status_text}<br/>
                            Result: <b>{result}</b> | Normal Range: {normal_range}
                        </div>
                        """, unsafe_allow_html=True)

        # TAB 3: EXPORT
        with tab3:
            st.subheader("📥 Export Data")

            # Prepare export data
            export_df = df_spec.copy()
            export_df["DatePrelevement"] = export_df["DatePrelevement"].dt.strftime("%Y-%m-%d")
            export_df = export_df.rename(columns={
                "DatePrelevement": "Date",
                "Libelle": "Analysis",
                "Resultat": "Result",
                "ValeurUsuelle": "Normal_Range",
                "FlagResult": "Status"
            })

            # CSV download
            csv = export_df.to_csv(index=False)
            st.download_button(
                label="📊 Download as CSV",
                data=csv,
                file_name=f"patient_analysis_{selected_patient}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )

            # Summary statistics
            st.markdown("### 📈 Summary Statistics")
            st.write(f"**Total Tests:** {len(export_df)}")
            st.write(f"**Unique Analyses:** {export_df['Analysis'].nunique()}")
            st.write(f"**Date Range:** {export_df['Date'].min()} to {export_df['Date'].max()}")
            st.write(f"**Normal Results:** {len(export_df[export_df['Status'] == 'N'])} ({round(100*len(export_df[export_df['Status'] == 'N'])/len(export_df), 1)}%)")
            st.write(f"**Abnormal Results:** {len(export_df[export_df['Status'].isin(['H', 'L'])])} ({round(100*len(export_df[export_df['Status'].isin(['H', 'L'])])/len(export_df), 1)}%)")

    else:
        st.warning("⚠️ No data available for this selection.")
        st.info("Try adjusting the date range or selecting a different patient.")

except Exception as e:
    st.error(f"❌ Error loading data: {e}")
    st.info("Debug: Check database connection and ensure all tables are properly populated")

# ==================== FOOTER ====================
st.markdown("---")
st.markdown("""
<div style='text-align: center; opacity: 0.6;'>
    <small>Yassine Zorgui • Smart Lab Insights • 2026</small>
</div>
""", unsafe_allow_html=True)
