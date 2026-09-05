import type { MealCycle, CycleSlot } from './mealCyclesApi'
import type { InventoryAvailability, ProductionAvailability } from './reservationsApi'
import type { PrepScheduleTask } from './prepScheduleApi'

function toLocalDateKey(value: Date): string {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function localMidnight(value: Date): Date {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate())
}

export function selectCurrentCycle(cycles: MealCycle[], now = new Date()): MealCycle | null {
  const lifecycleActive = cycles.find((cycle) => cycle.status === 'ACTIVE')
  if (lifecycleActive) return lifecycleActive

  const eligible = cycles.filter((cycle) => cycle.status === 'DRAFT')
  const today = toLocalDateKey(now)
  const scheduled = eligible.filter((cycle) => cycle.start_date !== null)
  const dateActive = scheduled.find((cycle) => {
    const start = new Date(`${cycle.start_date}T00:00:00`)
    const end = new Date(start)
    end.setDate(end.getDate() + cycle.duration_days - 1)
    return cycle.start_date! <= today && toLocalDateKey(end) >= today
  })
  return dateActive ?? [...scheduled].sort((a, b) => (a.start_date ?? '').localeCompare(b.start_date ?? ''))[0] ?? eligible[0] ?? null
}

export function todaysMealSlots(cycle: MealCycle | null, now = new Date()): CycleSlot[] {
  if (!cycle?.start_date) return []
  const start = new Date(`${cycle.start_date}T00:00:00`)
  const dayNumber = Math.floor((localMidnight(now).getTime() - start.getTime()) / 86_400_000) + 1
  if (dayNumber < 1 || dayNumber > cycle.duration_days) return []
  return cycle.slots
    .filter((slot) => slot.day_number === dayNumber && slot.planned_meal !== null)
    .sort((a, b) => (a.serving_time ?? '').localeCompare(b.serving_time ?? '') || a.sort_order - b.sort_order || a.id - b.id)
}

export function todaysPrepTasks(tasks: PrepScheduleTask[], now = new Date()): PrepScheduleTask[] {
  const today = toLocalDateKey(now)
  return tasks
    .filter((task) => task.start_datetime?.slice(0, 10) === today)
    .sort((a, b) => (a.start_datetime ?? '').localeCompare(b.start_datetime ?? '') || a.planned_meal_id - b.planned_meal_id || a.advance_prep_id - b.advance_prep_id)
}

export function inventoryDashboardSummary(rows: InventoryAvailability[]) {
  return {
    tracked: rows.length,
    reserved: rows.filter((row) => Number(row.reserved_quantity) > 0).length,
    shortages: rows.filter((row) => Number(row.shortage_quantity) > 0).length,
  }
}

export function producedInventoryDashboardSummary(rows: ProductionAvailability[]) {
  return {
    lots: rows.length,
    reservedLots: rows.filter((row) => Number(row.reserved_quantity) > 0).length,
    availableLots: rows.filter((row) => Number(row.available_quantity) > 0).length,
  }
}
