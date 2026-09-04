export type CompletionSubstitutionSuggestion = {
  ingredient_id: number
  ingredient_name: string
  ratio: string
  preferred: boolean
  notes: string | null
}

export type CompletionAllocation = {
  id: number
  usage_id: number
  lot_id: number
  inventory_transaction_id: number
  quantity: string
  unit_id: number
  unit_code: string
  source_quantity: string
  source_unit_id: number
  source_unit_code: string
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
  allocations: CompletionAllocation[]
}

export type MealCompletion = {
  id: number
  planned_meal_id: number
  status: 'DRAFT' | 'FINALIZED'
  meal_name: string
  snapshot_planned_servings: string
  snapshot_planned_leftover_servings: string
  stale: boolean
  finalized_at: string | null
  usages: CompletionUsage[]
}

export type CompletionUsageUpdate = {
  usage_id: number
  actual_ingredient_id: number
  actual_quantity: string
  actual_unit_id: number
  notes: string | null
}

export type CompletionShortage = {
  usage_id: number
  ingredient_id: number
  ingredient_name: string
  requested_quantity: string
  unit_id: number
  unit_code: string
  shortage_quantity: string
}

export type CompletionFinalizeResponse = {
  completion: MealCompletion | null
  shortages: CompletionShortage[]
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string | { message?: string; shortages?: CompletionShortage[] } } | null
    if (body?.detail && typeof body.detail === 'object') {
      const shortageText = body.detail.shortages?.map((row) => `${row.ingredient_name}: short ${row.shortage_quantity} ${row.unit_code}`).join('; ')
      throw new Error([body.detail.message, shortageText].filter(Boolean).join(' — ') || `Request failed: ${response.status}`)
    }
    throw new Error(body?.detail ?? `Request failed: ${response.status}`)
  }
  return response.json() as Promise<T>
}

export const startCompletion = (plannedMealId: number): Promise<MealCompletion> => request(`/api/planned-meals/${plannedMealId}/completion`, { method: 'POST' })
export const fetchCompletion = (plannedMealId: number): Promise<MealCompletion> => request(`/api/planned-meals/${plannedMealId}/completion`)
export const saveCompletion = (plannedMealId: number, usages: CompletionUsageUpdate[]): Promise<MealCompletion> => request(`/api/planned-meals/${plannedMealId}/completion`, { method: 'PUT', body: JSON.stringify({ usages }) })
export const refreshCompletion = (plannedMealId: number): Promise<MealCompletion> => request(`/api/planned-meals/${plannedMealId}/completion/refresh`, { method: 'POST' })
export const finalizeCompletion = (plannedMealId: number): Promise<CompletionFinalizeResponse> => request(`/api/planned-meals/${plannedMealId}/completion/finalize`, { method: 'POST' })
