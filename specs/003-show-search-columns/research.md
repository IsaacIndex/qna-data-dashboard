# Research Notes: Search Result Column Selections

- **Decision**: Persist column display preferences in a dedicated SQLite table linked to dataset identifiers.  
  **Rationale**: Keeps preferences durable across sessions, aligns with existing SQLAlchemy metadata layer, and supports per-dataset scoping required for multi-source searches.  
  **Alternatives considered**: (a) Store in Streamlit session state (lost on restart, no multi-user support); (b) Cache in local JSON files (harder to synchronize with ingestion updates and lacks transactional safety).

- **Decision**: Expose configuration through a Streamlit multiselect + ordering control that surfaces only columns available in the dataset’s catalog.  
  **Rationale**: Streamlit supports accessible multi-select widgets and reorderable lists, minimizing custom UI while allowing analysts to curate up to 10 fields per requirements.  
  **Alternatives considered**: (a) Build a custom React component (disproportionate effort + accessibility risk); (b) Rely on text input of column names (error-prone and unfriendly to analysts).

- **Decision**: Enrich search pipeline to attach supplemental column values at query time using bulk fetches from `QueryRecord` rows.  
  **Rationale**: Reuses existing metadata repository, ensures consistent data across UI/API, and lets Streamlit render the extra fields without duplicating storage.  
  **Alternatives considered**: (a) Precompute denormalized search documents (increases storage + refresh complexity); (b) Fetch per-row lazily in UI (adds latency and complicates caching).

- **Decision**: Handle missing or deprecated columns by recording preference validation during search execution and emitting user-facing notices plus log instrumentation.  
  **Rationale**: Prevents broken renders when ingestion updates schemas, keeps analysts informed, and supports observability requirements.  
  **Alternatives considered**: (a) Silently drop missing columns (confusing to users, harder to debug); (b) Block search until configuration is fixed (hurts analyst productivity).
