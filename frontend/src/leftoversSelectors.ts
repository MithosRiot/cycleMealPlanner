import type { CycleSlot, MealCycle, ProducedSourceOption } from './mealCyclesApi'

export type LeftoverState = 'AVAILABLE' | 'RESERVED' | 'EXHAUSTED' | 'EXPIRED' | 'PLANNED'

export function leftoverState(option: ProducedSourceOption, todayIso: string): LeftoverState {
  const physical = Number(option.physical_quantity)
  const reserved = Number(option.reserved_quantity)
  const available = Number(option.available_quantity)
  if (option.lot_id === null) return 'PLANNED'
  if (physical <= 0) return 'EXHAUSTED'
  if (option.expiration_date && option.expiration_date < todayIso) return 'EXPIRED'
  if (reserved > 0 && available <= 0) return 'RESERVED'
  return 'AVAILABLE'
}

export function sourceSlotFor(option: ProducedSourceOption, cycles: MealCycle[]): { cycle: MealCycle; slot: CycleSlot } | null {
  for (const cycle of cycles) {
    const slot = cycle.slots.find((candidate) => candidate.planned_meal?.id === option.source_origin_planned_meal_id)
    if (slot) return { cycle, slot }
  }
  return null
}

function targetIsAfterSource(sourceCycle: MealCycle, sourceSlot: CycleSlot, targetCycle: MealCycle, targetSlot: CycleSlot): boolean {
  if (sourceCycle.id === targetCycle.id) {
    return [targetSlot.day_number, targetSlot.sort_order, targetSlot.id].join(':') > [sourceSlot.day_number, sourceSlot.sort_order, sourceSlot.id].join(':')
  }
  if (sourceSlot.scheduled_datetime && targetSlot.scheduled_datetime) return targetSlot.scheduled_datetime > sourceSlot.scheduled_datetime
  return true
}

export function eligibleFutureSlots(option: ProducedSourceOption, cycles: MealCycle[]): Array<{ cycle: MealCycle; slot: CycleSlot; label: string }> {
  const source = sourceSlotFor(option, cycles)
  if (!source) return []
  const result: Array<{ cycle: MealCycle; slot: CycleSlot; label: string }> = []
  for (const cycle of cycles) {
    if (cycle.status !== 'DRAFT' && cycle.status !== 'ACTIVE') continue
    for (const slot of cycle.slots) {
      if (slot.planned_meal !== null) continue
      if (!targetIsAfterSource(source.cycle, source.slot, cycle, slot)) continue
      const definition = cycle.slot_definitions.find((item) => item.id === slot.slot_definition_id)
      result.push({ cycle, slot, label: `${cycle.name} · Day ${slot.day_number} · ${definition?.label ?? 'Slot'}` })
    }
  }
  return result
}
