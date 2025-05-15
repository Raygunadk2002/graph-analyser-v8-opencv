
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
import cv2
import tempfile
import os

st.set_page_config(layout="wide")
st.title("📐 Structural Movement Graph Analyser v8")

# Show logo
if os.path.exists("Moniteye+Logo+Correct+Blue.jpeg"):
    st.image("Moniteye+Logo+Correct+Blue.jpeg", width=200)

st.info("🧠 VERSION: v8 — Curve tracing + CSV multi-sensor graphing")

uploaded_file = st.file_uploader("Upload Excel or CSV file", type=["xls", "xlsx", "csv"])
uploaded_image = st.file_uploader("Or upload a graph image (screenshot/photo)", type=["png", "jpg", "jpeg"])

def safe_read_table(file):
    try:
        if file.name.endswith('.csv'):
            return pd.read_csv(file)
        elif file.name.endswith('.xlsx'):
            return pd.read_excel(file, engine='openpyxl')
        elif file.name.endswith('.xls'):
            import pyexcel
            tmp_path = "/tmp/upload.xls"
            with open(tmp_path, "wb") as f:
                f.write(file.read())
            sheet = pyexcel.get_sheet(file_name=tmp_path)
            return pd.DataFrame(sheet.to_array()[1:], columns=sheet.row[0])
    except Exception as e:
        st.error(f"Failed to load file: {e}")
    return None

def trace_curve_from_image(image):
    img = np.array(image.convert("L"))  # grayscale
    blurred = cv2.GaussianBlur(img, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)

    # Get nonzero edge coordinates
    y_coords, x_coords = np.nonzero(edges)

    if len(x_coords) == 0:
        st.warning("No curve detected.")
        return None

    # Normalize to synthetic time series
    df_trace = pd.DataFrame({
        "time": np.linspace(0, 1, len(x_coords)),
        "value": 1 - y_coords / img.shape[0]
    }).sort_values("time")

    return df_trace

if uploaded_image:
    st.subheader("🖼️ Curve Tracing from Image")
    image = Image.open(uploaded_image)
    st.image(image, caption="Uploaded Image", use_column_width=True)

    traced_data = trace_curve_from_image(image)

    if traced_data is not None:
        st.line_chart(traced_data.set_index("time"))
        st.success("Curve extracted and graphed.")
        st.dataframe(traced_data.head())

elif uploaded_file:
    df = safe_read_table(uploaded_file)
    if df is not None and not df.empty:
        df = df.loc[:, ~df.columns.duplicated()]
        df = df.dropna(how="all", axis=1)

        try:
            st.dataframe(df.head())
        except Exception as e:
            st.warning("Could not preview table.")
            st.text(f"Preview error: {e}")

        st.subheader("🧭 Map Columns")
        time_col = st.selectbox("Time column", df.columns)
        sensor_cols = st.multiselect("Sensor output columns", df.columns)

        try:
            df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
            df = df.dropna(subset=[time_col])
            df = df.sort_values(time_col)
            for col in sensor_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            fig, ax = plt.subplots()
            for col in sensor_cols:
                ax.plot(df[time_col], df[col], label=col)
            ax.set_title("Sensor Outputs Over Time")
            ax.legend()
            st.pyplot(fig)

        except Exception as e:
            st.error(f"Processing error: {e}")
