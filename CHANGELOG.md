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
- Draft-cycle scheduling with non-destructive start-date and per-slot serving-time updates, resolved meal dates/times, and Meal Plan schedule editing for activation and advance-prep workflows.
- Derived real prep schedules that turn Recipe advance-prep definitions into chronological start/end tasks from placed Meal serving dates/times, including prep-group/instruction provenance and unresolved scheduling visibility without mutating planning or Inventory state.
- Explicit PREP, THAW, MARINATE, SOAK, and PROOF advance-prep task types with safe legacy migration, Recipe classification controls, typed Meal Plan prep schedules, and representative seeded task data.
- Optional local prep reminders with configurable offsets, derived reminder times/statuses, Recipe reminder controls, Meal Plan visibility, safe legacy defaults, and representative seeded enabled/disabled reminders.
- Persisted exact-lot Gather selections with deterministic allocation suggestions, multi-lot requirements, compatible-lot overrides, reservation/expiration/capacity validation, automatic placement cleanup, and read-only Inventory semantics.
- Location-grouped Gather pick lists with hierarchical location paths, repeated-lot quantity consolidation, source traceability, and explicit incomplete-requirement visibility without Inventory mutation.
- Combined ingredient prep and duplicate advance-prep tasks across compatible Recipe components within a placed Meal, with safe unit conversion, source traceability, and serving-sensitive recalculation.
- Ordered Recipe cooking steps and a read-only Meal Plan Cooking Mode with one-step-at-a-time navigation, component/source context, prep-group ingredient context, current planned serving quantities, and explicit no-step component visibility.
- Multiple persistent Cooking Mode timers with ordered Recipe step timer definitions, concurrent countdowns, pause/resume/reset/dismiss controls, per-PlannedMeal runtime isolation, and reload-safe absolute end-time tracking.
- Step-specific Cooking Mode equipment references and structured Fahrenheit/Celsius temperature cues, preserving Recipe equipment quantity/notes and component context without changing serving or timer behavior.
- Multi-component Cooking Mode coordination with explicit step dependencies, stage-based ready-work ordering, parallel-capable groups, cycle rejection, deterministic interleaving across Recipe components, and preserved timer/equipment/temperature context.
- Persistent Meal completion drafts with planned-versus-actual ingredient usage, last-minute Ingredient substitution, safe same-family unit validation, plan-staleness detection/refresh, and a Meal Plan reconciliation UI that does not mutate Inventory before finalization.
- Atomic Meal completion finalization with actual-Ingredient lot allocation, valid Gather-selection preference, deterministic fallback allocation, Decimal-safe cross-unit consumption, immutable CONSUME transactions, lot-level audit history, structured shortage rollback, finalized locking, and idempotent retry behavior.
- Post-finalization production reconciliation with actual servings produced/eaten, deterministic leftover quantities including zero-leftover completion, durable leftover Inventory lots, actual RecipeOutput scaling and review/override, `PRODUCTION` transaction provenance, immutable historical output snapshots, and idempotent production commit behavior.
- Produced-stock planning coverage with automatic release of finalized Meal ingredient reservations, exact leftover/RecipeOutput source provenance, future-slot reservations, Physical / Reserved / Available visibility, excess-stock availability, deterministic shortage warnings, reservation-safe produced Inventory edits, and release-on-removal history.
- Operational Dashboard foundation for current-cycle meals, today's prep work, and high-level Ingredient/produced-stock status.
- Dashboard use-soon recommendations for Ingredient, Leftover, and RecipeOutput lots expiring within seven days, ordered by urgency and filtered by reservation-aware Available quantity.
- Dashboard Plan alerts that reuse current-cycle validation and generated Shopping-list shortages, provide source-workflow links, deduplicate validation rows, and refresh automatically when underlying alert state changes.
- Dashboard Daily and Evening summaries that compose current Meals, prep work, plan alerts, Shopping shortages, and use-soon Inventory into concise next-action views, including remaining-today and tomorrow advance-prep context with automatic refresh.

### Known limitations
- The development database currently defaults to `./data`; packaged Windows persistence will be moved outside the installation directory.