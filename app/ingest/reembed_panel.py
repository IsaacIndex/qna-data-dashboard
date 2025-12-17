from __future__ import annotations

from collections.abc import Sequence

import streamlit as st

from app.embeddings.service import ReembedService
from app.ingest.components.accessibility import apply_accessibility_baseline
from app.models.source import Source
from app.services.source_service import SourceService


def format_reembed_option(source: Source) -> dict[str, str]:
    display_label = f"{source.label} ({source.dataset}, {source.type.value})"
    return {
        "uuid": source.uuid,
        "displayLabel": display_label,
        "dataset": source.dataset,
        "type": source.type.value,
        "status": source.status.value,
    }


def build_reembed_options(sources: Sequence[Source]) -> list[dict[str, str]]:
    return [format_reembed_option(source) for source in sources]


def render_reembed_panel(
    source_service: SourceService | None = None,
    reembed_service: ReembedService | None = None,
    *,
    page_limit: int = 50,
) -> None:
    service = source_service or SourceService()
    jobs = reembed_service or ReembedService(repository=getattr(service, "repository", None))

    apply_accessibility_baseline()
    st.subheader("Re-embed sources with readable labels")
    page = service.list_sources(
        limit=page_limit, sort="label", status_overrides=jobs.status_overrides
    )
    options = build_reembed_options(page.items)

    if not options:
        st.info("No sources available for re-embedding yet.")
        return

    labels = [option["displayLabel"] for option in options]
    selected_label = st.selectbox(
        "Select a source",
        options=labels,
        index=0,
        help="Options list human-readable labels; press Enter to open and arrow keys to navigate.",
    )
    selected_uuid = next(
        (opt["uuid"] for opt in options if opt["displayLabel"] == selected_label), None
    )

    if selected_label:
        st.caption(
            "Options show dataset and type to disambiguate similar names. UUIDs stay hidden."
        )

    if selected_uuid and st.button(
        "Confirm re-embed", type="primary", help="Queue a re-embed job for the selected source."
    ):
        job = jobs.enqueue(selected_uuid)
        st.session_state["reembed_job_id"] = job.id
        st.success(f"Queued re-embed for {selected_label}")

    job_id = st.session_state.get("reembed_job_id")
    if job_id:
        job = jobs.get(job_id)
        if job:
            st.info(f"Job {job.id}: {job.status}")
            if job.status == "completed":
                st.success("Re-embed finished. Refreshing statuses.")
        refreshed = service.list_sources(
            limit=page_limit, sort="label", status_overrides=jobs.status_overrides
        )
        refreshed_map = {source.uuid: source.status.value for source in refreshed.items}
        if selected_uuid and selected_uuid in refreshed_map:
            st.caption(f"Current status for selected source: {refreshed_map[selected_uuid]}")
