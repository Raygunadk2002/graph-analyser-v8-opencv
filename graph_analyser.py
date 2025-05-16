
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
from fpdf import FPDF
import os
import pyexcel

st.set_page_config(layout="wide")
st.title("📐 Graph Analyser — Safe Loader Version")

# Logo
if os.path.exists("Moniteye+Logo+Correct+Blue.jpeg"):
    st.image("Moniteye+Logo+Correct+Blue.jpeg", width=200)

# Safe loader function
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
        else:
            st.error("Unsupported file type. Please upload .csv, .xls, or .xlsx")
    except Exception as e:
        st.error(f"Could not parse {uploaded_file.name!r}: {e}")
    return None

# Sidebar and uploader
uploaded_file = st.file_uploader("Upload CSV/XLS/XLSX", type=["csv","xls","xlsx"])
if uploaded_file:
    df = safe_read_table(uploaded_file)
    if df is None or df.empty:
        st.stop()

    st.success("File loaded.")
    time_col = st.selectbox("Time column", df.columns)
    sensor_cols = st.multiselect("Sensor columns", [col for col in df.columns if col != time_col])

    df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
    df = df.dropna(subset=[time_col])
    for col in sensor_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    fig = go.Figure()
    for col in sensor_cols:
        fig.add_trace(go.Scatter(x=df[time_col], y=df[col], name=col))
    st.plotly_chart(fig, use_container_width=True)
