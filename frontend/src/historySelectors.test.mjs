import assert from 'node:assert/strict'
import { inventoryHistoryName, signedQuantity, usageTitle } from './historySelectors.ts'

const ingredientRow = {
  transaction_id: 1, created_at: '2026-09-06T10:00:00', transaction_type: 'PURCHASE', lot_id: 7,
  ingredient_id: 3, ingredient_name: 'Eggs', source_type: 'INGREDIENT', source_id: null, source_name: null,
  quantity_delta: '12', unit_id: 14, unit_code: 'each', from_location_id: null, from_location_name: null,
  to_location_id: 2, to_location_name: 'Refrigerator', note: null,
}
assert.equal(inventoryHistoryName(ingredientRow), 'Eggs')
assert.equal(signedQuantity(ingredientRow), '+12 each')
assert.equal(inventoryHistoryName({ ...ingredientRow, ingredient_name: null, source_type: 'LEFTOVER', source_name: 'Leftover: Chicken Dinner' }), 'Leftover: Chicken Dinner')
assert.equal(signedQuantity({ ...ingredientRow, quantity_delta: '-1' }), '-1 each')

const usage = {
  recipe_name: 'Chicken and Rice', planned_ingredient_name: 'Chicken Breast', planned_quantity: '1', planned_unit_code: 'lb',
  actual_ingredient_name: 'Turkey Breast', actual_quantity: '1', actual_unit_code: 'lb', substituted: true, notes: null, allocations: [],
}
assert.equal(usageTitle(usage), 'Chicken and Rice · Turkey Breast (substitution)')
assert.equal(usageTitle({ ...usage, actual_ingredient_name: 'Chicken Breast', substituted: false }), 'Chicken and Rice · Chicken Breast')
console.log('history selectors: ok')
