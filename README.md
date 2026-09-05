# Cycle Meal Planner

A self-hosted/web-based meal planning application for recipes, reusable meals, flexible meal cycles, inventory, shopping, leftovers, prep, cooking, and pantry reconciliation.

## Project status

v0.9 Dashboard + Alerts is complete. Active development is now v1.0 Initial Complete Product. The first v1.0 increment adds an explicit Meal Cycle lifecycle: draft cycles can be validated and activated, only one cycle may be ACTIVE for a household, active cycles are treated as the current Dashboard cycle, and completion/cancellation release remaining reservations safely. ACTIVE plan editing remains intentionally frozen until the dedicated active-cycle revision/reconciliation increment is implemented.

The deterministic seeded reset starts Sample Week on the reset date; before any production is committed its Dashboard stock summary shows 16 tracked Ingredients, 3 with active reservations, 0 Ingredient shortages, and 0 produced lots.

## Stack

- React + TypeScript frontend
- Python + FastAPI backend
- SQLAlchemy + Alembic
- SQLite for the one-click desktop release
- Docker as an optional self-hosted deployment method later

Detailed product, architecture, workflow, data model, and roadmap documentation lives under `docs/`.