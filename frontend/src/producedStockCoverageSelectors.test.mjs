import assert from 'node:assert/strict'
import { emitProductionInventoryChanged, onProductionInventoryChanged } from './productionEvents.ts'
import { producedSourcePlacements } from './producedStockCoverageSelectors.ts'

const savedMeal = {
  id: 1,
  cycle_slot_id: 2,
  meal_id: 1,
  source_type: 'SAVED_MEAL',
  source_recipe_id: null,
  source_origin_planned_meal_id: null,
  source_record_id: null,
  source_recipe_output_id: null,
  source_quantity: null,
  source_unit_id: null,
  locked: false,
  planned_servings: '4',
  planned_leftover_servings: '0',
  component_serving_overrides: '{}',
  scaled_components: '[]',
  snapshot_name: 'Saved Meal',
  snapshot_description: null,
  snapshot_meal_types: '[]',
  snapshot_components: '[]',
  scheduled_date: null,
  serving_time: null,
  scheduled_datetime: null,
}

const directRecipe = {
  ...savedMeal,
  id: 4,
  cycle_slot_id: 4,
  meal_id: null,
  source_type: 'DIRECT_RECIPE',
  source_recipe_id: 5,
  snapshot_name: 'Direct Recipe',
}

const producedMeal = {
  ...savedMeal,
  id: 2,
  cycle_slot_id: 3,
  source_type: 'LEFTOVER',
  source_origin_planned_meal_id: 1,
  source_quantity: '2',
  source_unit_id: 16,
  snapshot_name: 'Leftover: Chicken Dinner',
}

const slots = [
  { id: 1, cycle_id: 1, slot_definition_id: 1, day_number: 1, sort_order: 0, scheduled_date: null, serving_time: null, scheduled_datetime: null, planned_meal: null },
  { id: 2, cycle_id: 1, slot_definition_id: 2, day_number: 1, sort_order: 1, scheduled_date: null, serving_time: null, scheduled_datetime: null, planned_meal: savedMeal },
  { id: 3, cycle_id: 1, slot_definition_id: 3, day_number: 2, sort_order: 2, scheduled_date: null, serving_time: null, scheduled_datetime: null, planned_meal: producedMeal },
  { id: 4, cycle_id: 1, slot_definition_id: 3, day_number: 3, sort_order: 2, scheduled_date: null, serving_time: null, scheduled_datetime: null, planned_meal: directRecipe },
]

const result = producedSourcePlacements(slots)
assert.equal(result.length, 1)
assert.equal(result[0].id, 3)
assert.equal(result[0].planned_meal.snapshot_name, 'Leftover: Chicken Dinner')

let refreshEvents = 0
const unsubscribe = onProductionInventoryChanged(() => { refreshEvents += 1 })
emitProductionInventoryChanged()
assert.equal(refreshEvents, 1)
unsubscribe()
emitProductionInventoryChanged()
assert.equal(refreshEvents, 1)
