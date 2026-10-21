import pandas as pd

def make_demo_data() -> pd.DataFrame:
    return pd.DataFrame({
        "order_id": [1001,1002,1003,1004,1005,1005,1007,1008,1009,1010],
        "region": ["Karnataka","Karnataka","Kerala","Tamil Nadu","Karnataka","Karnataka","Kerala","Karnataka",None,"Tamil Nadu"],
        "revenue": [5000,3000,4000,2500,2000,2000,-400,1200,800,None],
        "quantity": [2,1,2,1,1,1,1,1,1,1],
        "status": ["paid","paid","paid","paid","paid","paid","refunded","paid","paid","paid"]
    })

def profile_dataframe(df: pd.DataFrame, include_findings: bool = False):
    profile, findings = [], []
    for col in df.columns:
        s = df[col]
        profile.append({"column": col, "dtype": str(s.dtype), "non_null": int(s.notna().sum()),
                        "missing": int(s.isna().sum()), "missing_pct": round(float(s.isna().mean()*100), 2),
                        "unique": int(s.nunique(dropna=True))})
        if s.isna().any():
            findings.append({"id": f"missing_{col}", "type": "missing_values", "severity": "medium",
                             "column": col, "count": int(s.isna().sum()),
                             "evidence": f"{int(s.isna().sum())} missing value(s) in {col}."})
    duplicates = int(df.duplicated().sum())
    if duplicates:
        findings.append({"id": "duplicate_rows", "type": "duplicates", "severity": "medium",
                         "column": "*", "count": duplicates, "evidence": f"{duplicates} fully duplicated row(s)."})
    for col in df.select_dtypes(include="number").columns:
        count = int((df[col] < 0).sum())
        if count and any(word in col.lower() for word in ["revenue","price","amount","cost","quantity"]):
            findings.append({"id": f"negative_{col}", "type": "business_rule_violation", "severity": "high",
                             "column": col, "count": count, "evidence": f"{count} negative value(s) in {col}."})
    if "region" in df.columns and df["region"].isna().any():
        findings.append({"id": "missing_region", "type": "missing_dimension", "severity": "high",
                         "column": "region", "count": int(df["region"].isna().sum()),
                         "evidence": "Region is missing for one or more records."})
    return findings if include_findings else pd.DataFrame(profile)
