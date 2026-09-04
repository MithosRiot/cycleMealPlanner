# Cycle Meal Planner

A self-hosted/web-based meal planning application for recipes, reusable meals, flexible meal cycles, inventory, shopping, leftovers, prep, cooking, and pantry reconciliation.

## Project status

Active development is in v0.8 Completion + Leftovers. v0.7 Cooking Mode is complete. v0.8 now includes draft reconciliation of planned-versus-actual ingredient usage, atomic Meal finalization and Inventory deduction, post-finalization production reconciliation for actual servings and Recipe outputs, automatic release of completed Meal ingredient reservations, and exact-source future coverage for leftovers or Recipe-output stock with Physical / Reserved / Available quantities and deterministic shortage warnings.

## Stack

- React + TypeScript frontend
- Python + FastAPI backend
- SQLAlchemy + Alembic
- SQLite for the one-click desktop release
- Docker as an optional self-hosted deployment method later

Detailed product, architecture, workflow, data model, and roadmap documentation lives under `docs/`.
