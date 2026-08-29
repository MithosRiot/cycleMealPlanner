# Data Model

This document summarizes the planned relational model. SQLite is the primary packaged-release database; SQLAlchemy/Alembic will implement and migrate the schema.

## Core
### households
- id
- name
- default_servings
- created_at / updated_at

### users
- id
- household_id
- email
- password_hash
- display_name
- active

### measurement_units
- id
- code
- name
- unit_family
- base_multiplier
- allows_fraction

### tags
- id
- household_id
- name
- category
- active

## Inventory
### ingredients
Canonical ingredient identity.
- id
- household_id
- name
- shopping_category_id
- preferred_unit
- unit_family
- perishable
- default_location_id
- active
- notes

### ingredient_aliases
- id
- ingredient_id
- alias

### inventory_locations
Hierarchical physical storage.
- id
- household_id
- parent_location_id
- name
- location_type
- sort_order
- active

### inventory_lots
Physical food lots.
- id
- household_id
- ingredient_id
- location_id
- quantity
- unit_id
- purchase_date
- opened_date
- expiration_date
- frozen_date
- thawed_date
- is_open
- status
- notes

### inventory_transactions
History of physical inventory change.
Types include PURCHASE, CONSUME, TRANSFER, WASTE, EXPIRED, MANUAL_ADD, MANUAL_REMOVE, CORRECTION.

### stock_rules
- ingredient_id
- minimum_quantity
- target_quantity
- unit_id
- preferred_location_id
- active

## Recipes
### recipes
- id
- household_id
- name / description
- base_servings
- serving_unit
- optional yield quantity/unit
- prep/cook/rest minutes
- favorite / active
- image_path
- notes
- derived_from_recipe_id

### recipe_ingredients
- recipe_id
- ingredient_id
- quantity / unit_id
- preparation_text
- required_state
- scaling_mode
- optional
- prep_group_id
- sort_order
- notes

Scaling modes: LINEAR, FIXED, ROUND_UP, MANUAL.

### recipe_prep_groups
DRY_MIX, WET_MIX, SAUCE, MARINADE, CHOPPED, FILLING, TOPPING, DOUGH, CUSTOM.

### recipe_ingredient_prep
Optional structured actions such as CHOP, DICE, MINCE, PEEL, SHRED, MELT, SOFTEN, THAW.

### recipe_prep_tasks
Advance preparation with timing offsets/windows.

### recipe_steps
Ordered cooking instructions with optional timing, equipment, temperature and prep-group references.

### equipment / recipe_equipment
Required/preferred equipment relationships.

### recipe_ingredient_substitutions
Alternative ingredient, quantity/unit, preferred flag.

### recipe_outputs
Reusable output such as cooked shredded chicken or stock.

### recipe_dependencies
Defines required outputs/prepared components from another source.

### recipe_tags / recipe_meal_types
Many-to-many tags and compatible meal slots.

## Meals
### meals
Reusable meal template.
- id
- household_id
- name
- description
- default_servings
- favorite / active
- notes

### meal_recipes
Recipes composing the meal.
Serving rules: MATCH_MEAL, RATIO, FIXED.

### meal_tags / meal_types
Meal-level categorization.

## Planning
### meal_cycles
- id
- household_id
- name
- duration_days
- optional start_date
- status
- default_servings
- revision_number

Statuses: DRAFT, READY, SHOPPING, ACTIVE, COMPLETED, ARCHIVED.

### meal_slot_definitions
Household-configurable meal slots and default times.

### cycle_slots
- cycle_id
- day_number
- meal_slot_definition_id
- optional planned_date

Unique by cycle/day/slot.

### planned_meals
A concrete planned occurrence.
Source types: SAVED_MEAL, RECIPE, LEFTOVER, MANUAL, SKIP.

### planned_meal_components
Snapshots component recipes for the occurrence so template edits do not rewrite a plan/history.

### planned_ingredient_overrides
SUBSTITUTE, CHANGE_QUANTITY, OMIT, ADD.

### planned_leftovers
Connect source production to a later meal.
Types: MEAL_SERVINGS, RECIPE_SERVINGS, RECIPE_OUTPUT.

### cycle_selection_pool
Candidate Meals/Recipes/tags plus min/max usage and priority.

### cycle_population_rules
Required/preferred population constraints.

### cycle_validation_issues
Errors/warnings/info discovered during validation.

### cycle_revisions
Revision boundaries used to compare shopping/plan changes.

### inventory_reservations
Ingredient-level future reservations. Reservations do not change physical lot quantity.

## Shopping
### shopping_categories
User-configurable list grouping/order.

### ingredient_requirements
Optional persisted shopping snapshot/provenance for a cycle revision.

### shopping_lists
- household_id
- cycle_id
- cycle_revision_id
- status
- created/completed dates

### shopping_list_items
- ingredient or manual description
- required quantity
- inventory covered
- quantity to buy
- category
- actual quantity bought
- status

## Execution
### advance_prep_task_instances
Concrete scheduled tasks generated from recipe definitions or inventory state.

### gather_assignments
Maps planned ingredient usage to exact inventory lots close to gather time.

### generated_prep_items
Interactive prep checklist items.

### cooking_sessions
Represents execution of a planned meal.

### cooking_step_instances
Execution/status of recipe steps.

### actual_ingredient_usage
Planned vs actual ingredient usage and substitutions.

### actual_usage_lots
Allocates actual usage across one or more inventory lots.

## Leftovers and history
### leftover_lots
Physical leftovers or reusable recipe outputs with quantity, location and expiration.

### leftover_reservations
Reserves actual leftovers for future planned meals.

### meal_history
Snapshot of what was actually cooked/eaten, serving counts, rating and notes.

## Alerts/notifications
### alerts
Persistent in-app actionable issues such as expiration conflicts or leftover shortages.

### notifications
Scheduled reminder records.

### notification_preferences
Household defaults and lead times.

## Stored vs calculated
Store facts and user decisions. Calculate derived state whenever practical.

Calculated examples:
- total inventory by ingredient
- reserved quantity total
- available quantity = physical - active reservations
- projected ending inventory
- expiration urgency/use-soon score
- recipe scaling factor
- total cycle ingredient requirement
- shopping shortage
- cycle completion percentage
- meal recommendation score

Do not store derived values such as `available_quantity` on the ingredient itself.

## Key design rules
- One Ingredient can have many physical InventoryLots.
- Locations may be nested.
- Historical references should survive recipe/meal archival.
- Core reusable objects use soft-deactivation rather than destructive deletion once referenced.
- Planned/cooked instances snapshot mutable templates where needed.
- Quantities use decimal/numeric semantics, not binary floats.
- Foreign keys are enabled in SQLite.
- Multi-record operations such as meal completion are transactional.
