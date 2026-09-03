export type CookingStepInput = { title: string; instructions: string | null; prep_group_id: number | null; sort_order: number }
export type CookingStep = CookingStepInput & { id: number; recipe_id: number; prep_group_name: string | null }
export type CookingIngredient = { ingredient_id: number; ingredient_name: string; quantity: string; unit_id: number; unit_code: string; preparation: string | null; prep_method: string | null; prep_size: string | null; prep_state: string | null }
export type CookingModeStep = { step_id: number; component_index: number; meal_recipe_id: number; recipe_id: number; recipe_name: string; title: string; instructions: string | null; prep_group_id: number | null; prep_group_name: string | null; step_number: number; total_steps: number; ingredients: CookingIngredient[] }
export type CookingModeMeal = { planned_meal_id: number; day_number: number; slot_label: string; meal_name: string; planned_servings: string; planned_leftover_servings: string; steps: CookingModeStep[]; components_without_steps: string[] }
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
