# Accessibility Checklist: Local Query Coverage Analytics

**Reviewed**: 2025-10-21  
**Scope**: Streamlit ingestion, search, and analytics pages

## Keyboard & Focus Management

- [x] All form fields (upload, multiselects, sliders, buttons) are reachable via `Tab` order.
- [x] Search results table gains focus with `Shift+Tab` and supports arrow navigation.
- [x] Analytics dataframe respects Streamlit-provided focus outlines; no custom CSS overrides.

## Screen Reader & Semantics

- [x] Page titles and section headers use semantic elements (`st.title`, `st.subheader`) exposed to ARIA.
- [x] Buttons include descriptive labels (“Run Search”, “Refresh Analytics”) with no icon-only controls.
- [x] Status messaging uses `st.success`/`st.warning` ensuring polite live-region announcements.

## Color & Contrast

- [x] Verified default Streamlit theme meets WCAG AA for primary backgrounds/text.
- [x] Plotly/Streamlit tables use the high-contrast theme (no custom palettes applied).
- [x] Error states (red) and success states (green) include accompanying icons/text to avoid color-only cues.

## Motion & Feedback

- [x] No auto-playing animations; timers only log to console.
- [x] Search/analytics actions provide textual latency feedback and never rely solely on spinners.

## Outstanding Notes

- None. All pages satisfy current accessibility expectations; re-run checklist if custom components are introduced.
