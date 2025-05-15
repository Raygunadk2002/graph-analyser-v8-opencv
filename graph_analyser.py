
import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os

st.set_page_config(layout="wide")
st.title("📐 Structural Movement Graph Analyser v9.2 (Scaffolded)")

# Logo
if os.path.exists("Moniteye+Logo+Correct+Blue.jpeg"):
    st.image("Moniteye+Logo+Correct+Blue.jpeg", width=200)

# Metadata
postcode = st.text_input("Site Postcode (for Rainfall/SMD)", placeholder="e.g. SW1A 1AA")

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

# Postcode → lat/lon → rainfall
if postcode:
    lat, lon = get_latlon(postcode)
    if lat and lon:
        st.success(f"Lat: {lat:.4f}, Lon: {lon:.4f}")
        rain_df = get_rainfall(lat, lon)
        if rain_df is not None:
            st.write("Rainfall (Open-Meteo):")
            st.dataframe(rain_df)
        else:
            st.warning("Rainfall data not available for this location.")
    else:
        st.error("Invalid postcode or location not found.")
