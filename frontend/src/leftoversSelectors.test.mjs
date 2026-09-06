import assert from 'node:assert/strict'
import { eligibleFutureSlots, leftoverState } from './leftoversSelectors.ts'

const baseOption = {
  source_type: 'LEFTOVER',
  source_origin_planned_meal_id: 10,
  source_record_id: 22,
  source_recipe_output_id: null,
  source_name: 'Leftover: Chili',
  source_meal_id: 5,
  unit_id: 16,
  unit_code: 'serving',
  planned_quantity: '4',
  physical_quantity: '3',
  reserved_quantity: '1',
  available_quantity: '2',
  lot_id: 44,
  expiration_date: '2026-09-08',
}

assert.equal(leftoverState({ ...baseOption, reserved_quantity: '0', available_quantity: '3' }, '2026-09-06'), 'AVAILABLE')
assert.equal(leftoverState(baseOption, '2026-09-06'), 'RESERVED')
assert.equal(leftoverState({ ...baseOption, available_quantity: '0', reserved_quantity: '3' }, '2026-09-06'), 'RESERVED')
assert.equal(leftoverState({ ...baseOption, physical_quantity: '0', available_quantity: '0' }, '2026-09-06'), 'EXHAUSTED')
assert.equal(leftoverState({ ...baseOption, expiration_date: '2026-09-05' }, '2026-09-06'), 'EXPIRED')
assert.equal(leftoverState({ ...baseOption, lot_id: null, source_record_id: null }, '2026-09-06'), 'PLANNED')

const cycles = [{
  id: 1,
  household_id: 1,
  name: 'Cycle A',
  duration_days: 12,
  status: 'ACTIVE',
  start_date: '2026-09-01',
  notes: null,
  population_rules: '{}',
  smart_preferences: '{}',
  activated_at: null,
  completed_at: null,
  cancelled_at: null,
  slot_definitions: [{ id: 1, cycle_id: 1, label: 'Dinner', sort_order: 1, serving_time: null }],
  slots: [
    { id: 100, cycle_id: 1, slot_definition_id: 1, day_number: 2, sort_order: 1, scheduled_date: '2026-09-02', serving_time: null, scheduled_datetime: '2026-09-02T18:00:00', planned_meal: { id: 10 } },
    { id: 101, cycle_id: 1, slot_definition_id: 1, day_number: 2, sort_order: 2, scheduled_date: '2026-09-02', serving_time: null, scheduled_datetime: '2026-09-02T19:00:00', planned_meal: null },
    { id: 102, cycle_id: 1, slot_definition_id: 1, day_number: 10, sort_order: 1, scheduled_date: '2026-09-10', serving_time: null, scheduled_datetime: '2026-09-10T18:00:00', planned_meal: null },
    { id: 99, cycle_id: 1, slot_definition_id: 1, day_number: 1, sort_order: 1, scheduled_date: '2026-09-01', serving_time: null, scheduled_datetime: '2026-09-01T18:00:00', planned_meal: null },
  ],
}]

const future = eligibleFutureSlots(baseOption, cycles)
assert.deepEqual(future.map((row) => row.slot.id), [101, 102])
console.log('leftovers selectors: ok')
