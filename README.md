# Cycle Meal Planner

A self-hosted/web-based meal planning application for recipes, reusable meals, flexible meal cycles, inventory, shopping, leftovers, prep, cooking, and pantry reconciliation.

## Project status

v0.9 Dashboard + Alerts is complete. Active development is now v1.0 Initial Complete Product. v1.0 now includes an explicit Meal Cycle lifecycle plus the complete planned-occurrence model: saved Meals, direct Recipes, Leftovers, RecipeOutputs, Manual entries, Eating Out, and Skipped meals. Direct Recipes retain the normal food workflow; non-food occurrences persist as historical plan entries while creating no Ingredient reservations, Shopping demand, prep, Gather, Cooking, or Inventory deductions.

ACTIVE Meal Cycles now support safe revisions to unfinalized occurrences. Adding, replacing, moving, removing, or changing serving quantities reconciles Ingredient reservations, produced-stock coverage, Gather selections, Shopping demand, validation, prep, and other derived operational views in the same transaction. Shopping preserves completed purchase history while surfacing plan-added demand, removed demand, and already-purchased excess. Finalized occurrences remain immutable. The deterministic seeded reset starts Sample Week on the reset date; before any production is committed its Dashboard stock summary shows 16 tracked Ingredients, 3 with active reservations, 0 Ingredient shortages, and 0 produced lots.

## Stack

- React + TypeScript frontend
- Python + FastAPI backend
- SQLAlchemy + Alembic
- SQLite for the one-click desktop release
- Docker as an optional self-hosted deployment method later

Detailed product, architecture, workflow, data model, and roadmap documentation lives under `docs/`.
