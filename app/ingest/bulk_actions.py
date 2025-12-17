from __future__ import annotations

import streamlit as st

from app.ingest.components.accessibility import apply_accessibility_baseline
from app.models.source import Source, SourceStatus
from app.services.source_repository import SourceRepository
from app.services.source_service import SourceService


def format_bulk_row(source: Source) -> dict[str, object]:
    display_label = f"{source.label} ({source.dataset}, {source.type.value})"
    return {
        "uuid": source.uuid,
        "displayLabel": display_label,
        "status": source.status.value,
        "groups": list(source.groups),
    }


def render_bulk_actions(
    service: SourceService | None = None,
    repository: SourceRepository | None = None,
    *,
    page_limit: int = 50,
) -> None:
    apply_accessibility_baseline()
    service = service or SourceService()
    repository = repository or getattr(service, "repository", SourceRepository())

    st.subheader("Bulk actions (status and groups)")
    page = service.list_sources(limit=page_limit, sort="label")
    rows = [format_bulk_row(source) for source in page.items]
    if not rows:
        st.info("No sources available for bulk updates yet.")
        return

    labels = [row["displayLabel"] for row in rows]
    selected_labels = st.multiselect(
        "Select sources",
        options=labels,
        default=[],
        help=(
            "Tab to focus, press space to toggle selections; labels include "
            "dataset/type for clarity."
        ),
    )
    selected_rows = [row for row in rows if row["displayLabel"] in selected_labels]

    status_choice = st.selectbox(
        "New status",
        options=[""] + [status.value for status in SourceStatus],
        index=0,
        help=(
            "Apply a canonical status across selected sources; leave blank to "
            "keep current statuses."
        ),
    )
    groups_input = st.text_input(
        "Group tags (comma separated)",
        value="",
        help=(
            "Example: finance, reviewed, needs-mapping. Tags are deduplicated "
            "and trimmed automatically."
        ),
    )
    groups = [value.strip() for value in groups_input.split(",") if value.strip()]

    if st.button(
        "Apply bulk update",
        type="primary",
        help="Writes per-item results; successes and failures are reported.",
    ):
        if not selected_rows:
            st.warning("Choose at least one source to update.")
            return
        uuids = [row["uuid"] for row in selected_rows]
        try:
            results = repository.bulk_update(
                uuids, status=status_choice or None, groups=groups or None
            )
        except ValueError as error:
            st.error(str(error))
            return

        failures = [item for item in results if item.get("error")]
        successes = [item for item in results if item.get("error") is None]

        if successes:
            st.success(f"Updated {len(successes)} sources.")
        if failures:
            failed_ids = ", ".join(item["uuid"] for item in failures if item.get("uuid"))
            st.warning(f"{len(failures)} failed: {failed_ids}")
