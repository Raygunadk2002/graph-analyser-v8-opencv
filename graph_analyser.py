
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from PIL import Image
import os

st.set_page_config(layout="wide")
st.title("📐 Structural Movement Graph Analyser v9+")

# Show logo
if os.path.exists("Moniteye+Logo+Correct+Blue.jpeg"):
    st.image("Moniteye+Logo+Correct+Blue.jpeg", width=200)

# Job metadata
st.subheader("📋 Job Information")
job_number = st.text_input("Job Number")
client = st.text_input("Client")
address = st.text_input("Address")
requested_by = st.text_input("Requested By")
postcode = st.text_input("Site Postcode (for rainfall/soil data)")

uploaded_file = st.file_uploader("Upload sensor data (.csv, .xls, .xlsx)", type=["csv", "xls", "xlsx"])

if uploaded_file:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    df = df.loc[:, ~df.columns.duplicated()].dropna(how="all")

    st.subheader("🧭 Select Columns")
    time_col = st.selectbox("Time Column", df.columns)
    sensor_cols = st.multiselect("Sensor Output Columns", df.columns.difference([time_col]))

    rainfall_sim = st.checkbox("Overlay Simulated Rainfall Data", value=True)
    soil_sim = st.checkbox("Overlay Simulated Soil Moisture Deficit", value=True)

    try:
        df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
        df = df.dropna(subset=[time_col])
        for col in sensor_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Simulate rainfall and soil data for plotting
        df["rainfall_mm"] = np.random.normal(2, 1, len(df)) if rainfall_sim else None
        df["soil_deficit"] = np.random.normal(10, 3, len(df)) if soil_sim else None

        st.subheader("📊 Interactive Graph")
        fig = go.Figure()

        for col in sensor_cols:
            fig.add_trace(go.Scatter(x=df[time_col], y=df[col], name=col, mode='lines'))

        if rainfall_sim:
            fig.add_trace(go.Bar(x=df[time_col], y=df["rainfall_mm"], name="Rainfall (mm)", yaxis="y2", opacity=0.3))

        if soil_sim:
            fig.add_trace(go.Scatter(x=df[time_col], y=df["soil_deficit"], name="Soil Moisture Deficit", yaxis="y3", mode='lines', line=dict(dash='dot')))

        fig.update_layout(
            title="Sensor Outputs with Environmental Data",
            xaxis_title="Time",
            yaxis=dict(title="Sensor Output"),
            yaxis2=dict(title="Rainfall (mm)", overlaying="y", side="right", showgrid=False),
            yaxis3=dict(title="Soil Moisture Deficit", overlaying="y", side="right", position=0.95, showgrid=False),
            height=600
        )

        st.plotly_chart(fig, use_container_width=True)

        st.subheader("🔍 Correlation Summary")
        for col in sensor_cols:
            if rainfall_sim:
                r_corr = df[col].corr(df["rainfall_mm"])
                st.write(f"{col} vs Rainfall: r = {r_corr:.2f}")
            if soil_sim:
                s_corr = df[col].corr(df["soil_deficit"])
                st.write(f"{col} vs Soil Moisture Deficit: r = {s_corr:.2f}")

    except Exception as e:
        st.error(f"Error: {e}")
