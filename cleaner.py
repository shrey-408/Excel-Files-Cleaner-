import pandas as pd
import re
from utils import validate_email, clean_phone


# ─────────────────────────────────────────────
# BUG 1 FIX: Flexible encoding + filename-aware routing
# Old code tried utf-8 → latin-1 → excel blindly regardless of file type.
# If a CSV failed both encodings it silently fell into the Excel reader,
# which would either crash or return garbage.
# ─────────────────────────────────────────────
CSV_ENCODINGS = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]


def _get_name(file):
    """Works for both file paths (str) and Streamlit UploadedFile objects."""
    if isinstance(file, str):
        return file
    return getattr(file, "name", "")


def _seek(file):
    if not isinstance(file, str):
        file.seek(0)


def read_file_safely(file):
    name = _get_name(file).lower()

    # Route by extension first — never guess
    if name.endswith(".csv"):
        for enc in CSV_ENCODINGS:
            try:
                _seek(file)
                return pd.read_csv(file, encoding=enc)
            except (UnicodeDecodeError, pd.errors.ParserError):
                continue
        raise ValueError(
            f"Could not decode CSV with any of {CSV_ENCODINGS}. "
            "Try opening in Excel and re-saving as UTF-8 CSV."
        )

    if name.endswith((".xlsx", ".xls")):
        try:
            _seek(file)
            return pd.read_excel(file, engine="openpyxl")
        except Exception as e:
            raise ValueError(f"Could not read Excel file: {e}")

    # Unknown extension — try CSV first, then Excel
    for enc in CSV_ENCODINGS:
        try:
            _seek(file)
            return pd.read_csv(file, encoding=enc)
        except Exception:
            continue
    try:
        _seek(file)
        return pd.read_excel(file, engine="openpyxl")
    except Exception as e:
        raise ValueError(f"Unrecognised file type and all parsers failed: {e}")


# ─────────────────────────────────────────────
# BUG 2 FIX: Column name normalisation was incomplete
# Old regex only replaced spaces. Parentheses, slashes, dots, etc. stayed,
# which caused config column names to silently not match df columns.
# ─────────────────────────────────────────────
def _normalize_columns(df):
    new_cols = []
    for col in df.columns:
        col = str(col).strip().lower()
        col = re.sub(r"[^\w]+", "_", col)   # replace any non-word run with _
        col = col.strip("_")                 # remove leading/trailing _
        new_cols.append(col)
    df.columns = new_cols
    return df


# ─────────────────────────────────────────────
# Auto-detect (unchanged logic, extracted for reuse)
# ─────────────────────────────────────────────
def auto_detect_columns(df):
    detected = {
        "date_columns": [],
        "numeric_columns": [],
        "email_columns": [],
        "phone_columns": [],
    }

    for col in df.columns:
        sample = df[col].dropna()
        if sample.empty:
            continue

        sample = sample.astype(str).head(20)

        if sample.str.contains(r"@", regex=True).mean() > 0.6:
            detected["email_columns"].append(col)

        # BUG 3 FIX: Phone detector was matching numeric IDs (order IDs, zip codes).
        # Added extra guard: a real phone column name usually contains 'phone'/'tel'/'mobile'.
        # If the name doesn't hint at phone AND digits look like a plain integer, skip it.
        elif sample.str.replace(r"\D", "", regex=True).str.len().between(10, 15).mean() > 0.6:
            phone_hint = any(k in col for k in ("phone", "tel", "mobile", "cell", "fax"))
            looks_like_plain_int = pd.to_numeric(sample, errors="coerce").notnull().mean() > 0.9
            if phone_hint or not looks_like_plain_int:
                detected["phone_columns"].append(col)
            else:
                detected["numeric_columns"].append(col)

        elif pd.to_numeric(sample, errors="coerce").notnull().mean() > 0.7:
            detected["numeric_columns"].append(col)

        else:
            parsed = pd.to_datetime(sample, errors="coerce", dayfirst=True)
            if parsed.notnull().mean() > 0.7:
                detected["date_columns"].append(col)

    return detected


def clean_excel(file, config):
    df = read_file_safely(file)

    report = {}
    report["rows_before"] = df.shape[0]

    # Remove fully empty rows / columns
    df = df.dropna(how="all")
    df = df.dropna(axis=1, how="all")

    # BUG 2 FIX applied here
    df = _normalize_columns(df)

    if config.get("drop_duplicates", True):
        before = len(df)
        df = df.drop_duplicates()
        report["duplicates_removed"] = before - len(df)

    # Strip whitespace from string columns
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].str.strip()

    # Column-wise cleaning
    for col in df.columns:
        if col in config.get("date_columns", []):
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)

        if col in config.get("numeric_columns", []):
            df[col] = pd.to_numeric(df[col], errors="coerce")

        if col in config.get("email_columns", []):
            df[col] = df[col].apply(validate_email)

        if col in config.get("phone_columns", []):
            df[col] = df[col].apply(clean_phone)

    # ─────────────────────────────────────────
    # BUG 4 FIX: fillna(method=...) is deprecated in pandas >= 2.0
    # Use .ffill() / .bfill() directly instead.
    # ─────────────────────────────────────────
    fill_method = config.get("fill_method")
    if fill_method:
        target_cols = config.get("numeric_columns", []) + config.get("date_columns", [])
        for col in target_cols:
            if col not in df.columns:
                continue
            if fill_method == "ffill":
                df[col] = df[col].ffill()
            elif fill_method == "bfill":
                df[col] = df[col].bfill()

    report["rows_after"] = df.shape[0]
    report["nulls"] = int(df.isnull().sum().sum())

    return df, report
