import pandas as pd
from datasentinel.profiling import make_demo_data, profile_dataframe

EXPECTED_DEMO_TYPES = {"required_field_missing", "duplicate_event_delivery", "schema_drift",
                       "ingestion_delay", "api_error_spike"}


def _types(df):
    return {f["type"] for f in profile_dataframe(df, include_findings=True)}


def test_demo_data_contains_seeded_telemetry_issues():
    assert EXPECTED_DEMO_TYPES.issubset(_types(make_demo_data()))


def test_schema_drift_reports_affected_cohort():
    findings = profile_dataframe(make_demo_data(), include_findings=True)
    drift = next(f for f in findings if f["type"] == "schema_drift")
    assert "android 1.2" in drift["affected_cohorts"]  # regression test for the r.platform crash


def test_profile_has_one_row_per_column():
    df = make_demo_data()
    profile = profile_dataframe(df)
    assert "column" in profile.columns
    assert len(profile) == len(df.columns)


def test_generic_csv_checks_missing_duplicates_and_negatives():
    df = pd.DataFrame({
        "order_id": [1, 2, 2, 4],
        "revenue": [100, -5, -5, None],
    })
    types = _types(df)
    assert {"missing_values", "duplicates", "business_rule_violation"}.issubset(types)


def test_clean_generic_csv_has_no_findings():
    df = pd.DataFrame({"order_id": [1, 2, 3], "revenue": [10, 20, 30]})
    assert profile_dataframe(df, include_findings=True) == []
