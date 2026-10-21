# DataSentinel 🛡️

**A local-first, three-agent AI data-quality investigation prototype using LangChain, LangGraph, and RAG.**

DataSentinel profiles uploaded CSV data, retrieves supporting documentation, asks a root-cause agent to form evidence-grounded hypotheses, and produces a repair/verification report. Repairs are not automatically applied to original data.

## Features
- CSV upload and dataset preview
- Deterministic quality checks: missing values, duplicate rows, negative values in business numeric fields
- Three specialized agent roles: Data Detective, Root-Cause Investigator, Repair & Verification
- LangGraph orchestration with shared state
- RAG knowledge base using Chroma and sentence-transformers embeddings
- Local SQLite incident history
- Streamlit dashboard and JSON report export
- Synthetic demo dataset with deliberately seeded defects

## Quick start (macOS)
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

Choose OpenAI in the sidebar and set `OPENAI_API_KEY` in `.env`, or choose Ollama and ensure the selected local model is installed. A first embedding-model run may download model files and take some time.

## How to demo
1. Open the app and select **Use demo dataset**.
2. Click **Run quality scan** to show deterministic findings.
3. Optionally upload TXT/MD/SQL documentation and click **Index uploaded documents**.
4. Configure an LLM provider and click **Investigate dataset**.
5. Inspect the agent outputs, retrieved evidence, verification status, and download the JSON report.

## Architecture
- `datasentinel/profiling.py`: deterministic profiling and seeded demo data.
- `datasentinel/rag.py`: local Chroma RAG indexing and retrieval.
- `datasentinel/agents.py`: three specialized agent functions and output models.
- `datasentinel/workflow.py`: LangGraph workflow.
- `datasentinel/storage.py`: SQLite incident history.
- `app.py`: Streamlit UI.

## Limitations
This is a student portfolio MVP, not a production data reliability platform. Root-cause findings depend on available documentation and LLM quality. SQLGlot is included for future lineage analysis; the current MVP does not yet provide a complete lineage graph or execute arbitrary SQL. Repair is intentionally proposal-only; checks do not modify original data. Passing verification means only that the listed implemented checks passed, not that every issue has been repaired.

## Tests
```bash
pytest -q
```

## Resume wording (use only after running and verifying the project)
Built DataSentinel, a three-agent data-quality investigation prototype using LangChain, LangGraph, and RAG to profile datasets, retrieve supporting documentation, investigate potential root causes, and report repair-verification results through a Streamlit dashboard.
