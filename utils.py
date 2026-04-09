import re
import pandas as pd

def validate_email(email):
    if pd.isnull(email):
        return None
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return email if re.match(pattern, str(email)) else None

def clean_phone(phone):
    if pd.isnull(phone):
        return None
    phone = re.sub(r"\D", "", str(phone))
    return phone if len(phone) >= 10 else None