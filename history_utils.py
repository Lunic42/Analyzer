"""
In-session history tracking. Lives entirely in st.session_state — resets when
the browser tab/session ends, same as everything else in this app (no DB).
"""
import streamlit as st
from datetime import datetime

MAX_ENTRIES = 50


def init_history():
    if "history" not in st.session_state:
        st.session_state["history"] = []


def add_history_entry(kind, input_preview, result_preview, extra=None):
    """
    kind: short tag, e.g. 'Summarize', 'Sentiment', 'Full Analysis', 'YouTube'
    input_preview / result_preview: real text from that run, will be trimmed for display
    extra: optional dict of structured data (e.g. sentiment scores) for charts
    """
    init_history()
    entry = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "kind": kind,
        "input_preview": (input_preview[:150] + "…") if len(input_preview) > 150 else input_preview,
        "result_preview": (result_preview[:300] + "…") if len(result_preview) > 300 else result_preview,
        "extra": extra or {},
    }
    st.session_state["history"].insert(0, entry)
    st.session_state["history"] = st.session_state["history"][:MAX_ENTRIES]


def get_history(kind=None):
    init_history()
    entries = st.session_state["history"]
    if kind:
        return [e for e in entries if e["kind"] == kind]
    return entries


def clear_history():
    st.session_state["history"] = []