from pathlib import Path
import pandas as pd

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "demo_app_telemetry.csv"
TELEMETRY_COLUMNS = {"event_id", "event_time", "ingested_at", "session_id", "event_name", "platform", "app_version"}

def make_demo_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Bundled demo dataset missing: {DATA_PATH}")
    return pd.read_csv(DATA_PATH)

def _finding(fid, kind, severity, column, count, evidence, **extra):
    item = {"id": fid, "type": kind, "severity": severity, "column": column, "count": int(count), "evidence": evidence}
    item.update(extra)
    return item

def detect_telemetry_findings(df: pd.DataFrame):
    findings = []
    if not TELEMETRY_COLUMNS.issubset(df.columns):
        return findings
    for col in ["event_id", "event_time", "user_id", "session_id", "event_name"]:
        if col in df and df[col].isna().any():
            count = int(df[col].isna().sum())
            findings.append(_finding(f"required_missing_{col}", "required_field_missing", "high", col, count,
                                     f"{count} telemetry records have no {col}; they may be untraceable."))
    duplicated_ids = int(df["event_id"].duplicated().sum())
    if duplicated_ids:
        findings.append(_finding("duplicate_event_ids", "duplicate_event_delivery", "medium", "event_id", duplicated_ids,
                                 f"{duplicated_ids} repeated event_id value(s) indicate possible retry/replay duplication."))
    if {"product_id", "productId"}.issubset(df.columns):
        wrong_case = df["product_id"].isna() & df["productId"].notna()
        count = int(wrong_case.sum())
        if count:
            cohorts = df.loc[wrong_case, ["platform", "app_version"]].drop_duplicates().astype(str)
            cohort_text = ", ".join(f"{r['platform']} {r['app_version']}" for r in cohorts.to_dict("records"))
            findings.append(_finding("event_schema_drift", "schema_drift", "high", "product_id", count,
                                     f"{count} rows populate productId instead of product_id. Affected cohorts: {cohort_text}.",
                                     affected_cohorts=cohort_text))
    event_ts = pd.to_datetime(df["event_time"], errors="coerce", utc=True)
    ingested_ts = pd.to_datetime(df["ingested_at"], errors="coerce", utc=True)
    temp = df[["platform", "app_version"]].copy()
    temp["_lag"] = (ingested_ts - event_ts).dt.total_seconds()
    for (platform, version), group in temp.groupby(["platform", "app_version"], dropna=False):
        valid = group["_lag"].dropna()
        if len(valid) >= 10:
            delayed = int((valid > 300).sum())
            rate = delayed / len(valid)
            if rate >= .20:
                findings.append(_finding(f"ingestion_lag_{platform}_{version}", "ingestion_delay", "high" if rate >= .4 else "medium",
                                         "ingested_at", delayed, f"{delayed}/{len(valid)} events ({rate:.0%}) for {platform} {version} arrived over 5 minutes late; median lag is {valid.median():.0f}s.",
                                         affected_cohort=f"{platform} {version}", delayed_rate=round(rate, 3)))
    if {"checkout_started", "purchase_completed"}.intersection(set(df["event_name"].astype(str))):
        sessions = df[["session_id", "platform", "app_version", "event_name"]].dropna(subset=["session_id"])
        started = sessions[sessions["event_name"] == "checkout_started"].groupby(["platform", "app_version"])["session_id"].apply(set)
        completed = sessions[sessions["event_name"] == "purchase_completed"].groupby(["platform", "app_version"])["session_id"].apply(set)
        for cohort, session_set in started.items():
            if len(session_set) < 8:
                continue
            completed_set = completed.get(cohort, set())
            rate = len(session_set.intersection(completed_set)) / len(session_set)
            if rate < .65:
                p, v = cohort
                findings.append(_finding(f"checkout_funnel_{p}_{v}", "funnel_regression", "critical", "event_name",
                                         len(session_set)-len(session_set.intersection(completed_set)),
                                         f"Only {rate:.0%} of {len(session_set)} {p} {v} sessions with checkout_started reached purchase_completed. Compare with other releases and inspect API errors before concluding the cause.",
                                         affected_cohort=f"{p} {v}", completion_rate=round(rate, 3)))
    if {"status_code", "endpoint"}.issubset(df.columns):
        api = df[df["endpoint"].astype(str).str.startswith("/api/", na=False)].copy()
        if not api.empty:
            api["_status"] = pd.to_numeric(api["status_code"], errors="coerce")
            api["_latency"] = pd.to_numeric(api["latency_ms"], errors="coerce")
            for (platform, version, endpoint), group in api.groupby(["platform", "app_version", "endpoint"], dropna=False):
                statuses = group["_status"].dropna()
                if len(statuses) >= 8:
                    errors = int((statuses >= 500).sum()); rate = errors / len(statuses)
                    if rate >= .20:
                        findings.append(_finding(f"api_5xx_{platform}_{version}", "api_error_spike", "critical" if rate >= .4 else "high",
                                                 "status_code", errors, f"{errors}/{len(statuses)} requests ({rate:.0%}) to {endpoint} returned 5xx for {platform} {version}.",
                                                 affected_cohort=f"{platform} {version}", endpoint=endpoint, error_rate=round(rate, 3)))
                    lat = group["_latency"].dropna()
                    if len(lat) >= 8 and float(lat.quantile(.95)) > 2000:
                        findings.append(_finding(f"api_latency_{platform}_{version}", "api_latency_spike", "high", "latency_ms", int((lat > 2000).sum()),
                                                 f"p95 latency for {endpoint} is {lat.quantile(.95):.0f}ms in {platform} {version}.",
                                                 affected_cohort=f"{platform} {version}", p95_latency_ms=round(float(lat.quantile(.95)), 1)))
    return findings

def profile_dataframe(df: pd.DataFrame, include_findings: bool = False):
    profile, findings = [], []
    is_telemetry = TELEMETRY_COLUMNS.issubset(df.columns)
    for col in df.columns:
        s = df[col]
        profile.append({"column": col, "dtype": str(s.dtype), "non_null": int(s.notna().sum()),
                        "missing": int(s.isna().sum()), "missing_pct": round(float(s.isna().mean()*100), 2),
                        "unique": int(s.nunique(dropna=True))})
        if s.isna().any() and (not is_telemetry or col in {"event_id","event_time","user_id","session_id","event_name"}):
            findings.append(_finding(f"missing_{col}", "missing_values", "medium", col, int(s.isna().sum()),
                                     f"{int(s.isna().sum())} missing value(s) in {col}."))
    if is_telemetry:
        findings.extend(detect_telemetry_findings(df))
    else:
        duplicates = int(df.duplicated().sum())
        if duplicates:
            findings.append(_finding("duplicate_rows", "duplicates", "medium", "*", duplicates, f"{duplicates} fully duplicated row(s)."))
        for col in df.select_dtypes(include="number").columns:
            count = int((df[col] < 0).sum())
            if count and any(word in col.lower() for word in ["revenue","price","amount","cost","quantity"]):
                findings.append(_finding(f"negative_{col}", "business_rule_violation", "high", col, count, f"{count} negative value(s) in {col}."))
    return findings if include_findings else pd.DataFrame(profile)
