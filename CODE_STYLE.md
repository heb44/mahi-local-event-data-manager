# Project Consistency Standard

This document defines the baseline standard for all new and refactored code in this project.

## Goals
- Keep architecture clean, uniform, and predictable.
- Make code easy to review, extend, and refactor across all apps.
- Favor consistency over cleverness.

## Typing
- All new or refactored service and helper functions must include parameter and return type hints.
- Public functions should always declare a return type.
- Prefer modern built-in generics: `list`, `dict`, `tuple`, `set`.
- Do not mix old and new generic styles in the same module.
- Use `Any` only at genuinely dynamic boundaries, such as framework internals, third-party data structures without stable local contracts, or transitional compatibility points.
- Do not use `Any` for stable service inputs, outputs, or internal data contracts when a small alias, `TypedDict`, or concrete model type would be clear.
- If a value can be described with a short concrete union or a small named alias, prefer that over `Any`.
- Avoid decorative typing. Do not add complex typing machinery unless it materially improves clarity, safety, or reuse.
- In views and forms, add type hints when touching non-trivial functions or custom methods.
- Avoid partially typing adjacent functions in the same module; normalize the whole touched area.

## Imports
- Group imports in this order:
  1. Python standard library
  2. Django imports
  3. Third-party imports
  4. Local app imports
- Keep one blank line between groups.
- Within each group, sort imports consistently and keep formatting simple.
- Remove unused imports during refactors.

## Naming
- Use `snake_case` for functions, variables, and module-level helpers.
- Use `PascalCase` for classes.
- Name services by responsibility, not by implementation detail.
- Prefer explicit names like `CheckInWorkflowService` over generic names like `ManagerHelper`.
- Keep model, form, and service naming aligned with the domain term already used by the app.
- Avoid inconsistent variants of the same term in nearby code.

## Responses and View Patterns
- Views should focus on HTTP concerns: request parsing, form binding, auth, rendering, redirecting, and response creation.
- Forms should own validation and cleaned input handling.
- Services should own business rules, orchestration, and persistence-heavy workflows.
- HTML endpoints should use a consistent message + redirect/render flow.
- JSON endpoints should return predictable shapes, typically including `success` plus either data or errors.
- Avoid mixing transport logic and business logic in the same function when the logic is reusable.

## Error Handling
- Prefer targeted exceptions over broad `except Exception` where practical.
- If broad exception handling is temporarily necessary, keep it shallow and localized.
- Do not add logging-only complexity unless it materially improves the current refactor.

## Refactoring Rule
- Every new or refactored function or service must follow this standard.
- When touching an inconsistent module, normalize the touched section instead of adding another style variant.
