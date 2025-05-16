
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
st.title("📐 Structural Movement Graph Analyser v12")

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
    st.error("Unsupported file type.")
    return None

if uploaded:
    df = safe_read_table(uploaded)
    if df is None or df.empty:
        st.stop()
    # datetime parsing
    time_col = st.sidebar.selectbox("Time Column", df.columns)
    df['__time__'] = pd.to_datetime(df[time_col], errors='coerce')
    df = df.dropna(subset=['__time__']).sort_values('__time__')
    sensor_cols = st.sidebar.multiselect("Sensor Columns", [c for c in df.columns if c!=time_col])
    for c in sensor_cols:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    # rainfall data
    lat, lon = None, None
    if include_rain and postcode:
        try:
            r = requests.get(f"https://api.postcodes.io/postcodes/{postcode}")
            if r.ok:
                loc = r.json()['result']
                lat, lon = loc['latitude'], loc['longitude']
        except:
            pass
    rain_series = None
    if include_rain and lat:
        rf = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=precipitation_sum&timezone=Europe%2FLondon")
        if rf.ok:
            rdf = pd.DataFrame(rf.json()['daily'])
            rdf['time'] = pd.to_datetime(rdf['time'])
            rain_series = rdf.set_index('time')['precipitation_sum']
            rain_series = rain_series.reindex(df['__time__'], method='nearest').fillna(0)
    # Graph View
    with tabs[0]:
        st.subheader("Sensor Data Decomposition")
        fig = go.Figure()
        for c in sensor_cols:
            series = df[c].dropna()
            seasonal = series.rolling(window=30, min_periods=1, center=True).mean()
            progressive = series - seasonal
            if "Original" in components:
                fig.add_trace(go.Scatter(x=df['__time__'], y=series, name=f"{c} orig"))
            if "Thermal" in components:
                fig.add_trace(go.Scatter(x=df['__time__'], y=pd.Series(0,index=series.index), name=f"{c} thermal"))
            if "Seasonal" in components:
                fig.add_trace(go.Scatter(x=df['__time__'], y=seasonal, name=f"{c} seasonal"))
            if "Progressive" in components:
                fig.add_trace(go.Scatter(x=df['__time__'], y=progressive, name=f"{c} progressive"))
        if rain_series is not None:
            fig.add_trace(go.Bar(x=df['__time__'], y=rain_series, name='Rainfall', yaxis='y2', opacity=0.3))
        fig.update_layout(xaxis_title="Time", yaxis_title="Movement", yaxis2=dict(overlaying='y', side='right', title='Rainfall'), height=600)
        st.plotly_chart(fig, use_container_width=True)
    # Summary
    with tabs[1]:
        st.subheader("Summary Analysis")
        summary = []
        for c in sensor_cols:
            series = df[c]
            df['month'] = df['__time__'].dt.month
            summer = series[df['month'].isin([6,7,8])].mean()
            winter = series[df['month'].isin([12,1,2])].mean()
            if (summer - winter) > series.std():
                movement_type = "seasonal"
                strength = "strong"
                note = "Clay shrink/swell: summer opening, winter closing"
            elif series.iloc[-1] - series.iloc[0] > series.std():
                movement_type = "progressive"
                strength = "strong"
                note = "Consistent drift - possible drainage failure"
            else:
                movement_type = "none"
                strength = "weak"
                note = ""
            corr = ""
            if rain_series is not None:
                r = series.corr(rain_series)
                corr = f"Rain corr: {r:.2f}"
            summary.append({"Sensor": c, "Type": movement_type, "Strength": strength, "Note": note, "Correlation": corr})
        st.dataframe(pd.DataFrame(summary))
    # PDF Report
    with tabs[2]:
        if st.button("Export PDF"):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            if os.path.exists(logo_path):
                pdf.image(logo_path, x=10, y=8, w=50)
                pdf.ln(30)
            pdf.cell(200,10,txt="Structural Movement Report",ln=1)
            for row in summary:
                line = f"{row['Sensor']}: {row['Type']} ({row['Strength']})"
                if row['Note']:
                    line += f" - {row['Note']}"
                if row['Correlation']:
                    line += f" | {row['Correlation']}"

                pdf.cell(200,10,txt=line,ln=1)
            fig.write_image("/tmp/plot.png")
            pdf.image("/tmp/plot.png", x=10, y=pdf.get_y()+5, w=180)
            out = "/tmp/report_v12.pdf"
            pdf.output(out)
            with open(out,"rb") as f:
                st.download_button("Download PDF", f, file_name="report_v12.pdf")
