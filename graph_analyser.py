
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import os
from PIL import Image

st.set_page_config(layout="wide")
st.title("📐 Structural Movement Graph Analyser v9.2 Complete")

# Show Moniteye logo
if os.path.exists("Moniteye+Logo+Correct+Blue.jpeg"):
    st.image("Moniteye+Logo+Correct+Blue.jpeg", width=200)

# Job metadata and postcode
st.sidebar.subheader("📋 Job Info")
job_number = st.sidebar.text_input("Job Number")
client = st.sidebar.text_input("Client")
address = st.sidebar.text_input("Address")
requested_by = st.sidebar.text_input("Requested By")
postcode = st.sidebar.text_input("Postcode (for rainfall)")

uploaded_file = st.sidebar.file_uploader("Upload Sensor Data (.csv, .xls, .xlsx)", type=["csv", "xls", "xlsx"])
rain_toggle = st.sidebar.checkbox("Show Rainfall", value=True)

# Tabs
tabs = st.tabs(["📊 Graph View", "📈 Summary View"])

# Rainfall retrieval
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

# Load file
if uploaded_file:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
    df = df.loc[:, ~df.columns.duplicated()].dropna(how="all")

    time_col = st.sidebar.selectbox("Time Column", df.columns)
    sensor_cols = st.sidebar.multiselect("Sensor Columns", df.columns.difference([time_col]))

    try:
        df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
        df = df.dropna(subset=[time_col])
        for col in sensor_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Rainfall
        rainfall_df = None
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

        # --- Tab 1: Graph View ---
        with tabs[0]:
            st.subheader("📊 Interactive Plot")
            fig = go.Figure()
            for col in sensor_cols:
                fig.add_trace(go.Scatter(x=df[time_col], y=df[col], name=col, mode='lines'))
            if rain_toggle and "rainfall_mm" in df.columns:
                fig.add_trace(go.Bar(x=df[time_col], y=df["rainfall_mm"], name="Rainfall (mm)", yaxis="y2", opacity=0.3))
            fig.update_layout(
                title="Sensor Outputs and Rainfall",
                xaxis_title="Time",
                yaxis=dict(title="Sensor Output"),
                yaxis2=dict(title="Rainfall (mm)", overlaying="y", side="right", showgrid=False),
                height=600
            )
            st.plotly_chart(fig, use_container_width=True)

        # --- Tab 2: Summary View ---
        with tabs[1]:
            st.subheader("📈 Summary Analysis")

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

    except Exception as e:
        st.error(f"Processing error: {e}")
