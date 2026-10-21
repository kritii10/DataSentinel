from datasentinel.profiling import make_demo_data, profile_dataframe

def test_demo_data_contains_expected_issues():
    findings = profile_dataframe(make_demo_data(), include_findings=True)
    types = {item["type"] for item in findings}
    assert "missing_values" in types
    assert "duplicates" in types
    assert "business_rule_violation" in types

def test_profile_has_columns():
    profile = profile_dataframe(make_demo_data())
    assert "column" in profile.columns
    assert len(profile) == 5
