import streamlit as st
import pandas as pd
from cleaner import clean_excel, auto_detect_columns, _normalize_columns, read_file_safely
from config import DEFAULT_CONFIG
from logger import save_log
from batch_processor import process_folder
from io import BytesIO

st.title("Advanced Excel Automation Tool")

uploaded_file = st.file_uploader("Upload Excel/CSV File", type=["xlsx", "csv"])

output_format = st.selectbox("Select Output Format", ["CSV", "Excel"])

if uploaded_file:

    # ─────────────────────────────────────────────
    # STEP 1: READ FILE
    # BUG 5 FIX: app.py was calling clean_excel(uploaded_file, ...) twice
    # (once for preview, once on button click), plus reading df_raw a third time.
    # Streamlit UploadedFile is a stream — after one read the cursor is at EOF.
    # read_file_safely already calls seek(0), but the Excel path via pd.ExcelFile
    # does NOT, causing silent empty DataFrames on the second call.
    # Fix: read once into df_raw, pass that DataFrame everywhere.
    # ─────────────────────────────────────────────
    if uploaded_file.name.endswith(".xlsx"):
        xls = pd.ExcelFile(uploaded_file)
        sheet = st.selectbox("Select Sheet", xls.sheet_names)
        header_row = st.number_input(
            "Header Row (try 0,1,2 if wrong)", min_value=0, max_value=10, value=0
        )
        df_raw = pd.read_excel(xls, sheet_name=sheet, header=header_row)
    else:
        # BUG 1 FIX: use the flexible reader instead of hardcoding utf-8
        df_raw = read_file_safely(uploaded_file)

    # Normalise column names once here (matches what cleaner does internally)
    df_raw = _normalize_columns(df_raw)

    st.subheader("Raw Data Preview")
    st.dataframe(df_raw.head())
    st.write("Detected Columns:", df_raw.columns.tolist())

    # ─────────────────────────────────────────────
    # STEP 2: AUTO DETECT
    # ─────────────────────────────────────────────
    detected = auto_detect_columns(df_raw)

    st.subheader("Auto Detected Columns")
    st.json(detected)

    columns = df_raw.columns.tolist()

    # ─────────────────────────────────────────────
    # STEP 3: USER CONTROL PANEL
    # ─────────────────────────────────────────────
    st.sidebar.header("Rule Config Panel")

    date_cols = st.sidebar.multiselect("Date Columns", columns, default=detected["date_columns"])
    num_cols = st.sidebar.multiselect("Numeric Columns", columns, default=detected["numeric_columns"])
    email_cols = st.sidebar.multiselect("Email Columns", columns, default=detected["email_columns"])
    phone_cols = st.sidebar.multiselect("Phone Columns", columns, default=detected["phone_columns"])
    fill_method = st.sidebar.selectbox("Fill Missing (Numeric/Date only)", [None, "ffill", "bfill"])

    # ─────────────────────────────────────────────
    # STEP 4: BUILD CONFIG
    # ─────────────────────────────────────────────
    config = DEFAULT_CONFIG.copy()
    config["date_columns"] = date_cols
    config["numeric_columns"] = num_cols
    config["email_columns"] = email_cols
    config["phone_columns"] = phone_cols
    config["fill_method"] = fill_method

    # ─────────────────────────────────────────────
    # STEP 5: PREVIEW — operate on the already-loaded DataFrame, not the file stream
    # ─────────────────────────────────────────────
    df_preview, _ = clean_excel(df_raw, config)

    st.subheader("Preview (Cleaned)")
    st.dataframe(df_preview.head())

    # ─────────────────────────────────────────────
    # STEP 6: FINAL CLEAN
    # ─────────────────────────────────────────────
    if st.button("Clean File"):

        df_clean, report = clean_excel(df_raw, config)

        st.subheader("Cleaned Data")
        st.dataframe(df_clean.head())

        st.subheader("Report")
        st.json(report)

        save_log(report)

        if output_format == "CSV":
            file_data = df_clean.to_csv(index=False).encode("utf-8")
            file_name = "cleaned.csv"
            mime = "text/csv"
        else:
            buffer = BytesIO()
            df_clean.to_excel(buffer, index=False, engine="openpyxl")
            buffer.seek(0)
            file_data = buffer
            file_name = "cleaned.xlsx"
            mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        st.download_button(
            "Download Cleaned File",
            data=file_data,
            file_name=file_name,
            mime=mime,
        )

# ─────────────────────────────────────────────
# BATCH PROCESSING
# ─────────────────────────────────────────────
st.sidebar.header("Batch Processing")

folder_path = st.sidebar.text_input("Folder Path")

if st.sidebar.button("Run Batch Cleaning"):
    results = process_folder(folder_path, DEFAULT_CONFIG)
    st.write(results)
