from __future__ import annotations

import os
import sqlite3
import warnings
from pathlib import Path

from dotenv import load_dotenv
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from realestate_finder.models import BuyerPreferenceState, FeedbackEvent, json_safe_state
from realestate_finder.nodes import (
    feedback_receiver,
    listing_fetcher,
    matcher,
    preference_updater,
    presenter,
    ranker,
    state_loader,
    state_saver,
)
from realestate_finder.ui_helpers import checkpoint_tables_for_reset

load_dotenv()


def _load_streamlit_secrets() -> None:
    """Bridge st.secrets into os.environ so the rest of the module just reads env vars.

    Streamlit Cloud stores secrets in st.secrets; local dev uses .env via dotenv.
    This runs only when Streamlit is present and has secrets configured.
    """
    try:
        import streamlit as st  # type: ignore[import]
        secrets = dict(st.secrets)
        for key, value in secrets.items():
            if key not in os.environ:
                os.environ[key] = str(value)
    except Exception:
        pass


_load_streamlit_secrets()


def _setup_langsmith_tracing() -> bool:
    """Enable LangSmith observability when LANGSMITH_API_KEY is set in the environment.

    LangGraph and LangChain read the LANGCHAIN_* env vars for tracing.  We
    bridge the LANGSMITH_* names so the .env.example convention is consistent.
    Returns True when tracing was activated.
    """
    api_key = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")
    if not api_key:
        return False
    os.environ.setdefault("LANGCHAIN_TRACING_V2", os.getenv("LANGSMITH_TRACING_V2", "true"))
    os.environ.setdefault("LANGCHAIN_API_KEY", api_key)
    os.environ.setdefault(
        "LANGCHAIN_PROJECT",
        os.getenv("LANGSMITH_PROJECT", "realestate-finder"),
    )
    return True


LANGSMITH_ACTIVE: bool = _setup_langsmith_tracing()

# Reflects which checkpointer is actually in use after compile_graph() runs.
# "postgresql" when POSTGRES_CONNECTION_STRING / DATABASE_URL is set and reachable;
# "sqlite" otherwise (local development default).
CHECKPOINTER_TYPE: str = "sqlite"


def build_graph():
    builder = StateGraph(BuyerPreferenceState)
    builder.add_node("state_loader", state_loader)
    builder.add_node("listing_fetcher", listing_fetcher)
    builder.add_node("matcher", matcher)
    builder.add_node("Ranker", ranker)
    builder.add_node("presenter", presenter)
    builder.add_node("feedback_receiver", feedback_receiver)
    builder.add_node("preference_updater", preference_updater)
    builder.add_node("state_saver", state_saver)

    builder.set_entry_point("state_loader")
    builder.add_conditional_edges(
        "state_loader",
        _route_after_load,
        {
            "recommend": "listing_fetcher",
            "feedback": "feedback_receiver",
        },
    )
    builder.add_edge("listing_fetcher", "matcher")
    builder.add_edge("matcher", "Ranker")
    builder.add_edge("Ranker", "presenter")
    builder.add_edge("presenter", "state_saver")
    builder.add_edge("feedback_receiver", "preference_updater")
    builder.add_edge("preference_updater", "state_saver")
    builder.add_edge("state_saver", END)
    return builder


def _route_after_load(state: BuyerPreferenceState | dict) -> str:
    current = BuyerPreferenceState.model_validate(state)
    return current.graph_action


def checkpoint_path() -> Path:
    configured = os.getenv("REALESTATE_CHECKPOINT_DB", "data/checkpoints.sqlite")
    path = Path(configured)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _make_postgres_checkpointer(pg_url: str):
    """Create a PostgreSQL checkpointer via psycopg3 (psycopg[binary])."""
    try:
        import psycopg  # type: ignore[import]
        from langgraph.checkpoint.postgres import PostgresSaver  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "PostgreSQL checkpointer requires: "
            "pip install 'langgraph-checkpoint-postgres>=2.0.0' 'psycopg[binary]>=3.1.18'"
        ) from exc
    conn = psycopg.connect(pg_url, autocommit=True)
    checkpointer = PostgresSaver(conn)
    checkpointer.setup()
    return checkpointer


def compile_graph(db_path: str | Path | None = None):
    global CHECKPOINTER_TYPE
    pg_url = os.getenv("POSTGRES_CONNECTION_STRING") or os.getenv("DATABASE_URL")
    if pg_url:
        try:
            checkpointer = _make_postgres_checkpointer(pg_url)
            CHECKPOINTER_TYPE = "postgresql"
            return build_graph().compile(checkpointer=checkpointer)
        except Exception as exc:
            warnings.warn(
                f"PostgreSQL checkpointer unavailable ({exc}); falling back to SQLite.",
                stacklevel=2,
            )
    path = Path(db_path) if db_path else checkpoint_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, check_same_thread=False)
    checkpointer = SqliteSaver(connection)
    if hasattr(checkpointer, "setup"):
        checkpointer.setup()
    CHECKPOINTER_TYPE = "sqlite"
    return build_graph().compile(checkpointer=checkpointer)


def thread_config(buyer_id: str) -> dict:
    return {"configurable": {"thread_id": buyer_id}}


def load_checkpoint_state(graph, buyer_id: str) -> BuyerPreferenceState:
    snapshot = graph.get_state(thread_config(buyer_id))
    if snapshot and snapshot.values:
        return BuyerPreferenceState.model_validate(snapshot.values)
    return BuyerPreferenceState()


def run_recommendation_session(graph, buyer_id: str, state: BuyerPreferenceState | None = None) -> BuyerPreferenceState:
    current = state or load_checkpoint_state(graph, buyer_id)
    current.graph_action = "recommend"
    result = graph.invoke(json_safe_state(current), config=thread_config(buyer_id))
    return BuyerPreferenceState.model_validate(result)


def save_feedback(
    graph, buyer_id: str, feedback: list[FeedbackEvent]
) -> BuyerPreferenceState:
    current = load_checkpoint_state(graph, buyer_id)
    current.graph_action = "feedback"
    current.incoming_feedback = feedback
    result = graph.invoke(json_safe_state(current), config=thread_config(buyer_id))
    return BuyerPreferenceState.model_validate(result)


def update_buyer_state(graph, buyer_id: str, state: BuyerPreferenceState) -> BuyerPreferenceState:
    graph.update_state(thread_config(buyer_id), json_safe_state(state))
    return load_checkpoint_state(graph, buyer_id)


def reset_buyer_checkpoint(buyer_id: str, db_path: str | Path | None = None) -> None:
    if CHECKPOINTER_TYPE == "postgresql":
        pg_url = os.getenv("POSTGRES_CONNECTION_STRING") or os.getenv("DATABASE_URL")
        if pg_url:
            try:
                import psycopg  # type: ignore[import]
                with psycopg.connect(pg_url, autocommit=True) as conn:
                    for table in checkpoint_tables_for_reset():
                        conn.execute(f"DELETE FROM {table} WHERE thread_id = %s", (buyer_id,))
                return
            except Exception:
                pass

    path = Path(db_path) if db_path else checkpoint_path()
    if not path.exists():
        return
    with sqlite3.connect(path) as connection:
        existing_tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        for table in checkpoint_tables_for_reset():
            if table in existing_tables:
                connection.execute(f"DELETE FROM {table} WHERE thread_id = ?", (buyer_id,))
        connection.commit()

