
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.title("✅ Graph Analyser v10 - Final Real Build")

uploaded_file = st.file_uploader("Upload a CSV or Excel file", type=["csv", "xls", "xlsx"])
if uploaded_file:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    st.success("File loaded.")
    time_col = st.selectbox("Time column", df.columns)
    sensor_cols = st.multiselect("Sensor columns", [col for col in df.columns if col != time_col])

    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    df = df.dropna(subset=[time_col])
    for col in sensor_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    fig = go.Figure()
    for col in sensor_cols:
        fig.add_trace(go.Scatter(x=df[time_col], y=df[col], name=col))
    st.plotly_chart(fig, use_container_width=True)
