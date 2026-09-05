import assert from 'node:assert/strict'
import { buildDailySummary, buildEveningSummary } from './dashboardSummaries.ts'

const savedMeal = {
  id: 1, cycle_slot_id: 3, meal_id: 1, source_type: 'SAVED_MEAL', source_origin_planned_meal_id: null,
  source_record_id: null, source_recipe_output_id: null, source_quantity: null, source_unit_id: null,
  locked: true, planned_servings: '4', planned_leftover_servings: '1', component_serving_overrides: '{}',
  scaled_components: '[]', snapshot_name: 'Chicken Dinner', snapshot_description: null,
  snapshot_meal_types: '["DINNER"]', snapshot_components: '[]', scheduled_date: '2026-09-05',
  serving_time: '18:30:00', scheduled_datetime: '2026-09-05T18:30:00',
}
const cycle = {
  id: 1, household_id: 1, name: 'Sample Week', duration_days: 7, status: 'DRAFT', start_date: '2026-09-05',
  notes: null, population_rules: '{}', smart_preferences: '{}', slot_definitions: [],
  slots: [
    { id: 3, cycle_id: 1, slot_definition_id: 3, day_number: 1, sort_order: 2, scheduled_date: '2026-09-05', serving_time: '18:30:00', scheduled_datetime: '2026-09-05T18:30:00', planned_meal: savedMeal },
  ],
}
const prep = [
  { planned_meal_id: 1, cycle_slot_id: 3, meal_id: 1, meal_name: 'Chicken Dinner', recipe_id: 1, recipe_name: 'Chicken and Rice', advance_prep_id: 1, task_type: 'PREP', title: 'Rinse rice', instructions: null, prep_group_id: 1, prep_group_name: 'Rice prep', lead_time_minutes: 30, duration_minutes: 5, serving_datetime: '2026-09-05T18:30:00', start_datetime: '2026-09-05T18:00:00', end_datetime: '2026-09-05T18:05:00', reminder_enabled: false, reminder_offset_minutes: null, reminder_at: null, reminder_status: 'DISABLED', unresolved_reason: null },
  { planned_meal_id: 2, cycle_slot_id: 6, meal_id: 1, meal_name: 'Tomorrow Dinner', recipe_id: 1, recipe_name: 'Chicken and Rice', advance_prep_id: 2, task_type: 'THAW', title: 'Thaw chicken', instructions: null, prep_group_id: null, prep_group_name: null, lead_time_minutes: 480, duration_minutes: 5, serving_datetime: '2026-09-06T18:30:00', start_datetime: '2026-09-06T10:30:00', end_datetime: '2026-09-06T10:35:00', reminder_enabled: false, reminder_offset_minutes: null, reminder_at: null, reminder_status: 'DISABLED', unresolved_reason: null },
]
const validation = [{ severity: 'WARNING', code: 'INVENTORY_SHORTAGE', message: 'Onion is short.', context: { ingredient_id: 10 }, key: 'warning-onion' }]
const shopping = [{ id: 1, ingredient_id: 10, ingredient_name: 'Onion', shopping_category_id: null, shopping_category_name: 'Produce', shopping_category_sort_order: 1, unit_id: 14, unit_code: 'each', unit_family: 'COUNT', required_quantity: '1', inventory_quantity: '0', generated_quantity: '1', adjustment_quantity: '0', final_quantity: '1', source_trace: '[]', warning: null, status: 'PENDING', actual_quantity: null, actual_unit_id: null, actual_unit_code: null, purchase_date: null, storage_location_id: null, expiration_date: null, purchase_notes: null, inventory_lot_id: null, completed_at: null }]
const useSoon = [{ lot_id: 4, source_type: 'INGREDIENT', source_id: null, source_name: 'Milk', ingredient_id: 4, location_id: 2, location_name: 'Refrigerator', available_quantity: '1', unit_id: 8, unit_code: 'cup', expiration_date: '2026-09-12', days_remaining: 7 }]

const afternoon = new Date(2026, 8, 5, 13, 0, 0)
const daily = buildDailySummary(cycle, prep, validation, shopping, useSoon, afternoon)
assert.equal(daily.mealCount, 1)
assert.equal(daily.prepCount, 1)
assert.equal(daily.nextMealName, 'Chicken Dinner')
assert.equal(daily.validationCount, 1)
assert.equal(daily.shoppingCount, 1)
assert.equal(daily.useSoonCount, 1)
assert.equal(daily.topValidation?.code, 'INVENTORY_SHORTAGE')
assert.equal(daily.topShopping?.ingredient_name, 'Onion')
assert.equal(daily.mostUrgentUseSoon?.source_name, 'Milk')

const evening = buildEveningSummary(cycle, prep, afternoon)
assert.equal(evening.remainingMealCount, 1)
assert.equal(evening.remainingPrepCount, 1)
assert.equal(evening.tomorrowPrep.length, 1)
assert.equal(evening.tomorrowPrep[0].title, 'Thaw chicken')

const late = buildEveningSummary(cycle, prep, new Date(2026, 8, 5, 23, 0, 0))
assert.equal(late.remainingMealCount, 0)
assert.equal(late.remainingPrepCount, 0)
assert.equal(late.tomorrowPrep.length, 1)

const resolved = buildDailySummary(cycle, prep, [], [], [], afternoon)
assert.equal(resolved.validationCount, 0)
assert.equal(resolved.shoppingCount, 0)
assert.equal(resolved.useSoonCount, 0)
assert.equal(resolved.topValidation, null)
assert.equal(resolved.topShopping, null)
assert.equal(resolved.mostUrgentUseSoon, null)

console.log('dashboard summary checks passed')
