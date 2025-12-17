from __future__ import annotations

import streamlit as st

_SESSION_FLAG = "_ingest_accessibility_styles_applied"

_STYLES = """
<style>
:root {
  --ingest-focus: #1f6feb;
  --ingest-focus-shadow: rgba(31, 111, 235, 0.25);
  --ingest-contrast-surface: #0b1220;
}
.stButton > button:focus-visible,
.stSelectbox [data-baseweb="select"] > div:focus-visible,
.stMultiSelect [data-baseweb="select"] > div:focus-visible,
.stTextInput input:focus-visible {
  outline: 2px solid var(--ingest-focus);
  outline-offset: 2px;
  box-shadow: 0 0 0 3px var(--ingest-focus-shadow);
}
.stButton > button.primary {
  background: linear-gradient(135deg, #123a82, #1f6feb);
  color: #f8fafc;
}
.stButton > button.primary:focus-visible {
  background: #0b285c;
}
.badge-legacy {
  background-color: #2d333b;
  color: #f8fafc;
  padding: 0.1rem 0.5rem;
  border-radius: 0.5rem;
  font-size: 0.8rem;
  font-weight: 600;
}
</style>
"""


def apply_accessibility_baseline() -> None:
    """One-time injection of focus outlines and higher-contrast buttons for ingest views."""
    if st.session_state.get(_SESSION_FLAG):
        return
    st.session_state[_SESSION_FLAG] = True
    st.markdown(_STYLES, unsafe_allow_html=True)
