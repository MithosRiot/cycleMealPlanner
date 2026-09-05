# Cycle Meal Planner

A self-hosted/web-based meal planning application for recipes, reusable meals, flexible meal cycles, inventory, shopping, leftovers, prep, cooking, and pantry reconciliation.

## Project status

Active development is in v0.9 Dashboard + Alerts. v0.8 Completion + Leftovers is complete. v0.9 includes the operational Dashboard foundation plus use-soon recommendations for available Ingredient and produced Inventory expiring within seven days. Recommendations use reservation-aware Available quantities and are ordered by expiration urgency. The deterministic seeded reset starts Sample Week on the reset date; before any production is committed its Dashboard stock summary shows 16 tracked Ingredients, 3 with active reservations, 0 Ingredient shortages, and 0 produced lots.

## Stack

- React + TypeScript frontend
- Python + FastAPI backend
- SQLAlchemy + Alembic
- SQLite for the one-click desktop release
- Docker as an optional self-hosted deployment method later

Detailed product, architecture, workflow, data model, and roadmap documentation lives under `docs/`.