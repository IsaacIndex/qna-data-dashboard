from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

import pandas as pd
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.metadata import (  # noqa: E402
    MetadataRepository,
    build_engine,
    create_session_factory,
    init_database,
    session_scope,
)
from app.services.analytics import AnalyticsService  # noqa: E402
from app.utils.caching import cache_resource  # noqa: E402
from app.utils.logging import get_logger, log_event, log_timing  # noqa: E402

LOGGER = get_logger(__name__)


@cache_resource
def _get_session_factory():
    engine = build_engine()
    init_database(engine)
    return create_session_factory(engine)


def _dataset_options(repo: MetadataRepository) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for dataset in repo.list_data_files():
        entries.append(
            {
                "id": dataset.id,
                "label": f"{dataset.display_name} ({dataset.row_count} rows)",
            }
        )
    return entries


def _summary_metrics(service: AnalyticsService, dataset_ids: list[str]) -> dict[str, object]:
    summary = service.summarize_coverage(dataset_ids or None)
    metrics = {
        "summary": summary,
        "clusters": service.list_clusters(dataset_ids or None),
    }
    return metrics


def _clusters_dataframe(clusters) -> pd.DataFrame:
    if not clusters:
        return pd.DataFrame(columns=["Cluster", "Datasets", "Members", "Diversity", "Centroid Similarity"])
    rows = []
    for cluster in clusters:
        rows.append(
            {
                "Cluster": cluster.cluster_label,
                "Datasets": ", ".join(cluster.dataset_scope),
                "Members": cluster.member_count,
                "Diversity": f"{cluster.diversity_score:.2f}",
                "Centroid Similarity": f"{cluster.centroid_similarity:.2f}",
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    st.title("Coverage Analytics")
    st.caption("Visualize redundancy, cluster distribution, and diversity of ingested queries.")

    session_factory = _get_session_factory()
    with session_scope(session_factory) as session:
        repo = MetadataRepository(session)
        analytics_service = AnalyticsService(metadata_repository=repo)
        options = _dataset_options(repo)

        option_map = {item["label"]: item["id"] for item in options}
        selected_labels = st.multiselect(
            "Datasets",
            options=list(option_map.keys()),
        )
        selected_ids = [option_map[label] for label in selected_labels]

        if st.button("Refresh Analytics", type="primary"):
            try:
                with log_timing(LOGGER, "streamlit.analytics.refresh", dataset_count=len(selected_ids) or "all"):
                    analytics_service.build_clusters(selected_ids or None)
                st.success("Analytics refreshed.")
            except Exception as error:  # pragma: no cover - handled via UI
                LOGGER.exception("Analytics refresh failed: %s", error)
                st.error(f"Failed to refresh analytics: {error}")

        with log_timing(LOGGER, "streamlit.analytics.load", dataset_count=len(selected_ids) or "all"):
            metrics = _summary_metrics(analytics_service, selected_ids)
        summary = metrics["summary"]
        clusters = metrics["clusters"]
        log_event(
            LOGGER,
            "streamlit.analytics.loaded",
            dataset_count=len(summary.dataset_ids),
            cluster_count=len(clusters),
        )

    if summary.total_queries == 0:
        st.info("Analytics will appear once datasets with query records are available.")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Queries", summary.total_queries)
    col2.metric("Topic Estimates", summary.unique_topics_estimate)
    col3.metric("Redundancy Ratio", f"{summary.redundancy_ratio:.2f}")

    st.subheader("Cluster Overview")
    st.dataframe(_clusters_dataframe(clusters), use_container_width=True, hide_index=True)
    st.caption(f"Last refreshed: {summary.last_refreshed_at.isoformat()}")


if __name__ == "__main__":
    main()
