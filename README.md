# Cycle Meal Planner

A self-hosted/web-based meal planning application for recipes, reusable meals, flexible meal cycles, inventory, shopping, leftovers, prep, cooking, and pantry reconciliation.

## Project status

Active development is in v0.8 Completion + Leftovers. v0.7 Cooking Mode is complete, including step-by-step execution, persistent multiple timers, equipment/temperature context, and multi-component coordination. The current v0.8 work adds a draft reconciliation flow for planned-versus-actual ingredient usage before Inventory finalization.

## Stack

- React + TypeScript frontend
- Python + FastAPI backend
- SQLAlchemy + Alembic
- SQLite for the one-click desktop release
- Docker as an optional self-hosted deployment method later

Detailed product, architecture, workflow, data model, and roadmap documentation lives under `docs/`.
