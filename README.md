# Cycle Meal Planner

A self-hosted/web-based meal planning application for recipes, reusable meals, flexible meal cycles, inventory, shopping, leftovers, prep, cooking, and pantry reconciliation.

## Project status

Active development is in v0.9 Dashboard + Alerts. v0.8 Completion + Leftovers is complete. v0.9 begins with an operational dashboard that automatically identifies the current cycle and summarizes today's scheduled Meals, today's advance-prep work, Ingredient reservation/shortage counts, and produced-stock availability. Use-soon recommendations, cycle/shopping alerts, and daily/evening summaries follow as separate focused PRs.

## Stack

- React + TypeScript frontend
- Python + FastAPI backend
- SQLAlchemy + Alembic
- SQLite for the one-click desktop release
- Docker as an optional self-hosted deployment method later

Detailed product, architecture, workflow, data model, and roadmap documentation lives under `docs/`.