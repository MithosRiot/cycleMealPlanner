# Cycle Meal Planner

A self-hosted/web-based meal planning application for recipes, reusable meals, flexible meal cycles, inventory, shopping, leftovers, prep, cooking, and pantry reconciliation.

## Project status

Active development is in v0.9 Dashboard + Alerts. v0.8 Completion + Leftovers is complete. v0.9 now includes the operational Dashboard foundation for current-cycle meals, today's prep work, and high-level Ingredient/produced-stock status. The deterministic seeded reset starts Sample Week on the reset date; immediately after reset the Dashboard stock summary is expected to show 16 tracked Ingredients, 3 with active reservations, 0 Ingredient shortages, and 0 produced lots until Meal production is committed.

## Stack

- React + TypeScript frontend
- Python + FastAPI backend
- SQLAlchemy + Alembic
- SQLite for the one-click desktop release
- Docker as an optional self-hosted deployment method later

Detailed product, architecture, workflow, data model, and roadmap documentation lives under `docs/`.