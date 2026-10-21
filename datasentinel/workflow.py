from typing import Any, Dict, TypedDict
import pandas as pd
from langgraph.graph import StateGraph, START, END
from .agents import data_detective, root_cause_investigator, repair_and_verify

class InvestigationState(TypedDict, total=False):
    df: Any
    dataset_name: str
    kb: Any
    provider: str
    model: str
    detective: Dict
    investigator: Dict
    repair_agent: Dict
    iteration: int
    trace: list

def run_investigation(df: pd.DataFrame, dataset_name: str, kb, provider: str, model: str) -> Dict:
    def detective_node(state):
        out = data_detective(state["df"], state["provider"], state["model"])
        return {"detective": out, "iteration": state.get("iteration", 0)+1,
                "trace": state.get("trace", []) + [{"agent": "Data Detective", "status": "completed",
                                                    "findings": len(out.get("findings", []))}]}
    def investigator_node(state):
        out = root_cause_investigator(state["df"], state["detective"], state["kb"], state["provider"], state["model"])
        return {"investigator": out, "trace": state.get("trace", []) + [{"agent": "Root-Cause Investigator",
                                                                          "status": "completed", "hypotheses": len(out.get("hypotheses", []))}]}
    def repair_node(state):
        out = repair_and_verify(state["df"], state["detective"], state["investigator"], state["provider"], state["model"])
        return {"repair_agent": out, "trace": state.get("trace", []) + [{"agent": "Repair & Verification",
                                                                          "status": out.get("status")}]}
    graph = StateGraph(InvestigationState)
    graph.add_node("detective", detective_node)
    graph.add_node("investigator", investigator_node)
    graph.add_node("repair", repair_node)
    graph.add_edge(START, "detective")
    graph.add_edge("detective", "investigator")
    graph.add_edge("investigator", "repair")
    graph.add_edge("repair", END)
    final = graph.compile().invoke({"df": df.copy(deep=True), "dataset_name": dataset_name, "kb": kb,
                                    "provider": provider, "model": model, "iteration": 0, "trace": []})
    detective, investigator, repair = final["detective"], final["investigator"], final["repair_agent"]
    return {"dataset_name": dataset_name,
            "summary": investigator.get("summary") or detective.get("explanation") or "Investigation completed.",
            "detective": detective, "findings": detective.get("findings", []),
            "investigator": investigator, "hypotheses": investigator.get("hypotheses", []),
            "retrieved_sources": investigator.get("retrieved_sources", []),
            "repair_agent": repair.get("plan", {}),
            "verification": {"passed": repair.get("passed", False), "status": repair.get("status"),
                             "checks": repair.get("checks", []), "note": repair.get("note"),
                             "original_data_modified": repair.get("original_data_modified", False)},
            "trace": final.get("trace", [])}
