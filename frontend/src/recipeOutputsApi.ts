export type RecipeOutput = {
  id: number
  recipe_id: number
  name: string
  quantity: string
  unit_id: number
  notes: string | null
  active: boolean
  sort_order: number
}

export type RecipeOutputInput = Omit<RecipeOutput, 'id' | 'recipe_id'>

export type RecipeDependency = {
  id: number
  recipe_id: number
  recipe_output_id: number
  quantity: string
  unit_id: number
  scaling_mode: 'LINEAR' | 'FIXED' | 'ROUND_UP' | 'MANUAL'
  notes: string | null
  sort_order: number
}

export type RecipeDependencyInput = Omit<RecipeDependency, 'id' | 'recipe_id'>
export type RecipeOutputBundle = { outputs: RecipeOutput[]; dependencies: RecipeDependency[] }
export type ScaledDependency = { dependency_id: number; recipe_output_id: number; source_recipe_id: number; output_name: string; quantity: string; unit_id: number; unit_code: string; scaling_mode: string; manual_review: boolean }
export type DependencyScaleResponse = { recipe_id: number; requested_servings: string; dependencies: ScaledDependency[] }

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(body?.detail ?? `Request failed: ${response.status}`)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const fetchRecipeOutputs = (recipeId: number): Promise<RecipeOutputBundle> => request(`/api/recipes/${recipeId}/outputs-dependencies`)
export const fetchAvailableOutputs = (recipeId: number): Promise<RecipeOutput[]> => request(`/api/recipes/outputs/available?exclude_recipe_id=${recipeId}`)
export const createRecipeOutput = (recipeId: number, input: RecipeOutputInput): Promise<RecipeOutput> => request(`/api/recipes/${recipeId}/outputs`, { method: 'POST', body: JSON.stringify(input) })
export const updateRecipeOutput = (recipeId: number, outputId: number, input: RecipeOutputInput): Promise<RecipeOutput> => request(`/api/recipes/${recipeId}/outputs/${outputId}`, { method: 'PUT', body: JSON.stringify(input) })
export const archiveRecipeOutput = (recipeId: number, outputId: number): Promise<void> => request(`/api/recipes/${recipeId}/outputs/${outputId}`, { method: 'DELETE' })
export const createRecipeDependency = (recipeId: number, input: RecipeDependencyInput): Promise<RecipeDependency> => request(`/api/recipes/${recipeId}/dependencies`, { method: 'POST', body: JSON.stringify(input) })
export const updateRecipeDependency = (recipeId: number, dependencyId: number, input: RecipeDependencyInput): Promise<RecipeDependency> => request(`/api/recipes/${recipeId}/dependencies/${dependencyId}`, { method: 'PUT', body: JSON.stringify(input) })
export const deleteRecipeDependency = (recipeId: number, dependencyId: number): Promise<void> => request(`/api/recipes/${recipeId}/dependencies/${dependencyId}`, { method: 'DELETE' })
export const scaleRecipeDependencies = (recipeId: number, requestedServings: string): Promise<DependencyScaleResponse> => request(`/api/recipes/${recipeId}/dependencies/scale`, { method: 'POST', body: JSON.stringify({ requested_servings: requestedServings }) })
