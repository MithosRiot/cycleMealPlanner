import assert from 'node:assert/strict'
import { manualShoppingCreatesInventory, manualShoppingDisplayQuantity } from './manualShoppingApi.ts'

assert.equal(manualShoppingDisplayQuantity({ quantity: '2.000000', unit_code: null }), '2')
assert.equal(manualShoppingDisplayQuantity({ quantity: '6.000000', unit_code: 'each' }), '6 each')
assert.equal(manualShoppingCreatesInventory({ ingredient_id: null }, true), false)
assert.equal(manualShoppingCreatesInventory({ ingredient_id: 42 }, false), false)
assert.equal(manualShoppingCreatesInventory({ ingredient_id: 42 }, true), true)

console.log('manual shopping selectors: ok')
