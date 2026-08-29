# Changelog

All notable changes to Cycle Meal Planner will be documented here.

## 0.1.0-dev

### Added
- Initial repository bootstrap and product planning documentation.
- FastAPI backend foundation with SQLite, SQLAlchemy, Alembic, WAL mode, foreign-key enforcement, structured logging, and health checks.
- React + TypeScript + Vite frontend shell with routing, responsive navigation, TanStack Query, and backend connectivity status.
- Household defaults, measurement units, safe same-family unit conversion, shopping categories, and hierarchical inventory locations.
- Ingredient and alias management with duplicate/collision protection, reference defaults, search, archive behavior, and reusable tags.
- Recipe and structured RecipeIngredient models with servings, optional yield, meal types, tags, preparation metadata, required state, favorites, and archive behavior.
- Authoritative Decimal recipe scaling for LINEAR, FIXED, ROUND_UP, and MANUAL modes, including safe same-family unit overrides.
- Recipe CRUD/search/filter/scale APIs and backend test coverage.
