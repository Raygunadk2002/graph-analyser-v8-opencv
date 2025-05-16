
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
from fpdf import FPDF
import os
import pyexcel
from PIL import Image

st.set_page_config(layout="wide")
st.title("📐 Structural Movement Graph Analyser v12 — Cumulative Rain Correlation")

# Display logo
logo_path = "Moniteye+Logo+Correct+Blue.jpeg"
if os.path.exists(logo_path):
    st.image(logo_path, width=200)

# Sidebar inputs
st.sidebar.header("📋 Job & Site Info")
job_number = st.sidebar.text_input("Job Number")
client = st.sidebar.text_input("Client")
address = st.sidebar.text_input("Address")
requested_by = st.sidebar.text_input("Requested By")
postcode = st.sidebar.text_input("Site Postcode", placeholder="SW1A 1AA")

uploaded = st.sidebar.file_uploader("Upload CSV/XLS/XLSX", type=["csv","xls","xlsx"])
include_rain = st.sidebar.checkbox("Include Rainfall", value=True)
components = st.sidebar.multiselect("Show Components", ["Original","Seasonal","Progressive"], default=["Original","Seasonal","Progressive"])

tabs = st.tabs(["📊 Graph View","📈 Summary","🖨 PDF Report"])

def safe_read_table(uploaded_file):
    uploaded_file.seek(0)
    name = uploaded_file.name.lower()
    if name.endswith('.csv'):
        return pd.read_csv(uploaded_file)
    elif name.endswith('.xlsx'):
        uploaded_file.seek(0)
        return pd.read_excel(uploaded_file, engine='openpyxl')
    elif name.endswith('.xls'):
        uploaded_file.seek(0)
        content = uploaded_file.read()
        tmp = "/tmp/temp.xls"
        with open(tmp, "wb") as f:
            f.write(content)
        sheet = pyexcel.get_sheet(file_name=tmp)
        return pd.DataFrame(sheet.to_array()[1:], columns=sheet.row[0])
    else:
        st.error("Unsupported file type.")
        return None

def get_latlon(postcode):
    try:
        r = requests.get(f"https://api.postcodes.io/postcodes/{postcode}")
        r.raise_for_status()
        res = r.json().get('result', {})
        return res.get('latitude'), res.get('longitude')
    except:
        return None, None

def get_historical_rainfall(lat, lon, start_date, end_date):
    url = (
        "https://archive-api.open-meteo.com/v1/era5?"
        f"latitude={lat}&longitude={lon}"
        f"&start_date={start_date}&end_date={end_date}"
        "&daily=precipitation_sum"
        "&timezone=Europe%2FLondon"
    )
    r = requests.get(url)
    if r.ok:
        df = pd.DataFrame(r.json().get('daily', {}))
        df['time'] = pd.to_datetime(df['time'])
        return df.set_index('time')['precipitation_sum']
    return None

if uploaded:
    df = safe_read_table(uploaded)
    if df is None or df.empty:
        st.stop()
    time_col = st.sidebar.selectbox("Time Column", df.columns)
    df['__time__'] = pd.to_datetime(df[time_col], errors='coerce')
    df = df.dropna(subset=['__time__']).sort_values('__time__')
    sensor_cols = st.sidebar.multiselect("Sensor Columns", [c for c in df.columns if c!=time_col])
    for c in sensor_cols:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    rain_series = None
    cum_rain = None
    if include_rain and postcode:
        lat, lon = get_latlon(postcode)
        if lat is not None:
            start = df['__time__'].dt.date.min().isoformat()
            end = df['__time__'].dt.date.max().isoformat()
            rain_series = get_historical_rainfall(lat, lon, start, end)
            if rain_series is not None:
                rain_series = rain_series.reindex(df['__time__'], method='nearest').fillna(0)
                cum_rain = rain_series.cumsum()
            else:
                st.warning("Historical rainfall data unavailable.")
    # Graph View
    with tabs[0]:
        st.subheader("Sensor Data with Seasonal/Progressive")
        fig = go.Figure()
        for c in sensor_cols:
            s = df[c].dropna()
            seasonal = s.rolling(window=30, min_periods=1, center=True).mean()
            progressive = s - seasonal
            fig.add_trace(go.Scatter(x=df['__time__'], y=s, name=f"{c} original"))
            if "Seasonal" in components:
                fig.add_trace(go.Scatter(x=df['__time__'], y=seasonal, name=f"{c} seasonal"))
            if "Progressive" in components:
                fig.add_trace(go.Scatter(x=df['__time__'], y=progressive, name=f"{c} progressive"))
        if rain_series is not None:
            fig.add_trace(go.Bar(x=df['__time__'], y=rain_series, name='Rainfall', yaxis='y2', opacity=0.3))
        fig.update_layout(xaxis_title="Time", yaxis_title="Movement",
                          yaxis2=dict(overlaying='y', side='right', title='Rainfall'),
                          height=600)
        st.plotly_chart(fig, use_container_width=True)
    # Summary
    with tabs[1]:
        st.subheader("Summary Analysis")
        summary = []
        for c in sensor_cols:
            s = df[c]
            # seasonal check
            df['month'] = df['__time__'].dt.month
            summer = s[df['month'].isin([6,7,8])].mean()
            winter = s[df['month'].isin([12,1,2])].mean()
            # cumulative rain correlation
            corr_cum = None
            if cum_rain is not None:
                corr_cum = s.corr(cum_rain)
            # determine type
            if corr_cum is not None and corr_cum < -0.3:
                movement_type = "seasonal"
                strength = "strong"
                note = "Cumulative rain correlates negatively—clay shrink/swell"
            elif s.iloc[-1] - s.iloc[0] > s.std():
                movement_type = "progressive"
                strength = "strong"
                note = "Consistent drift—possible drainage failure"
            else:
                movement_type = "none"
                strength = "weak"
                note = ""
            summary.append({
                "Sensor": c,
                "Type": movement_type,
                "Strength": strength,
                "Cumulative Rain Corr": f"{corr_cum:.2f}" if corr_cum is not None else ""
            })
        st.dataframe(pd.DataFrame(summary))
    # PDF Report
    with tabs[2]:
        if st.button("Export PDF"):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            if os.path.exists("Moniteye+Logo+Correct+Blue.jpeg"):
                pdf.image("Moniteye+Logo+Correct+Blue.jpeg", x=10, y=8, w=50)
                pdf.ln(30)
            pdf.cell(200,10,txt="Structural Movement Report",ln=1)
            for row in summary:
                line = f"{row['Sensor']}: {row['Type']} ({row['Strength']})"
                if row["Cumulative Rain Corr"]:
                    line += f" | Cum Rain Corr: {row['Cumulative Rain Corr']}"
                pdf.cell(200,10,txt=line,ln=1)
            fig.write_image("/tmp/plot.png")
            pdf.image("/tmp/plot.png", x=10, y=pdf.get_y()+5, w=180)
            out = "/tmp/report_v12.pdf"
            pdf.output(out)
            with open(out,"rb") as f:
                st.download_button("Download PDF", f, file_name="report_v12.pdf")
