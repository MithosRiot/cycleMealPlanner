# Milestone 1 — Foundation + Recipe Library

## Status
Milestone 1 is implemented and validated end to end.

## Goal
Deliver a stable application foundation with usable Recipe CRUD and basic Inventory support.

## Implemented
1. FastAPI application skeleton, health endpoint, configuration and structured logging.
2. SQLite + SQLAlchemy persistence with Alembic migrations, foreign keys and WAL mode.
3. React + TypeScript + Vite application shell with responsive navigation and TanStack Query.
4. Household settings and default servings.
5. Measurement-unit seed data with safe same-family conversions.
6. Shopping-category management.
7. Hierarchical inventory-location management.
8. Ingredient CRUD with aliases, defaults, search and archive behavior.
9. Reusable tags.
10. Recipe and structured RecipeIngredient persistence.
11. Recipe meal types, tags, favorites, serving yield and prep/cook metadata.
12. Authoritative Decimal scaling for LINEAR, FIXED, ROUND_UP and MANUAL modes.
13. Recipe CRUD/search/filter/archive APIs.
14. Recipe Library, Editor, Detail and serving-scaler UI.
15. Inventory lots with independent quantities, locations and expiration-related dates.
16. Inventory transaction history for purchases, manual adds/removals, corrections and transfers.
17. Inventory browsing by ingredient or location with add/move/correct/deplete workflows.
18. End-to-end restart/persistence validation covering the complete Milestone 1 user path.

## Validated user path
A fresh database can:
1. Initialize automatically without manual database setup.
2. Create and edit inventory locations.
3. Create an ingredient with aliases and reference defaults.
4. Create a reusable tag.
5. Create a recipe with structured ingredients, meal type and tag.
6. Scale that recipe to another serving count using Decimal arithmetic.
7. Add a purchased inventory lot with an expiration date.
8. Remove quantity, transfer the lot and correct its physical count while retaining transaction history.
9. Reject an operation that would produce a negative quantity.
10. Restart the application and recover the locations, ingredient/alias, recipe, inventory balance, location, expiration date and transaction history from SQLite.

## Known Milestone 1 limitations
- Meal templates and multi-recipe meals begin in Milestone 2.
- Meal-cycle planning is not implemented yet.
- Shopping-list generation and automated inventory subtraction are not implemented yet.
- Inventory reservations and calculated Available quantity are later features.
- Expiration dates are stored and displayed, but expiration-aware ranking/alerts are later milestones.
- Inventory consumption is manual in Milestone 1; cooking completion does not yet reconcile stock automatically.
- Recipe preparation groups, step-by-step cooking mode, substitutions, dependencies and advanced outputs are later milestones.
- Authentication/multi-user behavior is intentionally outside the current local-first foundation.
- The development database defaults to `./data`; the packaged Windows release will move persistent user data outside the installation directory.

## Completion criteria
Milestone 1 is complete when a user can:
1. Launch the application.
2. Create/edit inventory locations.
3. Create ingredients and aliases.
4. Create a recipe with structured ingredients.
5. Set `Serves X` and scale the recipe to another serving count.
6. Add tags/meal types and search/filter recipes.
7. Enter pantry/fridge/freezer inventory and adjust or move lots safely.
8. Close/reopen the application without losing data.

These criteria are now covered by feature tests plus the end-to-end persistence test.

Meal templates begin in Milestone 2. Meal-cycle planning and shopping workflows follow in later milestones.
