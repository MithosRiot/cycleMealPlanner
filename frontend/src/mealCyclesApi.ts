export type MealSlotDefinitionInput = {
  label: string
  sort_order: number
}

export type MealSlotDefinition = MealSlotDefinitionInput & {
  id: number
  cycle_id: number
}

export type SlotPopulationRule = {
  include_meal_ids: number[]
  exclude_meal_ids: number[]
}

export type PopulationRules = {
  include_meal_ids: number[]
  exclude_meal_ids: number[]
  slot_rules: Record<string, SlotPopulationRule>
}

export type SmartPlanningPreferences = {
  repeat_spacing_days: number
  favorite_boost: number
  history_penalty: number
  tag_weights: Record<number, number>
}

export type ScaledPlannedComponent = {
  meal_recipe_id: number
  recipe_id: number
  base_servings: string
  requested_servings: string
  scale_factor: string
  ingredients: Array<{
    recipe_ingredient_id: number
    ingredient_id: number
    quantity: string
    unit_id: number
    scaling_mode: string
    manual_review: boolean
  }>
}

export type PlannedMeal = {
  id: number
  cycle_slot_id: number
  meal_id: number
  locked: boolean
  planned_servings: string
  planned_leftover_servings: string
  component_serving_overrides: string
  scaled_components: string
  snapshot_name: string
  snapshot_description: string | null
  snapshot_meal_types: string
  snapshot_components: string
}

export type CycleSlot = {
  id: number
  cycle_id: number
  slot_definition_id: number
  day_number: number
  sort_order: number
  planned_meal: PlannedMeal | null
}

export type MealCycleInput = {
  name: string
  duration_days: number
  start_date: string | null
  notes: string | null
  slot_definitions: MealSlotDefinitionInput[]
}

export type MealCycle = {
  id: number
  household_id: number
  name: string
  duration_days: number
  status: 'DRAFT'
  start_date: string | null
  notes: string | null
  population_rules: string
  smart_preferences: string
  slot_definitions: MealSlotDefinition[]
  slots: CycleSlot[]
}

async function jsonRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(body?.detail ?? `Request failed: ${response.status}`)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const fetchMealCycles = (): Promise<MealCycle[]> => jsonRequest('/api/meal-cycles')
export const fetchMealCycle = (id: number): Promise<MealCycle> => jsonRequest(`/api/meal-cycles/${id}`)
export const createMealCycle = (input: MealCycleInput): Promise<MealCycle> => jsonRequest('/api/meal-cycles', { method: 'POST', body: JSON.stringify(input) })
export const updateMealCycle = (id: number, input: MealCycleInput): Promise<MealCycle> => jsonRequest(`/api/meal-cycles/${id}`, { method: 'PUT', body: JSON.stringify(input) })
export const updatePopulationRules = (id: number, input: PopulationRules): Promise<MealCycle> => jsonRequest(`/api/meal-cycles/${id}/population-rules`, { method: 'PUT', body: JSON.stringify(input) })
export const updateSmartPlanningPreferences = (id: number, input: SmartPlanningPreferences): Promise<MealCycle> => jsonRequest(`/api/meal-cycles/${id}/smart-preferences`, { method: 'PUT', body: JSON.stringify(input) })
export const deleteMealCycle = (id: number): Promise<void> => jsonRequest(`/api/meal-cycles/${id}`, { method: 'DELETE' })
export const assignPlannedMeal = (cycleId: number, slotId: number, mealId: number): Promise<PlannedMeal> => jsonRequest(`/api/meal-cycles/${cycleId}/slots/${slotId}/planned-meal`, { method: 'POST', body: JSON.stringify({ meal_id: mealId }) })
export const updatePlannedMealPlanning = (cycleId: number, slotId: number, input: { planned_servings: string; planned_leftover_servings: string; component_serving_overrides: Record<number, string> }): Promise<PlannedMeal> => jsonRequest(`/api/meal-cycles/${cycleId}/slots/${slotId}/planned-meal/planning`, { method: 'PUT', body: JSON.stringify(input) })
export const removePlannedMeal = (cycleId: number, slotId: number): Promise<void> => jsonRequest(`/api/meal-cycles/${cycleId}/slots/${slotId}/planned-meal`, { method: 'DELETE' })
export const setPlannedMealLock = (cycleId: number, slotId: number, locked: boolean): Promise<PlannedMeal> => jsonRequest(`/api/meal-cycles/${cycleId}/slots/${slotId}/planned-meal/lock`, { method: 'PUT', body: JSON.stringify({ locked }) })
export const movePlannedMeal = (cycleId: number, slotId: number, targetSlotId: number): Promise<PlannedMeal> => jsonRequest(`/api/meal-cycles/${cycleId}/slots/${slotId}/planned-meal/move`, { method: 'POST', body: JSON.stringify({ target_cycle_slot_id: targetSlotId }) })
export const randomFillMealCycle = (cycleId: number): Promise<{ filled_count: number }> => jsonRequest(`/api/meal-cycles/${cycleId}/random-fill`, { method: 'POST' })
