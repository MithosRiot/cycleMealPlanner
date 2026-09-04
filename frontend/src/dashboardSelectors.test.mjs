import assert from 'node:assert/strict'
import { inventoryDashboardSummary, producedInventoryDashboardSummary, selectCurrentCycle, todaysMealSlots, todaysPrepTasks } from './dashboardSelectors.ts'

const savedMeal = {
  id: 1,
  cycle_slot_id: 3,
  meal_id: 1,
  source_type: 'SAVED_MEAL',
  source_origin_planned_meal_id: null,
  source_record_id: null,
  source_recipe_output_id: null,
  source_quantity: null,
  source_unit_id: null,
  locked: true,
  planned_servings: '4',
  planned_leftover_servings: '1',
  component_serving_overrides: '{}',
  scaled_components: '[]',
  snapshot_name: 'Chicken Dinner',
  snapshot_description: null,
  snapshot_meal_types: '["DINNER"]',
  snapshot_components: '[]',
  scheduled_date: '2026-09-04',
  serving_time: '18:30:00',
  scheduled_datetime: '2026-09-04T18:30:00',
}

const cycle = {
  id: 1,
  household_id: 1,
  name: 'Sample Week',
  duration_days: 7,
  status: 'DRAFT',
  start_date: '2026-09-04',
  notes: null,
  population_rules: '{}',
  smart_preferences: '{}',
  slot_definitions: [],
  slots: [
    { id: 1, cycle_id: 1, slot_definition_id: 1, day_number: 1, sort_order: 0, scheduled_date: '2026-09-04', serving_time: '08:00:00', scheduled_datetime: '2026-09-04T08:00:00', planned_meal: null },
    { id: 3, cycle_id: 1, slot_definition_id: 3, day_number: 1, sort_order: 2, scheduled_date: '2026-09-04', serving_time: '18:30:00', scheduled_datetime: '2026-09-04T18:30:00', planned_meal: savedMeal },
  ],
}

const now = new Date(2026, 8, 4, 15, 0, 0)
assert.equal(selectCurrentCycle([cycle], now)?.name, 'Sample Week')
assert.equal(todaysMealSlots(cycle, now).length, 1)
assert.equal(todaysMealSlots(cycle, now)[0].planned_meal.snapshot_name, 'Chicken Dinner')
assert.equal(todaysMealSlots(cycle, new Date(2026, 8, 12)).length, 0)

const prep = [
  { planned_meal_id: 1, cycle_slot_id: 3, meal_id: 1, meal_name: 'Chicken Dinner', recipe_id: 1, recipe_name: 'Chicken and Rice', advance_prep_id: 1, task_type: 'PREP', title: 'Rinse rice', instructions: null, prep_group_id: 1, prep_group_name: 'Rice prep', lead_time_minutes: 30, duration_minutes: 5, serving_datetime: '2026-09-04T18:30:00', start_datetime: '2026-09-04T18:00:00', end_datetime: '2026-09-04T18:05:00', reminder_enabled: false, reminder_offset_minutes: null, reminder_at: null, reminder_status: 'DISABLED', unresolved_reason: null },
  { planned_meal_id: 2, cycle_slot_id: 6, meal_id: 1, meal_name: 'Tomorrow', recipe_id: 1, recipe_name: 'Chicken and Rice', advance_prep_id: 2, task_type: 'THAW', title: 'Tomorrow task', instructions: null, prep_group_id: null, prep_group_name: null, lead_time_minutes: 480, duration_minutes: 5, serving_datetime: '2026-09-05T18:30:00', start_datetime: '2026-09-05T10:30:00', end_datetime: '2026-09-05T10:35:00', reminder_enabled: false, reminder_offset_minutes: null, reminder_at: null, reminder_status: 'DISABLED', unresolved_reason: null },
]
assert.equal(todaysPrepTasks(prep, now).length, 1)
assert.equal(todaysPrepTasks(prep, now)[0].title, 'Rinse rice')

assert.deepEqual(inventoryDashboardSummary([
  { ingredient_id: 1, unit_family: 'MASS', unit_id: 2, unit_code: 'lb', physical_quantity: '3', reserved_quantity: '1', available_quantity: '2', shortage_quantity: '0' },
  { ingredient_id: 2, unit_family: 'MASS', unit_id: 2, unit_code: 'lb', physical_quantity: '0', reserved_quantity: '0', available_quantity: '0', shortage_quantity: '1' },
]), { tracked: 2, reserved: 1, shortages: 1 })

assert.deepEqual(producedInventoryDashboardSummary([
  { lot_id: 1, source_type: 'LEFTOVER', source_id: 1, source_name: 'Leftover: Chicken Dinner', unit_id: 16, physical_quantity: '3', reserved_quantity: '2', available_quantity: '1', expiration_date: null },
]), { lots: 1, reservedLots: 1, availableLots: 1 })
