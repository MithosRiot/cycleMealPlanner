# Roadmap

## Milestone 1 — Foundation + Recipe Library
Goal: usable Recipe CRUD and basic Inventory foundation.

- Project bootstrap and repository structure.
- FastAPI backend skeleton and health endpoint.
- SQLite + SQLAlchemy + Alembic foundation.
- React + TypeScript frontend shell.
- Household/default servings.
- Measurement units and conversion engine.
- Shopping categories.
- Hierarchical inventory locations.
- Ingredient and alias management.
- Tags.
- Recipes and recipe ingredients.
- Recipe scaling engine.
- Recipe library/editor/detail UI.
- Inventory lots and transaction foundation.
- Inventory UI by ingredient and location.
- End-to-end persistence tests.

Completion criteria: a user can launch the app, manage locations and ingredients, create/tag/scale recipes, enter inventory, restart the app, and retain all data.

## v0.1 — Core Meal Planning MVP
- Recipes and saved Meals.
- Flexible meal cycles.
- Manual/basic random placement.
- Planned servings and basic leftovers.
- Inventory-aware shopping-list generation.
- Actual purchase intake into inventory.

## v0.2 — Smart Planning
- Cycle selection pools and population rules.
- Repeat spacing, tags, favorites and history preferences.
- Expiration-aware planning and meal reordering suggestions.
- Cycle validation and dependency warnings.

## v0.3 — Advanced Recipes
- Prep groups and structured ingredient prep.
- Advance prep definitions.
- Equipment.
- Preferred/per-use substitutions.
- Recipe variants.
- Recipe outputs and dependencies.

## v0.4 — Reservations + Advanced Inventory
- Ingredient reservations.
- Physical/reserved/available inventory.
- Expiration-aware allocation.
- Lot splitting/transfers and transaction history.
- Staple minimum/target rules.

## v0.5 — Activation + Advance Prep
- Cycle start dates and serving times.
- Real prep schedules.
- Thaw/marinate/soak/proof tasks.
- Optional reminders and notifications.

## v0.6 — Gather + Prep
- Exact lot selection.
- Gather by location.
- Combined prep tasks/groups across meal components.

## v0.7 — Cooking Mode
- Step-by-step cooking view.
- Multiple timers.
- Equipment/temperature display.
- Multi-component coordination.

## v0.8 — Completion + Leftovers
- Actual ingredient usage.
- Automatic inventory deductions.
- Actual servings and leftover creation.
- Leftover reservations and shortage detection.

## v0.9 — Dashboard + Alerts
- Operational dashboard.
- Use-soon recommendations.
- Cycle issues and shopping shortages.
- Daily/evening summaries.

## v1.0 — Initial Complete Product
All core recipe, meal, cycle, inventory, shopping, expiration, prep, cooking, leftover, history, notification and dashboard workflows integrated and reliable.

## Deferred beyond v1.0
- Live grocery prices/store APIs.
- Receipt/barcode scanning.
- Nutrition optimization.
- AI-generated recipes.
- Native mobile apps.
- Smart-home/appliance integrations.
