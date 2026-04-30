from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from realestate_finder.models import BuyerPreferenceState
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
    builder.add_edge("state_loader", "listing_fetcher")
    builder.add_edge("listing_fetcher", "matcher")
    builder.add_edge("matcher", "Ranker")
    builder.add_edge("Ranker", "presenter")
    builder.add_edge("presenter", "feedback_receiver")
    builder.add_edge("feedback_receiver", "preference_updater")
    builder.add_edge("preference_updater", "state_saver")
    builder.add_edge("state_saver", END)
    return builder


def checkpoint_path() -> Path:
    configured = os.getenv("REALESTATE_CHECKPOINT_DB", "data/checkpoints.sqlite")
    path = Path(configured)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def compile_graph(db_path: str | Path | None = None):
    path = Path(db_path) if db_path else checkpoint_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, check_same_thread=False)
    checkpointer = SqliteSaver(connection)
    if hasattr(checkpointer, "setup"):
        checkpointer.setup()
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
    result = graph.invoke(current.model_dump(mode="python"), config=thread_config(buyer_id))
    return BuyerPreferenceState.model_validate(result)


def save_feedback(graph, buyer_id: str, feedback) -> BuyerPreferenceState:
    current = load_checkpoint_state(graph, buyer_id)
    current.graph_action = "feedback"
    current.incoming_feedback = feedback
    result = graph.invoke(current.model_dump(mode="python"), config=thread_config(buyer_id))
    return BuyerPreferenceState.model_validate(result)


def reset_buyer_checkpoint(buyer_id: str, db_path: str | Path | None = None) -> None:
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

