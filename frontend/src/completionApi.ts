export type CompletionSubstitutionSuggestion = {
  ingredient_id: number
  ingredient_name: string
  ratio: string
  preferred: boolean
  notes: string | null
}

export type CompletionUsage = {
  id: number
  component_key: number
  recipe_id: number
  recipe_name: string
  recipe_ingredient_id: number
  planned_ingredient_id: number
  planned_ingredient_name: string
  planned_quantity: string
  planned_unit_id: number
  planned_unit_code: string
  actual_ingredient_id: number
  actual_ingredient_name: string
  actual_quantity: string
  actual_unit_id: number
  actual_unit_code: string
  preparation: string | null
  prep_method: string | null
  prep_size: string | null
  prep_state: string | null
  notes: string | null
  substitutions: CompletionSubstitutionSuggestion[]
}

export type MealCompletion = {
  id: number
  planned_meal_id: number
  status: 'DRAFT' | 'FINALIZED'
  meal_name: string
  snapshot_planned_servings: string
  snapshot_planned_leftover_servings: string
  stale: boolean
  usages: CompletionUsage[]
}

export type CompletionUsageUpdate = {
  usage_id: number
  actual_ingredient_id: number
  actual_quantity: string
  actual_unit_id: number
  notes: string | null
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(body?.detail ?? `Request failed: ${response.status}`)
  }
  return response.json() as Promise<T>
}

export const startCompletion = (plannedMealId: number): Promise<MealCompletion> => request(`/api/planned-meals/${plannedMealId}/completion`, { method: 'POST' })
export const fetchCompletion = (plannedMealId: number): Promise<MealCompletion> => request(`/api/planned-meals/${plannedMealId}/completion`)
export const saveCompletion = (plannedMealId: number, usages: CompletionUsageUpdate[]): Promise<MealCompletion> => request(`/api/planned-meals/${plannedMealId}/completion`, { method: 'PUT', body: JSON.stringify({ usages }) })
export const refreshCompletion = (plannedMealId: number): Promise<MealCompletion> => request(`/api/planned-meals/${plannedMealId}/completion/refresh`, { method: 'POST' })
