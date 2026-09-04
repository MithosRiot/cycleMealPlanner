# Cycle Meal Planner

A self-hosted/web-based meal planning application for recipes, reusable meals, flexible meal cycles, inventory, shopping, leftovers, prep, cooking, and pantry reconciliation.

## Project status

Active development is in v0.8 Completion + Leftovers. v0.7 Cooking Mode is complete. v0.8 now includes draft reconciliation of planned-versus-actual ingredient usage plus atomic Meal finalization that deducts physical Inventory, records lot-level consumption history, blocks on shortages, and prevents duplicate deductions. Leftover creation and reservation release remain the next v0.8 work.

## Stack

- React + TypeScript frontend
- Python + FastAPI backend
- SQLAlchemy + Alembic
- SQLite for the one-click desktop release
- Docker as an optional self-hosted deployment method later

Detailed product, architecture, workflow, data model, and roadmap documentation lives under `docs/`.
