import type { CycleSlot, PlannedMeal } from './mealCyclesApi'

export type ProducedSourceSlot = CycleSlot & { planned_meal: PlannedMeal }

export function producedSourcePlacements(slots: CycleSlot[]): ProducedSourceSlot[] {
  return slots.filter((slot): slot is ProducedSourceSlot =>
    slot.planned_meal !== null && slot.planned_meal.source_type !== 'SAVED_MEAL'
  )
}
