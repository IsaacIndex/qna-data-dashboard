from __future__ import annotations

import streamlit as st

from app.ingest.components.accessibility import apply_accessibility_baseline
from app.ingest.components.base_filters import summarize_filters
from app.models.source import Source
from app.services.source_service import SourcePage, SourceService


def format_source_row(source: Source) -> dict[str, object]:
    """Return a display-friendly mapping for unified source rows."""
    display_label = f"{source.label} ({source.dataset}, {source.type.value})"
    return {
        "uuid": source.uuid,
        "displayLabel": display_label,
        "status": source.status.value,
        "legacy": bool(getattr(source, "legacy", False)),
        "dataset": source.dataset,
        "type": source.type.value,
        "groups": list(source.groups),
        "lastUpdated": source.last_updated.isoformat() if source.last_updated else None,
        "metadata": source.metadata,
    }


def _load_page(
    service: SourceService,
    *,
    cursor: str | None,
    limit: int,
    dataset: str | None,
    status: str | None,
    source_type: str | None,
    group: str | None,
    sort: str,
) -> SourcePage:
    return service.list_sources(
        cursor=cursor,
        limit=limit,
        status_filter=status,
        type_filter=source_type,
        dataset=dataset,
        group=group,
        sort=sort,
    )


def render_unified_list(service: SourceService | None = None, *, page_limit: int = 20) -> None:
    service = service or SourceService()
    apply_accessibility_baseline()
    st.subheader("Unified source inventory", anchor="unified-source-inventory")
    st.caption("Keyboard: tab through filters, press Enter to open dropdowns, and use load more to append rows.")

    options = service.build_filter_options()
    dataset = st.selectbox(
        "Dataset",
        options=["All datasets"] + options["datasets"],
        index=0,
        help="Limit the unified list to a single dataset (default shows all datasets).",
    )
    source_type = st.selectbox(
        "Type",
        options=["All types"] + options["types"],
        index=0,
        help="Filter by ingest source type such as tmp files, sheet sources, or embeddings.",
    )
    status = st.selectbox(
        "Status",
        options=["All statuses"] + options["statuses"],
        index=0,
        help="Filter by canonical status; archived/error items stay visible for action.",
    )
    group = st.selectbox(
        "Group tag",
        options=["All groups"] + options["groups"],
        index=0,
        help="Filter by group tag; leave All groups to include everything.",
    )
    sort_by = st.selectbox(
        "Sort by",
        options=["label", "dataset", "status", "group", "last_updated"],
        index=0,
        help="Server-side sort used for pagination and infinite scroll batches.",
    )

    if "unified_sources" not in st.session_state:
        st.session_state["unified_sources"] = []
        st.session_state["unified_cursor"] = None

    if st.button("Refresh unified list", help="Reset filters, clear cursor, and reload the first page."):
        st.session_state["unified_sources"] = []
        st.session_state["unified_cursor"] = None

    dataset_filter = None if dataset == "All datasets" else dataset
    source_type_filter = None if source_type == "All types" else source_type
    status_filter = None if status == "All statuses" else status
    group_filter = None if group == "All groups" else group

    # initial load or subsequent fetches
    if not st.session_state["unified_sources"]:
        page = _load_page(
            service,
            cursor=None,
            limit=page_limit,
            dataset=dataset_filter,
            status=status_filter,
            source_type=source_type_filter,
            group=group_filter,
            sort=sort_by,
        )
        st.session_state["unified_sources"] = list(page.items)
        st.session_state["unified_cursor"] = page.next_cursor

    rows = [format_source_row(source) for source in st.session_state["unified_sources"]]
    st.caption(
        summarize_filters(
            dataset=dataset_filter,
            source_type=source_type_filter,
            status=status_filter,
            group=group_filter,
            search=None,
        )
    )
    st.caption(f"Showing {len(rows)} source(s)")
    st.dataframe(
        rows,
        hide_index=True,
        use_container_width=True,
        column_config={
            "displayLabel": st.column_config.TextColumn("Source", help="Human-readable label plus dataset/type."),
            "status": st.column_config.TextColumn("Status", width="small"),
            "dataset": st.column_config.TextColumn("Dataset", width="small"),
            "type": st.column_config.TextColumn("Type", width="small"),
            "legacy": st.column_config.CheckboxColumn("Legacy", disabled=True),
            "groups": st.column_config.ListColumn("Groups", width="medium"),
            "lastUpdated": st.column_config.DatetimeColumn("Last updated", format="YYYY-MM-DD HH:mm"),
        },
    )

    if st.session_state["unified_cursor"]:
        if st.button("Load more sources", help="Append the next server-side batch to the table."):
            next_page = _load_page(
                service,
                cursor=st.session_state["unified_cursor"],
                limit=page_limit,
                dataset=dataset_filter,
                status=status_filter,
                source_type=source_type_filter,
                group=group_filter,
                sort=sort_by,
            )
            st.session_state["unified_sources"].extend(next_page.items)
            st.session_state["unified_cursor"] = next_page.next_cursor
            st.experimental_rerun()
