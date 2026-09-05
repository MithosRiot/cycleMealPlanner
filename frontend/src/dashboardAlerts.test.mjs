import assert from 'node:assert/strict'
import { dashboardShoppingShortages, dashboardValidationAlerts } from './dashboardAlerts.ts'

const validation = [
  { severity: 'WARNING', code: 'BETA', message: 'Beta warning', context: { planned_meal_id: 2 } },
  { severity: 'ERROR', code: 'ALPHA', message: 'Alpha error', context: { planned_meal_id: 1 } },
  { severity: 'ERROR', code: 'ALPHA', message: 'Alpha error', context: { planned_meal_id: 1 } },
]
const alerts = dashboardValidationAlerts(validation)
assert.equal(alerts.length, 2)
assert.equal(alerts[0].severity, 'ERROR')
assert.equal(alerts[0].code, 'ALPHA')
assert.equal(alerts[1].severity, 'WARNING')
assert.equal(alerts[1].code, 'BETA')

const shoppingBase = {
  ingredient_id: 1,
  shopping_category_id: null,
  shopping_category_name: 'Uncategorized',
  shopping_category_sort_order: 9999,
  unit_id: 14,
  unit_code: 'each',
  unit_family: 'COUNT',
  required_quantity: '1',
  inventory_quantity: '0',
  adjustment_quantity: '0',
  final_quantity: '1',
  source_trace: '[]',
  warning: null,
  actual_quantity: null,
  actual_unit_id: null,
  actual_unit_code: null,
  purchase_date: null,
  storage_location_id: null,
  expiration_date: null,
  purchase_notes: null,
  inventory_lot_id: null,
  completed_at: null,
}
const shortages = dashboardShoppingShortages([
  { ...shoppingBase, id: 2, ingredient_name: 'Onion', generated_quantity: '2', status: 'PENDING' },
  { ...shoppingBase, id: 1, ingredient_name: 'Chicken Breast', generated_quantity: '1', status: 'PENDING' },
  { ...shoppingBase, id: 3, ingredient_name: 'Rice', generated_quantity: '3', status: 'COMPLETED' },
  { ...shoppingBase, id: 4, ingredient_name: 'Salt', generated_quantity: '0', status: 'PENDING' },
])
assert.deepEqual(shortages.map((item) => item.ingredient_name), ['Chicken Breast', 'Onion'])
console.log('dashboard alert selector checks passed')
