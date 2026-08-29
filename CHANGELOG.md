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
- Recipe Library, structured Recipe Editor, recipe detail view, search/filter controls, favorites/tags/meal-type display, and serving-scale preview UI.
- Physical inventory lots with location, quantity/unit, purchase/open/expiration/frozen/thawed dates, immutable transaction history, add/remove/correction/transfer operations, browse filters, and Inventory management UI.
- Milestone 1 end-to-end validation covering fresh database initialization, reference data, ingredients/aliases, tagged recipes, scaling, inventory transactions, negative-quantity protection, application restart, and persistence.

### Known limitations
- Meal templates, meal-cycle planning, shopping-list generation, reservations, expiration-aware alerts, automated cooking reconciliation, and advanced recipe execution features are planned for later milestones.
- The development database currently defaults to `./data`; packaged Windows persistence will be moved outside the installation directory.
