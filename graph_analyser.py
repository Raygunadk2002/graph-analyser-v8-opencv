
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import os
from PIL import Image
from fpdf import FPDF

st.set_page_config(layout="wide")
st.title("📐 Structural Movement Graph Analyser v10 — FINAL")

# Moniteye logo
if os.path.exists("Moniteye+Logo+Correct+Blue.jpeg"):
    st.image("Moniteye+Logo+Correct+Blue.jpeg", width=200)

# Sidebar inputs
st.sidebar.subheader("📋 Job Info")
job_number = st.sidebar.text_input("Job Number")
client = st.sidebar.text_input("Client")
address = st.sidebar.text_input("Address")
requested_by = st.sidebar.text_input("Requested By")
postcode = st.sidebar.text_input("Postcode (for rainfall)", placeholder="e.g. SW1A 1AA")

uploaded_file = st.sidebar.file_uploader("Upload Data (.csv, .xls, .xlsx)", type=["csv", "xls", "xlsx"])
rain_toggle = st.sidebar.checkbox("Show Rainfall", value=True)

tabs = st.tabs(["📊 Graph View", "📈 Summary View", "🖨 Export Report"])

def get_latlon(postcode):
    try:
        r = requests.get(f"https://api.postcodes.io/postcodes/{postcode}")
        if r.status_code == 200:
            result = r.json()["result"]
            return result["latitude"], result["longitude"]
    except:
        return None, None
    return None, None

def get_rainfall(lat, lon):
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=precipitation_sum&timezone=Europe%2FLondon"
        r = requests.get(url)
        if r.status_code == 200:
            return pd.DataFrame(r.json()["daily"])
    except:
        return None
    return None

def classify_strength(value, thresholds=(0.3, 0.6)):
    if abs(value) < thresholds[0]: return "weak"
    elif abs(value) < thresholds[1]: return "moderate"
    else: return "strong"

def analyze_pattern(series):
    if len(series.dropna()) < 5:
        return "none", "insufficient data"
    slope = np.polyfit(range(len(series.dropna())), series.dropna(), 1)[0]
    trend_strength = classify_strength(slope / series.std())
    return "progressive", trend_strength

if uploaded_file:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    df = df.loc[:, ~df.columns.duplicated()].dropna(how="all")

    # Smart datetime detection
    dt_candidates = [col for col in df.columns if "date" in col.lower() or "time" in col.lower()]
    time_col = st.sidebar.selectbox("Time Column", dt_candidates or df.columns)
    sensor_cols = st.sidebar.multiselect("Sensor Columns", df.columns.difference([time_col]))

    try:
        df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
        df = df.dropna(subset=[time_col])
        for col in sensor_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        if postcode and rain_toggle:
            lat, lon = get_latlon(postcode)
            if lat and lon:
                rainfall_df = get_rainfall(lat, lon)
                if rainfall_df is not None:
                    rain_series = pd.Series(rainfall_df["precipitation_sum"].values, index=pd.to_datetime(rainfall_df["time"]))
                    df["rainfall_mm"] = np.interp(
                        pd.to_numeric(df[time_col]),
                        pd.to_numeric(rain_series.index),
                        rain_series.values
                    )

        with tabs[0]:
            st.subheader("📊 Sensor Data")
            fig = go.Figure()
            for col in sensor_cols:
                fig.add_trace(go.Scatter(x=df[time_col], y=df[col], name=col, mode='lines'))
            if rain_toggle and "rainfall_mm" in df.columns:
                fig.add_trace(go.Bar(x=df[time_col], y=df["rainfall_mm"], name="Rainfall", yaxis="y2", opacity=0.3))
            fig.update_layout(
                title="Sensor Plot",
                xaxis_title="Time",
                yaxis=dict(title="Sensor Output"),
                yaxis2=dict(title="Rainfall (mm)", overlaying="y", side="right", showgrid=False),
                height=600
            )
            st.plotly_chart(fig, use_container_width=True)

        with tabs[1]:
            st.subheader("📈 Summary Analysis")
            summary = []
            for col in sensor_cols:
                row = {"Sensor": col}
                pattern, strength = analyze_pattern(df[col])
                row["Movement Type"] = pattern
                row["Strength"] = strength
                if rain_toggle and "rainfall_mm" in df.columns:
                    r_corr = df[col].corr(df["rainfall_mm"])
                    row["Rainfall Corr"] = f"{r_corr:.2f} ({classify_strength(r_corr)})"
                summary.append(row)
            st.dataframe(pd.DataFrame(summary))

        with tabs[2]:
            st.subheader("🖨 Generate PDF Report")
            if st.button("Export PDF"):
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", size=12)
                if os.path.exists("Moniteye+Logo+Correct+Blue.jpeg"):
                    pdf.image("Moniteye+Logo+Correct+Blue.jpeg", x=10, y=8, w=50)
                    pdf.ln(30)
                pdf.cell(200, 10, txt="Structural Movement Summary", ln=True)
                pdf.cell(200, 10, txt=f"Job Number: {job_number}", ln=True)
                pdf.cell(200, 10, txt=f"Client: {client}", ln=True)
                pdf.cell(200, 10, txt=f"Address: {address}", ln=True)
                pdf.cell(200, 10, txt=f"Requested By: {requested_by}", ln=True)
                pdf.ln(10)
                pdf.cell(200, 10, txt="Trend Summary:", ln=True)
                for row in summary:
                    line = f"{row['Sensor']} - {row['Movement Type']} ({row['Strength']})"
                    if "Rainfall Corr" in row:
                        line += f" - Rainfall Corr: {row['Rainfall Corr']}"
                    pdf.cell(200, 10, txt=line, ln=True)
                out_path = "/tmp/moniteye_report.pdf"
                pdf.output(out_path)
                with open(out_path, "rb") as f:
                    st.download_button("Download PDF", data=f, file_name="moniteye_report.pdf")

    except Exception as e:
        st.error(f"❌ Error: {e}")
