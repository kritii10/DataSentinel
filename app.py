import json
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from datasentinel.profiling import profile_dataframe, make_demo_data
from datasentinel.rag import KnowledgeBase
from datasentinel.workflow import run_investigation
from datasentinel.storage import init_db, save_incident, list_incidents

load_dotenv()
st.set_page_config(page_title="DataSentinel", page_icon="🛡️", layout="wide")
init_db()
st.title("🛡️ DataSentinel")
st.caption("Multi-agent data quality investigation · LangChain · LangGraph · RAG")

with st.sidebar:
    st.header("Workspace")
    source = st.radio("Dataset source", ["Use demo dataset", "Upload CSV"])
    uploaded = st.file_uploader("Upload CSV", type=["csv"]) if source == "Upload CSV" else None
    st.divider()
    st.subheader("LLM configuration")
    provider = st.selectbox("Provider", ["OpenAI", "Ollama"])
    model = st.text_input("Model", value="gpt-4o-mini" if provider == "OpenAI" else "llama3.1")
    st.caption("OpenAI requires OPENAI_API_KEY in .env. Ollama requires a running local model.")
    st.divider()
    st.subheader("RAG knowledge base")
    kb_files = st.file_uploader("Add TXT, Markdown, or SQL documentation", type=["txt", "md", "sql"], accept_multiple_files=True)
    index_docs = st.button("Index uploaded documents", use_container_width=True)

if source == "Upload CSV":
    if uploaded is None:
        st.info("Upload a CSV or select the demo dataset.")
        st.stop()
    try:
        df = pd.read_csv(uploaded)
        dataset_name = uploaded.name
    except Exception as exc:
        st.error(f"Could not read CSV: {exc}")
        st.stop()
else:
    df, dataset_name = make_demo_data(), "demo_sales.csv"

if "kb" not in st.session_state:
    st.session_state.kb = KnowledgeBase()
if index_docs:
    if not kb_files:
        st.warning("Choose documentation files first.")
    else:
        try:
            docs = [{"name": f.name, "text": f.getvalue().decode("utf-8", errors="replace")} for f in kb_files]
            with st.spinner("Indexing documentation..."):
                count = st.session_state.kb.add_documents(docs)
            st.success(f"Indexed {count} document chunks.")
        except Exception as exc:
            st.error(f"Indexing failed: {exc}")

st.subheader(f"Dataset: {dataset_name}")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Rows", f"{len(df):,}")
m2.metric("Columns", len(df.columns))
m3.metric("Missing cells", int(df.isna().sum().sum()))
m4.metric("Duplicate rows", int(df.duplicated().sum()))
with st.expander("Preview dataset"):
    st.dataframe(df.head(100), use_container_width=True)
with st.expander("Column profile"):
    st.dataframe(profile_dataframe(df), use_container_width=True)

quality_tab, agent_tab, history_tab = st.tabs(["🔎 Quality scan", "🤖 Agent investigation", "🗂️ Incident history"])
with quality_tab:
    if st.button("Run quality scan", type="primary"):
        st.session_state.findings = profile_dataframe(df, include_findings=True)
    if "findings" in st.session_state:
        findings = st.session_state.findings
        if findings:
            st.dataframe(pd.DataFrame(findings), use_container_width=True)
        else:
            st.success("No configured data-quality issues detected.")
with agent_tab:
    st.write("Data Detective → Root-Cause Investigator → Repair & Verification")
    st.caption("Repairs are proposals only; the original dataset is never overwritten.")
    if st.button("Investigate dataset", type="primary"):
        with st.spinner("Running the three-agent workflow..."):
            try:
                result = run_investigation(df, dataset_name, st.session_state.kb, provider, model)
                st.session_state.last_result = result
                save_incident(dataset_name, result)
            except Exception as exc:
                st.error(f"Investigation could not complete: {exc}")
                st.info("Check provider configuration and the README troubleshooting notes.")
    if "last_result" in st.session_state:
        result = st.session_state.last_result
        st.info(result.get("summary", "Investigation completed."))
        c1, c2, c3 = st.columns(3)
        c1.metric("Findings", len(result.get("findings", [])))
        c2.metric("Hypotheses", len(result.get("hypotheses", [])))
        c3.metric("Verification", "Passed" if result.get("verification", {}).get("passed") else "Not verified")
        with st.expander("Agent 1 · Data Detective", expanded=True):
            st.json(result.get("detective", {}))
        with st.expander("Agent 2 · Root-Cause Investigator", expanded=True):
            st.json(result.get("investigator", {}))
            sources = result.get("retrieved_sources", [])
            if sources:
                st.write("Retrieved RAG evidence")
                st.dataframe(pd.DataFrame(sources), use_container_width=True)
        with st.expander("Agent 3 · Repair & Verification", expanded=True):
            st.json(result.get("repair_agent", {}))
            st.json(result.get("verification", {}))
        with st.expander("Full report"):
            st.json(result)
        st.download_button("Download report JSON", json.dumps(result, indent=2, default=str),
                           file_name="datasentinel_report.json", mime="application/json")
with history_tab:
    incidents = list_incidents()
    if incidents:
        st.dataframe(pd.DataFrame(incidents), use_container_width=True)
    else:
        st.caption("No incidents saved yet.")
st.caption("Prototype: root-cause hypotheses depend on evidence available. Verification is limited to implemented checks.")
