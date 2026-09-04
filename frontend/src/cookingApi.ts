export type CookingTimerInput = { label: string; duration_seconds: number; notes: string | null; sort_order: number }
export type CookingTimer = CookingTimerInput & { id: number; cooking_step_id: number }
export type CookingTemperatureInput = { label: string; value: string; unit: 'F' | 'C'; notes: string | null; sort_order: number }
export type CookingTemperature = CookingTemperatureInput & { id: number; cooking_step_id: number }
export type CookingEquipmentContext = { recipe_equipment_id: number; equipment_id: number; equipment_name: string; quantity: number; notes: string | null; sort_order: number }
export type CookingStepInput = { title: string; instructions: string | null; prep_group_id: number | null; sort_order: number; timers: CookingTimerInput[]; recipe_equipment_ids: number[]; temperatures: CookingTemperatureInput[]; coordination_stage: number; parallel_capable: boolean; depends_on_step_orders: number[] }
export type CookingStep = Omit<CookingStepInput, 'timers' | 'recipe_equipment_ids' | 'temperatures'> & { id: number; recipe_id: number; prep_group_name: string | null; timers: CookingTimer[]; equipment: CookingEquipmentContext[]; temperatures: CookingTemperature[] }
export type CookingIngredient = { ingredient_id: number; ingredient_name: string; quantity: string; unit_id: number; unit_code: string; preparation: string | null; prep_method: string | null; prep_size: string | null; prep_state: string | null }
export type CookingTimerRuntime = { timer_id: number; label: string; duration_seconds: number; notes: string | null; sort_order: number; status: 'READY' | 'RUNNING' | 'PAUSED' | 'COMPLETED' | 'DISMISSED'; remaining_seconds: number; ends_at_epoch: number | null }
export type CookingModeStep = { step_id: number; component_index: number; meal_recipe_id: number; recipe_id: number; recipe_name: string; title: string; instructions: string | null; prep_group_id: number | null; prep_group_name: string | null; step_number: number; total_steps: number; ingredients: CookingIngredient[]; timers: CookingTimerRuntime[]; equipment: CookingEquipmentContext[]; temperatures: CookingTemperature[]; coordination_stage: number; parallel_capable: boolean; parallel_group: number | null }
export type CookingModeMeal = { planned_meal_id: number; day_number: number; slot_label: string; meal_name: string; planned_servings: string; planned_leftover_servings: string; steps: CookingModeStep[]; components_without_steps: string[]; coordinated: boolean }
export type CycleCookingMode = { cycle_id: number; meals: CookingModeMeal[] }

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(body?.detail ?? `Request failed: ${response.status}`)
  }
  return response.json() as Promise<T>
}

export const fetchCookingSteps = (recipeId: number): Promise<CookingStep[]> => request(`/api/recipes/${recipeId}/cooking-steps`)
export const saveCookingSteps = (recipeId: number, steps: CookingStepInput[]): Promise<CookingStep[]> => request(`/api/recipes/${recipeId}/cooking-steps`, { method: 'PUT', body: JSON.stringify(steps) })
export const fetchCycleCookingMode = (cycleId: number): Promise<CycleCookingMode> => request(`/api/meal-cycles/${cycleId}/cooking-mode`)
export const updateCookingTimer = (plannedMealId: number, timerId: number, action: 'START' | 'PAUSE' | 'RESUME' | 'RESET' | 'DISMISS'): Promise<CookingTimerRuntime> => request(`/api/planned-meals/${plannedMealId}/cooking-timers/${timerId}`, { method: 'POST', body: JSON.stringify({ action }) })
