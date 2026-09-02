# Changelog

All notable changes to Cycle Meal Planner will be documented here.

## 0.1.0-dev

### Added
- Initial repository bootstrap and product planning documentation.
- FastAPI backend foundation with SQLite, SQLAlchemy, Alembic, WAL mode, foreign-key enforcement, structured logging, and health checks.
- React + TypeScript + Vite frontend shell with routing, responsive navigation, TanStack Query, and backend connectivity status.
- Household defaults, measurement units, safe same-family unit conversion, shopping categories, and hierarchical inventory locations.
- Ingredient and alias management with duplicate/collision protection, reference defaults, search, archive behavior, and reusable tags.
- Recipe and structured RecipeIngredient models with servings, optional yield, meal types, tags, preparation metadata, required state, favorites, and archive behavior.
- Authoritative Decimal recipe scaling for LINEAR, FIXED, ROUND_UP, and MANUAL modes, including safe same-family unit overrides.
- Recipe CRUD/search/filter/scale APIs and backend test coverage.
- Recipe Library, structured Recipe Editor, recipe detail view, search/filter controls, favorites/tags/meal-type display, and serving-scale preview UI.
- Physical inventory lots with location, quantity/unit, purchase/open/expiration/frozen/thawed dates, immutable transaction history, add/remove/correction/transfer operations, browse filters, and Inventory management UI.
- Milestone 1 end-to-end validation covering fresh database initialization, reference data, ingredients/aliases, tagged recipes, scaling, inventory transactions, negative-quantity protection, application restart, and persistence.
- Reusable saved Meals composed of ordered Recipe components with serving multipliers/defaults, tags, meal types, favorites, archive behavior, CRUD/search API, and Meals library/editor/detail UI.
- Flexible draft Meal Cycles with arbitrary duration up to 365 days, configurable ordered slot definitions, generated per-day CycleSlots, optional start dates, CRUD API, and Meal Plan cycle editor/preview UI.
- Planned Meal placement with immutable source snapshots, manual assign/remove/move, lock/unlock controls, meal-type-aware random fill, and Meal Plan placement UI.
- Reproducible seeded manual-testing database with sample ingredients, recipes, Meals, Inventory, and a seven-day sample cycle.
- Planned serving targets, planned leftover servings, per-component serving overrides, deterministic scaled component/ingredient requirements, persistence, and Meal Plan quantity controls.
- Persistent inventory-aware Shopping Lists with safe same-family unit aggregation, current-inventory subtraction, category grouping, source traceability, deterministic regeneration, manual quantity adjustments, and Shopping UI.
- Shopping completion and purchase intake with actual purchased quantity/unit, storage and date metadata, skip state, exactly-once Inventory lot creation, PURCHASE transactions, persisted completion state, and Shopping intake controls.
- Cycle-level and slot-specific Meal population rules with include/exclude pools, persisted configuration, backward-compatible unrestricted cycles, and rule-aware random fill.
- Smart planning preferences with repeat spacing, favorite weighting, tag weighting, prior-planning history penalties, persisted configuration, and weighted random population layered on top of population rules.
- Expiration-aware Meal Plan analysis that matches dated Inventory lots to planned ingredient requirements, performs safe same-family conversion, ranks urgency, and suggests earlier same-slot move/swap opportunities without mutating the plan.
- Deterministic cycle validation with structured errors/warnings for empty slots, broken Meal/Recipe dependencies, MANUAL scaling review, Inventory shortages, incompatible unit families, expiration risks, and population-rule gaps, plus a Plan Validation UI.
- Recipe prep groups and structured ingredient prep fields for method, size/shape, and prep state, with editor assignment/reordering, grouped Recipe detail display, and scaling metadata preservation.
- Ordered Recipe advance-prep definitions with lead time, optional duration/instructions, optional prep-group links, editor management, and Recipe detail display for later scheduling workflows.
- Reusable household Equipment records plus ordered Recipe equipment requirements with quantity/notes, Settings management, Recipe editor/detail UI, archive-safe references, and unchanged serving scaling.
- Recipe ingredient substitutions with ordered alternates, conversion ratios, one preferred default, notes, nested Recipe editing, Recipe detail display, and per-use substitution selection in the serving-scale preview.
- Named Recipe variants with sparse ingredient quantity/unit/prep/substitution overrides, base-Recipe inheritance, variant-aware serving previews, archive/order support, and override preservation across base Recipe edits.
- Reusable Recipe outputs and explicit cross-Recipe dependencies with quantity/unit/scaling rules, cycle prevention, archive-safe references, and dependency serving previews.
- Ingredient-level future reservations generated from planned scaled requirements, stable reconcile/release behavior, and Physical / Reserved / Available / Shortage inventory visibility without changing physical lots.
- Centralized Physical / Reserved / Available inventory semantics shared by Inventory, Shopping, and cycle validation, with current-cycle reservation exclusion to prevent double counting and reservation-aware cross-cycle shortages.
- Expiration-aware lot allocation previews with deterministic expiration/opened/frozen/age/location priority, partial-lot splitting, reservation-aware capacity, cycle use dates, and Meal Plan lot recommendations without mutating Inventory.
- Partial Inventory lot splitting with inherited metadata, optional destination location, paired immutable provenance transactions, lot-level history inspection, and unchanged Physical / Reserved / Available totals.
- Ingredient staple minimum/target stock rules with compatible units, zero-stock low-status visibility, reservation-aware Available thresholds, and deterministic Shopping replenishment that combines meal demand with target stock without double-counting Inventory.

### Known limitations
- Exact-lot reservations, expiration-aware alerts, automated cooking reconciliation, and advanced recipe execution features are planned for later milestones.
- The development database currently defaults to `./data`; packaged Windows persistence will be moved outside the installation directory.
