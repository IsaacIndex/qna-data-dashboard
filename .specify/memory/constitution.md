<!-- Sync Impact Report
Version change: 2.0.0 -> 2.1.0
Modified principles:
- Evidence-Driven Testing (document temporary coverage deferrals with remediation plan)
Added sections: none
Removed sections: none
Templates requiring updates (✅ updated / ⚠ pending):
- ✅ .specify/templates/plan-template.md
- ✅ .specify/templates/spec-template.md
- ✅ .specify/templates/tasks-template.md
Follow-up TODOs: None
-->
# QnA Data Dashboard Constitution

## Core Principles

### Code Quality Rigor
- MUST enforce shared coding standards, linting, and type-checking baselines in CI with zero outstanding violations before merge approval.
- MUST document architectural decisions, module boundaries, and dependency impacts in plans/specs prior to implementation; divergence requires updated documentation.
- MUST consolidate reusable logic into shared packages or utilities and schedule refactors that remove duplication during each iteration planning cycle.
Rationale: Codified quality expectations keep the codebase maintainable, simplify reviews, and ensure contributors make changes that fit long-term architecture.

### Evidence-Driven Testing
- MUST define automated unit, integration, and data-validation tests prior to feature implementation and demonstrate failing tests during review of early commits.
- MUST maintain >=85% line coverage for core modules and 100% coverage for critical paths flagged in specs; any temporary drop demands a recorded waiver with remediation date.
- MUST track flaky or slow tests via CI telemetry and resolve regressions within the same iteration they are detected.
- MUST document any temporary deferral of new automated tests or benchmarks with rationale, risk assessment, and a committed remediation owner/date before implementation proceeds.
Rationale: Continuous, measurable testing protects behaviour, catches regressions early, and provides objective evidence that quality gates are satisfied.

### Unified User Experience
- MUST design UI changes using approved patterns, components, copy, and accessibility criteria captured in specs; exceptions require documented UX sign-off.
- MUST verify accessibility compliance (WCAG 2.1 AA) and interaction consistency via automated linting and manual QA notes attached to the feature checklist.
- MUST update user walkthroughs or quickstarts whenever navigation flows or primary interactions change.
Rationale: Consistent interfaces reduce user confusion, maintain accessibility standards, and make the dashboard predictable for stakeholders.

### Performance Accountability
- MUST define quantitative performance budgets (e.g., page render <=2s at P95, embedding refresh <=15m) in plans before development starts.
- MUST instrument code to capture agreed metrics, store benchmark scripts under `tests/performance/`, and run them in CI or scheduled jobs before release.
- MUST remediate any regression that breaches budgets prior to deploy; unresolved issues require a time-bound, documented mitigation plan.
Rationale: Explicit performance goals paired with measurement ensure the dashboard remains responsive and scalable as data and features grow.

## Technology Stack Constraints

- Languages & Frameworks: Declare chosen runtimes/frameworks per feature with justification for maintainability and performance; new stacks require governance approval.
- Quality Tooling: Maintain repository-standard formatters, linters, and type-checkers; introducing new tools mandates configuration updates and documentation in the plan.
- Experience Toolkit: Keep shared design assets (components, tokens, accessibility checklists) versioned alongside specs and reference them in implementation plans.
- Performance Instrumentation: Store repeatable benchmark/profiling scripts under `tests/performance/` and ensure CI publishes their results.
- Documentation: Update developer guides, quickstarts, and UX playbooks whenever tooling, patterns, or budgets change.

## Development Workflow & Quality Gates

- Discovery artifacts (plan/spec) must map each requirement to the principle it satisfies and include quality, UX, and performance acceptance criteria.
- Iterations follow: write failing tests/benchmarks, implement code, refactor with green suites, and record evidence in plans or checklists.
- Code reviews enforce principle alignment, verifying documentation updates, UX evidence, performance results, and test coverage before approval.
- Any temporary waivers for tests or performance checks must be logged with remediation owners and deadlines before merge approval.
- CI gates run linting, type checks, automated accessibility scans, unit/integration suites, and performance smoke tests; any failure blocks merge.
- Release readiness requires documented rollback plans, updated user guidance, and confirmation that performance dashboards show metrics within budget.

## Governance

- This constitution is the authoritative guide for the QnA Data Dashboard; conflicting practices are superseded.
- Amendments require justification tied to repository needs, an impact analysis referencing each core principle, and maintainer approval.
- Technical decisions (architectural changes, new tooling, third-party services) must document principle alignment and trade-offs in the plan/spec or an ADR.
- Versioning follows semantic rules: MAJOR for principle changes/removals, MINOR for new sections/principles, PATCH for clarifications.
- Compliance reviews occur at least once per quarter or before major releases, with findings logged in repository docs and remediation owners assigned.
- Deviations demand a documented risk assessment, mitigation plan, and explicit approval; temporary waivers expire after one release cycle and must be reviewed at the next compliance checkpoint.

**Version**: 2.1.0 | **Ratified**: 2025-10-20 | **Last Amended**: 2025-10-23
