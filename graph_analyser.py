
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
st.title("📐 Structural Movement Graph Analyser — Latest")

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
postcode = st.sidebar.text_input("Postcode (for rainfall)", placeholder="e.g. SW1A 1AA")

# File uploader and options
uploaded = st.sidebar.file_uploader("Upload CSV/XLS/XLSX", type=["csv","xls","xlsx"])
include_rain = st.sidebar.checkbox("Include Rainfall Data", value=True)
include_soil = st.sidebar.checkbox("Include Soil Moisture Deficit", value=False)
components = st.sidebar.multiselect("Show Components", ["Original","Thermal","Seasonal","Progressive"], default=["Original","Thermal","Seasonal","Progressive"])

tabs = st.tabs(["📊 Graph View","📈 Summary","🖨 PDF Report"])

def safe_read_table(uploaded_file):
    uploaded_file.seek(0)
    name = uploaded_file.name.lower()
    try:
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
    except Exception as e:
        st.error(f"Could not parse {uploaded_file.name}: {e}")
    st.error("Unsupported or invalid file type.")
    return None

def get_latlon(postcode):
    try:
        r = requests.get(f"https://api.postcodes.io/postcodes/{postcode}")
        if r.ok:
            d = r.json().get('result',{})
            return d.get('latitude'), d.get('longitude')
    except:
        pass
    return None, None

def get_rainfall(lat, lon):
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=precipitation_sum&timezone=Europe%2FLondon"
        r = requests.get(url)
        if r.ok:
            df = pd.DataFrame(r.json().get('daily',{}))
            df['time'] = pd.to_datetime(df['time'])
            return df.set_index('time')['precipitation_sum']
    except:
        pass
    return None

def get_soil_moisture(lat, lon):
    # Placeholder for COSMOS-UK integration
    return None

def smart_datetime(df):
    for col in df.columns:
        try:
            parsed = pd.to_datetime(df[col], dayfirst=True, errors='coerce')
            if parsed.notna().sum() > len(df)*0.5:
                return col, parsed
        except:
            continue
    return None, None

def decompose(series, env=None):
    if env is not None:
        mask = series.notna() & env.notna()
        coeff = np.polyfit(env[mask], series[mask], 1)
        thermal = coeff[0]*env + coeff[1]
    else:
        thermal = pd.Series(0, index=series.index)
    residual = series - thermal
    seasonal = residual.rolling(window=30, min_periods=1, center=True).mean()
    progressive = series - thermal - (seasonal - residual.mean())
    return thermal, seasonal, progressive

def classify_strength(v):
    v = abs(v)
    if v < 0.3: return "weak"
    if v < 0.6: return "moderate"
    return "strong"

def analyze_trend(series):
    s = pd.Series(series).dropna().reset_index(drop=True)
    if len(s) < 5: return "none","insufficient"
    slope = np.polyfit(range(len(s)), s, 1)[0]
    return "progressive", classify_strength(slope/s.std())

if uploaded:
    df = safe_read_table(uploaded)
    if df is None or df.empty: st.stop()
    dt_col, parsed = smart_datetime(df)
    if dt_col:
        df['__time__'] = parsed
    else:
        dt_col = st.sidebar.selectbox("Select Time Column", df.columns)
        df['__time__'] = pd.to_datetime(df[dt_col], errors='coerce')
    df = df.dropna(subset=['__time__']).sort_values('__time__')
    sensor_cols = st.sidebar.multiselect("Select Sensor Columns", [c for c in df.columns if c!='__time__'])
    for c in sensor_cols:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    lat, lon = get_latlon(postcode)
    rain = get_rainfall(lat, lon) if include_rain and lat else None
    soil = get_soil_moisture(lat, lon) if include_soil and lat else None
    if rain is not None:
        rain = rain.reindex(df['__time__'], method='nearest').fillna(0)
    if soil is not None:
        soil = soil.reindex(df['__time__'], method='nearest').fillna(0)

    ### Graph View
    with tabs[0]:
        fig = go.Figure()
        for c in sensor_cols:
            orig = df[c]
            thermal, seasonal, prog = decompose(orig, rain if include_rain else None)
            if "Original" in components:
                fig.add_trace(go.Scatter(x=df['__time__'], y=orig, name=f"{c} orig"))
            if "Thermal" in components:
                fig.add_trace(go.Scatter(x=df['__time__'], y=thermal, name=f"{c} thermal"))
            if "Seasonal" in components:
                fig.add_trace(go.Scatter(x=df['__time__'], y=seasonal, name=f"{c} seasonal"))
            if "Progressive" in components:
                fig.add_trace(go.Scatter(x=df['__time__'], y=prog, name=f"{c} progressive"))
        if rain is not None:
            fig.add_trace(go.Bar(x=df['__time__'], y=rain, name='Rainfall', yaxis='y2', opacity=0.3))
        fig.update_layout(
            xaxis_title="Time", 
            yaxis_title="Sensor",
            yaxis2=dict(overlaying='y', side='right', title='Rainfall'),
            height=600)
        st.plotly_chart(fig, use_container_width=True)

    ### Summary
    with tabs[1]:
        cols = st.columns(len(sensor_cols) or 1)
        for i,c in enumerate(sensor_cols):
            trend, strength = analyze_trend(df[c])
            corr_r = df[c].corr(rain) if rain is not None else None
            corr_s = df[c].corr(soil) if soil is not None else None
            with cols[i]:
                st.metric(label=f"{c} trend", value=trend, delta=strength)
                if corr_r is not None:
                    st.write(f"Rain corr: {corr_r:.2f}")
                if corr_s is not None:
                    st.write(f"Soil corr: {corr_s:.2f}")

    ### PDF Report
    with tabs[2]:
        if st.button("Download PDF Report"):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
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
                trend, strength = analyze_trend(df[c])
                line = f"{c}: {trend} ({strength})"
                if rain is not None:
                    r = df[c].corr(rain)
                    line += f", rain corr {r:.2f}"
                if soil is not None:
                    s = df[c].corr(soil)
                    line += f", soil corr {s:.2f}"
                pdf.cell(200,10,txt=line,ln=1)
            fig.write_image("/tmp/plot.png")
            pdf.image("/tmp/plot.png", x=10, y=pdf.get_y()+5, w=180)
            out = "/tmp/report_v11.pdf"
            pdf.output(out)
            with open(out, "rb") as f:
                st.download_button("Download Report", f, file_name="report_v11.pdf")
