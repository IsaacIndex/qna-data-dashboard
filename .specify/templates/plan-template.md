# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]
**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

[Extract from feature spec: primary requirement + technical approach from research]

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Runtime**: Declare supported runtimes and provide linting/typing tooling coverage.  
**Quality Tooling**: List formatters, linters, and static analyzers enforced in CI plus any new configurations.  
**Testing Strategy**: Outline unit, integration, data validation, and performance coverage commitments with measurement plans.  
**User Experience Framework**: Reference component library, accessibility tooling, and UX artifacts driving the experience.  
**Performance Budgets**: Capture render/response thresholds, data refresh expectations, and monitoring checkpoints.  
**Dependencies**: Identify critical packages/services with ownership and risk considerations.  
**Data & Storage**: Summarize data sources, schemas, retention, and compliance expectations.  
**Scale/Scope**: Estimate user concurrency, dataset growth, and operational load.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Map modules and dependencies to approved coding standards, architectural boundaries, and documentation updates.
- Provide test coverage targets, required suites (unit, integration, performance), and evidence of failure-first execution.
- Document UX patterns, accessibility approach, and consistency checks planned for this work.
- Define performance budgets, instrumentation strategy, and how results will be reported in CI/release notes.
- Identify any principle waivers, governance approvals, or decision records required before implementation, including time-bound remediation plans for any temporary test or benchmark deferrals.

## Project Structure

### Documentation (this feature)

```
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```
# [REMOVE IF UNUSED] Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# [REMOVE IF UNUSED] Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# [REMOVE IF UNUSED] Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure: feature modules, UI flows, platform tests]
```

**Structure Decision**: [Document the selected structure and reference the real
directories captured above]

## Complexity Tracking

*Fill ONLY if Constitution Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
