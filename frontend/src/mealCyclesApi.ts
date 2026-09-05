export type MealSlotDefinitionInput = { label: string; sort_order: number; serving_time?: string | null }
export type MealSlotDefinition = MealSlotDefinitionInput & { id: number; cycle_id: number }
export type SlotPopulationRule = { include_meal_ids: number[]; exclude_meal_ids: number[] }
export type PopulationRules = { include_meal_ids: number[]; exclude_meal_ids: number[]; slot_rules: Record<string, SlotPopulationRule> }
export type SmartPlanningPreferences = { repeat_spacing_days: number; favorite_boost: number; history_penalty: number; tag_weights: Record<number, number> }
export type ExpiringMatch = { ingredient_id: number; ingredient_name: string; inventory_lot_id: number; expiration_date: string; days_until_expiration_on_planned_date: number; usable_quantity: string; unit_id: number; unit_code: string }
export type ExpirationSuggestion = { planned_meal_id: number; cycle_slot_id: number; meal_id: number | null; meal_name: string; day_number: number; planned_date: string; urgency_days: number; expiring_matches: ExpiringMatch[]; suggested_empty_day_numbers: number[]; suggested_swap_day_numbers: number[]; can_move_earlier: boolean; can_swap_earlier: boolean }
export type ExpirationSuggestionsResponse = { meal_cycle_id: number; meal_cycle_name: string; start_date: string; suggestions: ExpirationSuggestion[] }
export type CycleValidationIssue = { severity: 'ERROR' | 'WARNING'; code: string; message: string; context: Record<string, unknown> }
export type CycleValidationResponse = { meal_cycle_id: number; meal_cycle_name: string; valid: boolean; error_count: number; warning_count: number; issues: CycleValidationIssue[] }
export type ScaledPlannedComponent = { meal_recipe_id: number; recipe_id: number; base_servings: string; requested_servings: string; scale_factor: string; ingredients: Array<{ recipe_ingredient_id: number; ingredient_id: number; quantity: string; unit_id: number; scaling_mode: string; manual_review: boolean }> }
export type PlannedMealSourceType = 'SAVED_MEAL' | 'DIRECT_RECIPE' | 'LEFTOVER' | 'RECIPE_OUTPUT'
export type PlannedMeal = {
  id: number; cycle_slot_id: number; meal_id: number | null; source_type: PlannedMealSourceType; source_recipe_id: number | null;
  source_origin_planned_meal_id: number | null; source_record_id: number | null; source_recipe_output_id: number | null; source_quantity: string | null; source_unit_id: number | null;
  locked: boolean; planned_servings: string; planned_leftover_servings: string; component_serving_overrides: string; scaled_components: string;
  snapshot_name: string; snapshot_description: string | null; snapshot_meal_types: string; snapshot_components: string; scheduled_date: string | null; serving_time: string | null; scheduled_datetime: string | null
}
export type ProducedSourceOption = { source_type: 'LEFTOVER' | 'RECIPE_OUTPUT'; source_origin_planned_meal_id: number; source_record_id: number | null; source_recipe_output_id: number | null; source_name: string; source_meal_id: number | null; unit_id: number; unit_code: string; planned_quantity: string; physical_quantity: string; reserved_quantity: string; available_quantity: string; lot_id: number | null; expiration_date: string | null }
export type CycleSlot = { id: number; cycle_id: number; slot_definition_id: number; day_number: number; sort_order: number; scheduled_date: string | null; serving_time: string | null; scheduled_datetime: string | null; planned_meal: PlannedMeal | null }
export type MealCycleInput = { name: string; duration_days: number; start_date: string | null; notes: string | null; slot_definitions: MealSlotDefinitionInput[] }
export type MealCycleStatus = 'DRAFT' | 'ACTIVE' | 'COMPLETED' | 'CANCELLED'
export type MealCycle = { id: number; household_id: number; name: string; duration_days: number; status: MealCycleStatus; start_date: string | null; notes: string | null; population_rules: string; smart_preferences: string; activated_at: string | null; completed_at: string | null; cancelled_at: string | null; slot_definitions: MealSlotDefinition[]; slots: CycleSlot[] }
export type MealCycleScheduleUpdate = { start_date: string | null; serving_times: Record<number, string | null> }

async function jsonRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: unknown } | null
    const detail = body?.detail
    const message = typeof detail === 'string' ? detail : detail && typeof detail === 'object' && 'message' in detail && typeof detail.message === 'string' ? detail.message : `Request failed: ${response.status}`
    throw new Error(message)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const fetchMealCycles = (): Promise<MealCycle[]> => jsonRequest('/api/meal-cycles')
export const fetchMealCycle = (id: number): Promise<MealCycle> => jsonRequest(`/api/meal-cycles/${id}`)
export const fetchExpirationSuggestions = (id: number): Promise<ExpirationSuggestionsResponse> => jsonRequest(`/api/meal-cycles/${id}/expiration-suggestions`)
export const fetchCycleValidation = (id: number): Promise<CycleValidationResponse> => jsonRequest(`/api/meal-cycles/${id}/validate`)
export const fetchProducedSourceOptions = (): Promise<ProducedSourceOption[]> => jsonRequest('/api/produced-source-options')
export const createMealCycle = (input: MealCycleInput): Promise<MealCycle> => jsonRequest('/api/meal-cycles', { method: 'POST', body: JSON.stringify(input) })
export const updateMealCycle = (id: number, input: MealCycleInput): Promise<MealCycle> => jsonRequest(`/api/meal-cycles/${id}`, { method: 'PUT', body: JSON.stringify(input) })
export const updateMealCycleSchedule = (id: number, input: MealCycleScheduleUpdate): Promise<MealCycle> => jsonRequest(`/api/meal-cycles/${id}/schedule`, { method: 'PUT', body: JSON.stringify(input) })
export const updatePopulationRules = (id: number, input: PopulationRules): Promise<MealCycle> => jsonRequest(`/api/meal-cycles/${id}/population-rules`, { method: 'PUT', body: JSON.stringify(input) })
export const updateSmartPlanningPreferences = (id: number, input: SmartPlanningPreferences): Promise<MealCycle> => jsonRequest(`/api/meal-cycles/${id}/smart-preferences`, { method: 'PUT', body: JSON.stringify(input) })
export const activateMealCycle = (id: number): Promise<MealCycle> => jsonRequest(`/api/meal-cycles/${id}/activate`, { method: 'POST' })
export const completeMealCycle = (id: number): Promise<MealCycle> => jsonRequest(`/api/meal-cycles/${id}/complete`, { method: 'POST' })
export const cancelMealCycle = (id: number): Promise<MealCycle> => jsonRequest(`/api/meal-cycles/${id}/cancel`, { method: 'POST' })
export const deleteMealCycle = (id: number): Promise<void> => jsonRequest(`/api/meal-cycles/${id}`, { method: 'DELETE' })
export const assignPlannedMeal = (cycleId: number, slotId: number, mealId: number): Promise<PlannedMeal> => jsonRequest(`/api/meal-cycles/${cycleId}/slots/${slotId}/planned-meal`, { method: 'POST', body: JSON.stringify({ meal_id: mealId }) })
export const assignDirectRecipe = (cycleId: number, slotId: number, recipeId: number, plannedServings: string, plannedLeftoverServings = '0'): Promise<PlannedMeal> => jsonRequest(`/api/meal-cycles/${cycleId}/slots/${slotId}/planned-recipe`, { method: 'POST', body: JSON.stringify({ recipe_id: recipeId, planned_servings: plannedServings, planned_leftover_servings: plannedLeftoverServings }) })
export const assignProducedSource = (cycleId: number, slotId: number, source: ProducedSourceOption, quantity: string): Promise<PlannedMeal> => jsonRequest(`/api/meal-cycles/${cycleId}/slots/${slotId}/planned-source`, { method: 'POST', body: JSON.stringify({ source_type: source.source_type, source_origin_planned_meal_id: source.source_origin_planned_meal_id, source_record_id: source.source_record_id, source_recipe_output_id: source.source_recipe_output_id, quantity, unit_id: source.unit_id }) })
export const updatePlannedMealPlanning = (cycleId: number, slotId: number, input: { planned_servings: string; planned_leftover_servings: string; component_serving_overrides: Record<number, string> }): Promise<PlannedMeal> => jsonRequest(`/api/meal-cycles/${cycleId}/slots/${slotId}/planned-meal/planning`, { method: 'PUT', body: JSON.stringify(input) })
export const removePlannedMeal = (cycleId: number, slotId: number): Promise<void> => jsonRequest(`/api/meal-cycles/${cycleId}/slots/${slotId}/planned-meal`, { method: 'DELETE' })
export const setPlannedMealLock = (cycleId: number, slotId: number, locked: boolean): Promise<PlannedMeal> => jsonRequest(`/api/meal-cycles/${cycleId}/slots/${slotId}/planned-meal/lock`, { method: 'PUT', body: JSON.stringify({ locked }) })
export const movePlannedMeal = (cycleId: number, slotId: number, targetSlotId: number): Promise<PlannedMeal> => jsonRequest(`/api/meal-cycles/${cycleId}/slots/${slotId}/planned-meal/move`, { method: 'POST', body: JSON.stringify({ target_cycle_slot_id: targetSlotId }) })
export const randomFillMealCycle = (cycleId: number): Promise<{ filled_count: number }> => jsonRequest(`/api/meal-cycles/${cycleId}/random-fill`, { method: 'POST' })
