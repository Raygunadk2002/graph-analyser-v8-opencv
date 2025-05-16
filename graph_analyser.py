
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
from fpdf import FPDF
import os
from PIL import Image

st.set_page_config(layout="wide")
st.title("📐 Structural Movement Graph Analyser v11 — Complete")

# Logo display
if os.path.exists("Moniteye+Logo+Correct+Blue.jpeg"):
    st.image("Moniteye+Logo+Correct+Blue.jpeg", width=200)

# Sidebar: Job metadata and settings
st.sidebar.subheader("📋 Job Information")
job_number = st.sidebar.text_input("Job Number")
client = st.sidebar.text_input("Client")
address = st.sidebar.text_input("Address")
requested_by = st.sidebar.text_input("Requested By")
postcode = st.sidebar.text_input("Site Postcode (for rainfall/SMD)", placeholder="e.g. SW1A 1AA")

# Data upload
uploaded_file = st.sidebar.file_uploader("Upload CSV or Excel", type=["csv","xls","xlsx"])
include_rain = st.sidebar.checkbox("Include Rainfall Data", value=True)
include_soil = st.sidebar.checkbox("Include Soil Moisture Deficit", value=True)

tabs = st.tabs(["📊 Graph View", "📈 Summary Dashboard", "🖨 PDF Report"])

# Helper functions
def get_latlon(postcode):
    try:
        r = requests.get(f"https://api.postcodes.io/postcodes/{postcode}")
        if r.ok:
            res = r.json()['result']
            return res['latitude'], res['longitude']
    except:
        pass
    return None, None

def get_rainfall(lat, lon):
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=precipitation_sum&timezone=Europe%2FLondon"
        r = requests.get(url)
        if r.ok:
            df = pd.DataFrame(r.json()['daily'])
            df['time'] = pd.to_datetime(df['time'])
            return df.set_index('time')['precipitation_sum']
    except:
        pass
    return None

def get_soil_moisture(lat, lon):
    # Stub: replace with COSMOS-UK API or data source
    # Returns pandas Series indexed by date
    return None

def smart_datetime(df):
    # auto-detect datetime columns
    for col in df.columns:
        try:
            parsed = pd.to_datetime(df[col], dayfirst=True, errors='coerce')
            if parsed.notna().sum() > len(df)*0.5:
                return col, parsed
        except:
            continue
    return None, None

def decompose_components(series, env_series=None):
    # Thermal component: regression vs env_series
    if env_series is not None:
        mask = ~series.isna() & ~env_series.isna()
        coeff = np.polyfit(env_series[mask], series[mask], 1)
        thermal = coeff[0]*env_series + coeff[1]
    else:
        thermal = pd.Series(0, index=series.index)
    # Seasonal: residual low-pass
    residual = series - thermal
    seasonal = residual.rolling(window=30, min_periods=1, center=True).mean()
    # Progressive: residual after subtracting seasonal and thermal
    progressive = series - thermal - (seasonal - residual.mean())
    return thermal, seasonal, progressive

def classify_strength(val):
    if abs(val)<0.3: return "weak"
    if abs(val)<0.6: return "moderate"
    return "strong"

# Main logic
if uploaded_file:
    # Load data
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file, engine='openpyxl')
    df = df.loc[:,~df.columns.duplicated()].dropna(how='all', axis=1)
    # datetime handling
    dt_col, parsed = smart_datetime(df)
    if dt_col:
        df['__time__'] = parsed
    else:
        dt_col = st.sidebar.selectbox("Time Column", df.columns)
        df['__time__'] = pd.to_datetime(df[dt_col], errors='coerce')
    df = df.dropna(subset=['__time__']).sort_values('__time__')
    # sensor selection
    sensor_cols = st.sidebar.multiselect("Sensor Columns", [c for c in df.columns if c!=dt_col])
    # numeric conversion
    for c in sensor_cols:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    # env data
    lat, lon = get_latlon(postcode)
    rain_series = get_rainfall(lat, lon) if include_rain and lat else None
    soil_series = get_soil_moisture(lat, lon) if include_soil and lat else None
    # align env to sensor timeframe
    if rain_series is not None:
        rain_series = rain_series.reindex(df['__time__'], method='nearest').fillna(0)
    if soil_series is not None:
        soil_series = soil_series.reindex(df['__time__'], method='nearest').fillna(0)
    # decomposition and plotting
    with tabs[0]:
        st.subheader("Composite Sensor Plot")
        fig = go.Figure()
        for c in sensor_cols:
            series = df[c]
            thermal, seasonal, prog = decompose_components(series, rain_series if include_rain else None)
            # user toggles per axis?
            fig.add_trace(go.Scatter(x=df['__time__'], y=series, name=f"{c} (orig)", line=dict(color='black')))
            fig.add_trace(go.Scatter(x=df['__time__'], y=thermal, name=f"{c} (thermal)", line=dict(color='orange')))
            fig.add_trace(go.Scatter(x=df['__time__'], y=seasonal, name=f"{c} (seasonal)", line=dict(color='blue')))
            fig.add_trace(go.Scatter(x=df['__time__'], y=prog, name=f"{c} (progressive)", line=dict(color='red')))
        if rain_series is not None:
            fig.add_trace(go.Bar(x=df['__time__'], y=rain_series, name='Rainfall (mm)', yaxis='y2', opacity=0.3))
        fig.update_layout(yaxis_title="Sensor", yaxis2=dict(overlaying='y', side='right', title='Rainfall'), height=600)
        st.plotly_chart(fig, use_container_width=True)
    # summary dashboard
    with tabs[1]:
        st.subheader("Summary Dashboard")
        cols = st.columns(len(sensor_cols))
        for i,c in enumerate(sensor_cols):
            series = df[c].dropna()
            trend, strength = analyze_trend(series)
            corr_rain = series.corr(rain_series) if rain_series is not None else None
            corr_soil = series.corr(soil_series) if soil_series is not None else None
            with cols[i]:
                st.metric(label=f"{c} trend", value=trend, delta=strength)
                if corr_rain is not None:
                    st.write(f"Rain corr: {corr_rain:.2f}")
                if corr_soil is not None:
                    st.write(f"Soil corr: {corr_soil:.2f}")
    # PDF export
    with tabs[2]:
        st.subheader("Export PDF Report")
        if st.button("Generate PDF"):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font('Arial', size=12)
            if os.path.exists(logo_path):
                pdf.image(logo_path, x=10, y=8, w=50)
                pdf.ln(30)
            pdf.cell(200,10,txt="Structural Movement Report",ln=1)
            pdf.cell(200,10,txt=f"Job Number: {job_number}",ln=1)
            pdf.cell(200,10,txt=f"Client: {client}",ln=1)
            pdf.cell(200,10,txt=f"Address: {address}",ln=1)
            pdf.cell(200,10,txt=f"Requested By: {requested_by}",ln=1)
            pdf.ln(5)
            for c in sensor_cols:
                series = df[c].dropna()
                trend, strength = analyze_trend(series)
                line = f"{c}: {trend} ({strength})"
                if rain_series is not None:
                    r = series.corr(rain_series)
                    line += f", rain corr {r:.2f}"
                if soil_series is not None:
                    s = series.corr(soil_series)
                    line += f", soil corr {s:.2f}"
                pdf.cell(200,10,txt=line,ln=1)
            # embed graph image
            img_data = None
            fig.write_image("temp_plot.png")
            pdf.image("temp_plot.png", x=10, y=pdf.get_y()+5, w=180)
            out_path = "/tmp/report_v11.pdf"
            pdf.output(out_path)
            with open(out_path,"rb") as f:
                st.download_button("Download PDF", f, file_name="report_v11.pdf")
