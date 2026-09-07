import assert from 'node:assert/strict'
import { canSubmitDiscard } from './inventoryDiscardSelectors.ts'

assert.equal(canSubmitDiscard('1', 'Expired container', '5'), true)
assert.equal(canSubmitDiscard('5', 'Use-by passed', '5'), true)
assert.equal(canSubmitDiscard('6', 'Too much', '5'), false)
assert.equal(canSubmitDiscard('0', 'No quantity', '5'), false)
assert.equal(canSubmitDiscard('-1', 'Negative', '5'), false)
assert.equal(canSubmitDiscard('1', '   ', '5'), false)
assert.equal(canSubmitDiscard('abc', 'Bad number', '5'), false)

console.log('Inventory discard selector tests passed')
