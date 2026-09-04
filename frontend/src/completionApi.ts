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
  actual_servings_produced: string | null
  actual_servings_eaten: string | null
  production_committed_at: string | null
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

export type CompletionOutputPreview = {
  component_key: number
  recipe_id: number
  recipe_name: string
  recipe_output_id: number
  output_name: string
  recipe_base_servings: string
  planned_component_servings: string
  base_quantity: string
  calculated_quantity: string
  unit_id: number
  unit_code: string
}

export type CompletionProductionPreview = {
  planned_servings: string
  planned_leftover_servings: string
  default_actual_servings_produced: string
  default_actual_servings_eaten: string
  default_leftover_servings: string
  outputs: CompletionOutputPreview[]
}

export type CompletionOutputCommitInput = {
  recipe_output_id: number
  component_key: number
  actual_quantity: string
  location_id: number | null
  expiration_date: string | null
  notes: string | null
}

export type CompletionProductionCommitInput = {
  actual_servings_produced: string
  actual_servings_eaten: string
  leftover_location_id: number | null
  leftover_expiration_date: string | null
  leftover_notes: string | null
  outputs: CompletionOutputCommitInput[]
}

export type Leftover = {
  id: number
  completion_id: number
  planned_meal_id: number
  source_meal_id: number
  source_meal_name: string
  actual_servings_produced: string
  actual_servings_eaten: string
  leftover_servings: string
  serving_unit: string
  location_id: number | null
  expiration_date: string | null
  notes: string | null
  status: 'NONE' | 'AVAILABLE'
  inventory_lot_id: number | null
  inventory_transaction_id: number | null
  created_at: string
}

export type CompletionOutput = {
  id: number
  completion_id: number
  component_key: number
  recipe_id: number
  recipe_name: string
  recipe_output_id: number
  output_name: string
  recipe_base_servings: string
  planned_component_servings: string
  base_quantity: string
  calculated_quantity: string
  actual_quantity: string
  quantity_overridden: boolean
  unit_id: number
  unit_code: string
  location_id: number | null
  expiration_date: string | null
  notes: string | null
  inventory_lot_id: number | null
  inventory_transaction_id: number | null
  created_at: string
}

export type CompletionProduction = {
  completion: MealCompletion
  leftover: Leftover
  outputs: CompletionOutput[]
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string | { message?: string; shortages?: CompletionShortage[] } } | null
    const detail = body?.detail
    if (detail && typeof detail === 'object') {
      const shortageText = detail.shortages?.map((row) => `${row.ingredient_name}: short ${row.shortage_quantity} ${row.unit_code}`).join('; ')
      throw new Error([detail.message, shortageText].filter(Boolean).join(' — ') || `Request failed: ${response.status}`)
    }
    throw new Error(typeof detail === 'string' ? detail : `Request failed: ${response.status}`)
  }
  return response.json() as Promise<T>
}

export const startCompletion = (plannedMealId: number): Promise<MealCompletion> => request(`/api/planned-meals/${plannedMealId}/completion`, { method: 'POST' })
export const fetchCompletion = (plannedMealId: number): Promise<MealCompletion> => request(`/api/planned-meals/${plannedMealId}/completion`)
export const saveCompletion = (plannedMealId: number, usages: CompletionUsageUpdate[]): Promise<MealCompletion> => request(`/api/planned-meals/${plannedMealId}/completion`, { method: 'PUT', body: JSON.stringify({ usages }) })
export const refreshCompletion = (plannedMealId: number): Promise<MealCompletion> => request(`/api/planned-meals/${plannedMealId}/completion/refresh`, { method: 'POST' })
export const finalizeCompletion = (plannedMealId: number): Promise<CompletionFinalizeResponse> => request(`/api/planned-meals/${plannedMealId}/completion/finalize`, { method: 'POST' })
export const fetchProductionPreview = (plannedMealId: number, produced?: string): Promise<CompletionProductionPreview> => request(`/api/planned-meals/${plannedMealId}/completion/production-preview${produced !== undefined ? `?actual_servings_produced=${encodeURIComponent(produced)}` : ''}`)
export const fetchCompletionProduction = (plannedMealId: number): Promise<CompletionProduction> => request(`/api/planned-meals/${plannedMealId}/completion/production`)
export const commitCompletionProduction = (plannedMealId: number, input: CompletionProductionCommitInput): Promise<CompletionProduction> => request(`/api/planned-meals/${plannedMealId}/completion/production`, { method: 'POST', body: JSON.stringify(input) })
