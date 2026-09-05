import type { UseSoonRecommendation } from './dashboardApi'
import type { DashboardValidationAlert } from './dashboardAlerts'
import type { MealCycle } from './mealCyclesApi'
import type { PrepScheduleTask } from './prepScheduleApi'
import type { ShoppingItem } from './shoppingApi'
import { todaysMealSlots, todaysPrepTasks } from './dashboardSelectors'

export type DashboardDailySummary = {
  mealCount: number
  prepCount: number
  validationCount: number
  shoppingCount: number
  useSoonCount: number
  nextMealName: string | null
  nextMealTime: string | null
  topValidation: DashboardValidationAlert | null
  topShopping: ShoppingItem | null
  mostUrgentUseSoon: UseSoonRecommendation | null
}

export type DashboardEveningSummary = {
  remainingMealCount: number
  remainingPrepCount: number
  tomorrowPrep: PrepScheduleTask[]
}

function localDateKey(value: Date): string {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function timestamp(value: string | null): number | null {
  if (!value) return null
  const parsed = new Date(value).getTime()
  return Number.isNaN(parsed) ? null : parsed
}

export function buildDailySummary(
  cycle: MealCycle,
  prepTasks: PrepScheduleTask[],
  validationAlerts: DashboardValidationAlert[],
  shoppingShortages: ShoppingItem[],
  useSoon: UseSoonRecommendation[],
  now = new Date(),
): DashboardDailySummary {
  const meals = todaysMealSlots(cycle, now)
  const prep = todaysPrepTasks(prepTasks, now)
  const upcoming = meals
    .map((slot) => ({ slot, time: timestamp(slot.scheduled_datetime) }))
    .filter((row) => row.time !== null && row.time >= now.getTime())
    .sort((a, b) => (a.time as number) - (b.time as number))
  const next = upcoming[0]?.slot ?? meals[0] ?? null

  return {
    mealCount: meals.length,
    prepCount: prep.length,
    validationCount: validationAlerts.length,
    shoppingCount: shoppingShortages.length,
    useSoonCount: useSoon.length,
    nextMealName: next?.planned_meal?.snapshot_name ?? null,
    nextMealTime: next?.serving_time ?? null,
    topValidation: validationAlerts[0] ?? null,
    topShopping: shoppingShortages[0] ?? null,
    mostUrgentUseSoon: useSoon[0] ?? null,
  }
}

export function buildEveningSummary(
  cycle: MealCycle,
  prepTasks: PrepScheduleTask[],
  now = new Date(),
): DashboardEveningSummary {
  const today = localDateKey(now)
  const tomorrowDate = new Date(now)
  tomorrowDate.setDate(tomorrowDate.getDate() + 1)
  const tomorrow = localDateKey(tomorrowDate)

  const remainingMealCount = cycle.slots.filter((slot) => {
    if (!slot.planned_meal || slot.scheduled_date !== today) return false
    const time = timestamp(slot.scheduled_datetime)
    return time === null || time >= now.getTime()
  }).length

  const remainingPrepCount = prepTasks.filter((task) => {
    if (!task.start_datetime || task.start_datetime.slice(0, 10) !== today) return false
    const end = timestamp(task.end_datetime) ?? timestamp(task.start_datetime)
    return end === null || end >= now.getTime()
  }).length

  const tomorrowPrep = prepTasks
    .filter((task) => task.start_datetime?.slice(0, 10) === tomorrow)
    .sort((a, b) => (a.start_datetime ?? '').localeCompare(b.start_datetime ?? '') || a.planned_meal_id - b.planned_meal_id || a.advance_prep_id - b.advance_prep_id)

  return { remainingMealCount, remainingPrepCount, tomorrowPrep }
}
