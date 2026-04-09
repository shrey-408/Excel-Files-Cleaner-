import os
from cleaner import clean_excel, read_file_safely, _normalize_columns


def process_folder(folder_path, config):
    results = []

    if not os.path.isdir(folder_path):
        return [{"error": f"Folder not found: {folder_path}"}]

    for file in os.listdir(folder_path):
        if not (file.endswith(".xlsx") or file.endswith(".csv")):
            continue

        full_path = os.path.join(folder_path, file)

        try:
            # Read once, normalise, then pass DataFrame (not path) to clean_excel
            # to avoid double-read issues
            df_raw = read_file_safely(full_path)
            df_raw = _normalize_columns(df_raw)

            df, report = clean_excel(df_raw, config)

            output_path = os.path.join(folder_path, f"cleaned_{file}")

            if file.endswith(".csv"):
                df.to_csv(output_path, index=False, encoding="utf-8")
            else:
                # Always specify engine= explicitly
                df.to_excel(output_path, index=False, engine="openpyxl")

            results.append({file: {"status": "ok", **report}})

        except Exception as e:
            results.append({file: {"status": "error", "message": str(e)}})

    return results
