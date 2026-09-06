import assert from 'node:assert/strict'
import { hasUnresolvedShoppingDemand, isShoppingSubstitution, shoppingPurchaseCount } from './shoppingApi.ts'

const partial = {
  ingredient_id: 9501,
  status: 'PENDING',
  remaining_quantity: '2.000000',
  purchases: [{ id: 1 }],
}
const completedSubstitution = {
  ingredient_id: 9502,
  status: 'COMPLETED',
  remaining_quantity: '0.000000',
  purchases: [{ id: 2 }],
}

assert.equal(hasUnresolvedShoppingDemand(partial), true, 'partial purchase must remain unresolved while quantity remains')
assert.equal(hasUnresolvedShoppingDemand(completedSubstitution), false, 'fully satisfied substitution must not remain pending')
assert.equal(isShoppingSubstitution(partial, 9501), false, 'buying the planned Ingredient is not a substitution')
assert.equal(isShoppingSubstitution(completedSubstitution, 9503), true, 'buying a different Ingredient is a substitution')
assert.equal(shoppingPurchaseCount([partial, completedSubstitution]), 2, 'purchase history count must include partial and substitution records')

console.log('Shopping partial/substitution selectors passed')
