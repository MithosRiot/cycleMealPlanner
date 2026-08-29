# Cycle Meal Planner — Product Specification

## Purpose
Cycle Meal Planner is a web-interface meal planning application that connects recipes, reusable meals, flexible meal cycles, household food inventory, shopping, leftovers, prep, cooking, and inventory reconciliation.

## Core user workflow
1. Enter recipes.
2. Enter pantry/fridge/freezer/etc. inventory.
3. Choose meal-cycle duration.
4. Choose recipes/meals for the cycle.
5. Populate the cycle.
6. Fill gaps.
7. Generate a shopping list that subtracts usable inventory.
8. Shop and enter actual purchased quantities into inventory.
9. Choose the cycle start date.
10. Complete advance prep/thaw tasks.
11. Gather ingredients by physical storage location.
12. Complete prep tasks.
13. Cook the meal.
14. Record actual servings and ingredient usage.
15. Deduct inventory and create leftovers.
16. Continue the cycle and feed leftovers/inventory back into planning.

## Recipe model
A Recipe is one prepared food item or component, not necessarily a complete meal.

Recipes support:
- Name, description, image, tags and meal types.
- Base servings and optional yield.
- Structured ingredients with quantity and unit.
- Ingredient preparation text and required state.
- Scaling rules.
- Prep groups such as dry mix, wet mix, sauce and marinade.
- Advance prep tasks such as thaw, soak, proof and marinate.
- Ordered cooking instructions and timers.
- Required equipment.
- Ingredient substitutions and preferred substitutions.
- Related recipe variants.
- Recipe outputs and dependencies on outputs from other recipes.

## Meal model
A Meal is a reusable combination of one or more Recipes.

Examples:
- Meatloaf Dinner = Meatloaf + Mashed Potatoes + Green Beans.
- Taco Night = Beef Tacos + Mexican Rice + Refried Beans.

Meals support:
- Default servings.
- Required and optional recipes.
- Match-meal, ratio and fixed serving rules.
- Tags and meal types.
- Per-occurrence overrides without modifying the saved template.

## Meal cycles
Meal cycles may be any user-selected duration, such as 7, 10, 21 or 30 days.

A cycle supports:
- Breakfast/lunch/dinner by default, with configurable meal slots.
- Manual meal placement.
- Locked meals.
- Rule-based random population.
- Fill-empty-slot behavior.
- Saved Meals, individual Recipes, leftovers, manual entries, eating out and skipped meals.
- Planned servings.
- Planned leftovers.
- Validation of dependencies and leftovers.
- Inventory-aware and expiration-aware recommendations.
- Plan revisions and post-shopping deltas.

## Serving and leftover math
Recipe quantities scale from the recipe's base serving/yield.

If a recipe serves X but the cycle requires Y servings, ingredient quantities scale automatically.

Planned leftovers increase production at the source meal rather than creating duplicate shopping requirements at the leftover meal.

Example: Saturday consumes 4 servings of spaghetti and Sunday consumes 2 leftover servings. Saturday production is 6 servings and shopping is calculated for 6 servings total.

## Inventory
Inventory is modeled as physical lots of canonical Ingredients.

Inventory supports:
- User-defined hierarchical locations, e.g. Pantry, Refrigerator, Kitchen Freezer, Garage Freezer, Spice Drawer.
- Multiple lots of the same Ingredient across different locations.
- Quantity and unit.
- Purchase/open/frozen/thawed/expiration dates.
- Lot splitting and transfers.
- Manual corrections, consumption, waste and spoilage.
- Stock minimum/target rules for staples.
- Reservations for future planned meals.

The gather step may pull the same ingredient from multiple lots/locations.

## Expiration-aware planning
Expiration data actively affects planning.

The planner should:
- Prefer time-sensitive inventory for earlier compatible meals.
- Warn when a planned ingredient is expected to expire before its meal.
- Suggest moving or swapping the meal earlier.
- Surface expiring inventory that has no planned use.
- Suggest recipes using one or more expiring items.
- Prefer suggestions that consume multiple expiring ingredients and require little additional shopping.
- Apply the same behavior to leftovers.
- Offer freezing as a possible resolution when appropriate.

## Shopping
Shopping requirements are calculated from scaled production requirements after substitutions and leftover/dependency resolution.

Shopping = cycle requirements + stock replenishment - usable inventory.

The shopping list supports:
- Categories/store order.
- Needed quantity rather than assumed store package size.
- Manual items.
- Actual quantity purchased.
- Partial purchases and unresolved shortages.
- Shopping-time substitutions.
- Provenance explaining why an item is required.
- Bulk intake of purchased quantities into inventory.

## Advance prep, gather and prep
After cycle activation, real dates/times are assigned.

The application supports:
- Thaw, transfer, marinate, soak, proof, brine, make-ahead and other advance tasks.
- Optional reminders/notifications.
- Gather lists grouped by inventory location.
- Exact lot selection close to gather time.
- Combined prep across all recipes in a Meal.
- Shared compatible ingredient preparation.
- Prep groups such as dry/wet mixtures.

## Cooking and reconciliation
Cooking supports step-by-step instructions and multiple timers.

Meal completion records:
- Actual ingredients used, defaulting to planned quantities.
- Last-minute substitutions.
- Actual servings produced.
- Actual servings eaten.
- Actual leftovers.
- Inventory deductions.
- Released reservations.
- Leftover lots and recipe outputs.
- Meal history and optional rating/notes.

## Dashboard and alerts
The dashboard is operational rather than analytics-heavy. It should answer:
- What am I eating today?
- What do I need to do next?
- What food needs attention?
- Is anything wrong with the cycle?

Primary dashboard areas include Today, Upcoming Prep, Use Soon, Cycle Issues, Leftovers, Shopping and Suggestions.

## Installation goal
The normal release must be a one-click style installation for nontechnical users.

Expected Windows experience:
- Download `CycleMealPlanner-Setup.exe`.
- Run installer.
- Launch Cycle Meal Planner.
- Local web UI opens automatically.

Users must not need to separately install Python, Node, SQLite, Docker or a database server.

Docker/self-hosted deployment may be offered later as an optional advanced deployment path.
