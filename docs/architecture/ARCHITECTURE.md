# Technical Architecture

## Application shape
Cycle Meal Planner is a modular monolith with a browser UI, a local backend API, and an embedded SQLite database.

```text
Browser
  ↓ REST/JSON
React + TypeScript frontend
  ↓
FastAPI backend
  ├─ API routes
  ├─ domain services
  ├─ calculation engines
  └─ SQLAlchemy
  ↓
SQLite
```

## Frontend
- React + TypeScript.
- TanStack Query for server state.
- Local React state for transient UI state.
- Feature-oriented structure: dashboard, recipes, meals, inventory, planner, shopping, prep, cooking, leftovers, history.
- Drag/drop may be used in the planner, but every action must also have a non-drag UI path.

## Backend
- Python + FastAPI.
- SQLAlchemy ORM.
- Alembic migrations.
- Backend is authoritative for state-changing business logic.
- Logical services remain inside one application rather than separate microservices.

Suggested logical modules:
- RecipeService
- MealService
- InventoryService
- PlanningService
- ShoppingService
- PrepService
- LeftoverService

Calculation engines:
- serving/recipe scaling
- unit conversion
- cycle population
- expiration scoring
- inventory allocation
- dependency resolution

## Database
Primary release database: SQLite.

Reasons:
- No separate database installation/server.
- Strong relational fit for the domain.
- Suitable for a single household and low write concurrency.
- Easy backup/restore.

Runtime settings should include SQLite foreign keys and WAL mode.

Use decimal/numeric quantities rather than binary floating-point for ingredient quantities.

## Installation/release
Normal users should receive a self-contained Windows installer.

The installer/package should bundle:
- compiled React frontend
- FastAPI application
- Python runtime/application bundle
- SQLite support
- automatic database initialization/migrations

Persistent user data must be stored separately from application binaries so application upgrades do not overwrite recipes/inventory/history.

Core data:
- SQLite database
- recipe images/uploads
- backups/configuration

Users should not need to install Python, Node, Docker, PostgreSQL, or other prerequisites manually.

## Development
Development may use separate frontend/backend processes and normal development dependencies. Release packaging hides those details from the user.

## Optional self-hosted edition
A later Docker-based deployment may expose the same application on a home server/NAS. It is optional and must not become a prerequisite for the normal installer.

## API approach
Use REST/JSON rather than GraphQL.

Examples:
- `GET /recipes`
- `POST /recipes`
- `POST /cycles/{id}/populate`
- `POST /cycles/{id}/validate`
- `POST /cycles/{id}/shopping-list`
- `POST /planned-meals/{id}/complete`

## Transaction boundaries
Operations that alter multiple related records must be atomic, including:
- complete shopping
- complete meal
- move/split inventory
- activate cycle

Example meal completion transaction:
1. Record actual usage.
2. Deduct inventory.
3. Release reservations.
4. Create leftovers.
5. Update planned-leftover coverage.
6. Write history.
7. Mark meal complete.

## Testing priority
Highest-risk logic receives automated unit/service tests first:
- recipe scaling
- unit conversion
- leftover production
- inventory allocation
- shopping math
- staple thresholds
- expiration logic
- dependency resolution
- reservations

UI tests follow the domain/service tests.
