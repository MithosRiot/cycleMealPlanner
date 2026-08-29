# Milestone 1 — Foundation + Recipe Library

## Goal
Deliver a stable application foundation with usable Recipe CRUD and basic Inventory support.

## Implementation order
1. Project bootstrap and repository structure.
2. FastAPI application skeleton, health endpoint, configuration and logging.
3. SQLite + SQLAlchemy session foundation.
4. Alembic migrations, SQLite foreign keys and WAL mode.
5. React + TypeScript shell, routing, API client and TanStack Query.
6. Household/default-serving foundation.
7. Measurement-unit seed data and safe same-family conversion tests.
8. Shopping-category defaults and management.
9. Hierarchical inventory locations and management UI.
10. Ingredient/alias CRUD.
11. Tag model and reusable tag selection UI.
12. Recipe and RecipeIngredient models.
13. Recipe scaling engine and unit tests.
14. Recipe CRUD/search/filter API.
15. Recipe library/editor/detail UI.
16. InventoryLot model and basic inventory API.
17. Inventory UI by ingredient and by location.
18. InventoryTransaction foundation for add/remove/correction/transfer/purchase.
19. End-to-end persistence and restart tests.
20. Documentation/changelog update.

## Suggested branches
- `chore/project-bootstrap`
- `feature/database-foundation`
- `feature/ingredients`
- `feature/inventory-locations`
- `feature/recipe-backend`
- `feature/recipe-ui`
- `feature/inventory-foundation`

## Completion criteria
A user can:
1. Launch the application.
2. Create/edit inventory locations.
3. Create ingredients and aliases.
4. Create a recipe with structured ingredients.
5. Set `Serves X` and scale the recipe to another serving count.
6. Add tags/meal types and search recipes.
7. Enter pantry/fridge/freezer inventory.
8. Close/reopen the application without losing data.

Meal-cycle planning and shopping-list generation begin in later milestones.
