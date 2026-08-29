export type HealthResponse = {
  status: string
}

export type Household = {
  id: number
  name: string
  default_servings: string
}

export type MeasurementUnit = {
  id: number
  code: string
  name: string
  unit_family: string
  base_multiplier: string
  allows_fraction: boolean
}

export type ShoppingCategory = {
  id: number
  household_id: number
  name: string
  sort_order: number
  active: boolean
}

export type InventoryLocation = {
  id: number
  household_id: number
  parent_location_id: number | null
  name: string
  location_type: string
  sort_order: number
  active: boolean
}

export type IngredientAlias = {
  id: number
  alias: string
}

export type Ingredient = {
  id: number
  household_id: number
  name: string
  shopping_category_id: number | null
  preferred_unit_id: number | null
  default_location_id: number | null
  perishable: boolean
  active: boolean
  notes: string | null
  aliases: IngredientAlias[]
}

export type IngredientInput = {
  name: string
  shopping_category_id: number | null
  preferred_unit_id: number | null
  default_location_id: number | null
  perishable: boolean
  notes: string | null
  aliases: string[]
  active?: boolean
}

export type Tag = {
  id: number
  household_id: number
  name: string
  category: string
  active: boolean
}

export type RecipeIngredientInput = {
  ingredient_id: number
  quantity: string
  unit_id: number
  display_text: string | null
  preparation: string | null
  optional: boolean
  scaling_mode: 'LINEAR' | 'FIXED' | 'ROUND_UP' | 'MANUAL'
  required_state: string
  sort_order: number
  notes: string | null
}

export type RecipeIngredient = RecipeIngredientInput & {
  id: number
  recipe_id: number
}

export type RecipeInput = {
  name: string
  description: string | null
  base_servings: string
  serving_unit: string
  yield_quantity: string | null
  yield_unit_id: number | null
  prep_time_minutes: number | null
  cook_time_minutes: number | null
  notes: string | null
  favorite: boolean
  meal_types: string[]
  tag_ids: number[]
  ingredients: RecipeIngredientInput[]
  active?: boolean
}

export type Recipe = {
  id: number
  household_id: number
  name: string
  description: string | null
  base_servings: string
  serving_unit: string
  yield_quantity: string | null
  yield_unit_id: number | null
  prep_time_minutes: number | null
  cook_time_minutes: number | null
  notes: string | null
  favorite: boolean
  active: boolean
  meal_types: string[]
  tags: Tag[]
  ingredients: RecipeIngredient[]
}

export type ScaledRecipeIngredient = {
  recipe_ingredient_id: number
  ingredient_id: number
  quantity: string
  unit_id: number
  unit_code: string
  scaling_mode: string
  manual_review: boolean
}

export type RecipeScaleResponse = {
  recipe_id: number
  base_servings: string
  requested_servings: string
  scale_factor: string
  ingredients: ScaledRecipeIngredient[]
}

async function jsonRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(body?.detail ?? `Request failed: ${response.status}`)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return response.json() as Promise<T>
}

export async function fetchHealth(): Promise<HealthResponse> {
  return jsonRequest<HealthResponse>('/health')
}

export function fetchHousehold(): Promise<Household> {
  return jsonRequest<Household>('/api/reference/household')
}

export function updateHousehold(input: { name: string; default_servings: string }): Promise<Household> {
  return jsonRequest<Household>('/api/reference/household', {
    method: 'PUT',
    body: JSON.stringify(input),
  })
}

export function fetchMeasurementUnits(): Promise<MeasurementUnit[]> {
  return jsonRequest<MeasurementUnit[]>('/api/reference/units')
}

export function fetchShoppingCategories(): Promise<ShoppingCategory[]> {
  return jsonRequest<ShoppingCategory[]>('/api/reference/shopping-categories')
}

export function createShoppingCategory(input: { name: string; sort_order: number }): Promise<ShoppingCategory> {
  return jsonRequest<ShoppingCategory>('/api/reference/shopping-categories', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function updateShoppingCategory(category: ShoppingCategory): Promise<ShoppingCategory> {
  return jsonRequest<ShoppingCategory>(`/api/reference/shopping-categories/${category.id}`, {
    method: 'PUT',
    body: JSON.stringify({
      name: category.name,
      sort_order: category.sort_order,
      active: category.active,
    }),
  })
}

export function archiveShoppingCategory(id: number): Promise<void> {
  return jsonRequest<void>(`/api/reference/shopping-categories/${id}`, { method: 'DELETE' })
}

export function fetchInventoryLocations(): Promise<InventoryLocation[]> {
  return jsonRequest<InventoryLocation[]>('/api/reference/inventory-locations')
}

export function createInventoryLocation(input: {
  name: string
  parent_location_id: number | null
  location_type: string
  sort_order: number
}): Promise<InventoryLocation> {
  return jsonRequest<InventoryLocation>('/api/reference/inventory-locations', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function updateInventoryLocation(location: InventoryLocation): Promise<InventoryLocation> {
  return jsonRequest<InventoryLocation>(`/api/reference/inventory-locations/${location.id}`, {
    method: 'PUT',
    body: JSON.stringify({
      name: location.name,
      parent_location_id: location.parent_location_id,
      location_type: location.location_type,
      sort_order: location.sort_order,
      active: location.active,
    }),
  })
}

export function archiveInventoryLocation(id: number): Promise<void> {
  return jsonRequest<void>(`/api/reference/inventory-locations/${id}`, { method: 'DELETE' })
}

export function fetchIngredients(search = '', includeInactive = false): Promise<Ingredient[]> {
  const params = new URLSearchParams()
  if (search.trim()) params.set('search', search.trim())
  if (includeInactive) params.set('include_inactive', 'true')
  const query = params.toString()
  return jsonRequest<Ingredient[]>(`/api/ingredients${query ? `?${query}` : ''}`)
}

export function createIngredient(input: IngredientInput): Promise<Ingredient> {
  return jsonRequest<Ingredient>('/api/ingredients', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function updateIngredient(ingredient: Ingredient, input: IngredientInput): Promise<Ingredient> {
  return jsonRequest<Ingredient>(`/api/ingredients/${ingredient.id}`, {
    method: 'PUT',
    body: JSON.stringify({ ...input, active: input.active ?? ingredient.active }),
  })
}

export function archiveIngredient(id: number): Promise<void> {
  return jsonRequest<void>(`/api/ingredients/${id}`, { method: 'DELETE' })
}

export function fetchTags(includeInactive = false): Promise<Tag[]> {
  return jsonRequest<Tag[]>(`/api/tags${includeInactive ? '?include_inactive=true' : ''}`)
}

export function createTag(input: { name: string; category: string }): Promise<Tag> {
  return jsonRequest<Tag>('/api/tags', { method: 'POST', body: JSON.stringify(input) })
}

export function updateTag(tag: Tag): Promise<Tag> {
  return jsonRequest<Tag>(`/api/tags/${tag.id}`, {
    method: 'PUT',
    body: JSON.stringify({ name: tag.name, category: tag.category, active: tag.active }),
  })
}

export function archiveTag(id: number): Promise<void> {
  return jsonRequest<void>(`/api/tags/${id}`, { method: 'DELETE' })
}

export function fetchRecipes(filters?: {
  search?: string
  meal_type?: string
  tag_id?: number
  favorite?: boolean
  include_inactive?: boolean
}): Promise<Recipe[]> {
  const params = new URLSearchParams()
  if (filters?.search?.trim()) params.set('search', filters.search.trim())
  if (filters?.meal_type) params.set('meal_type', filters.meal_type)
  if (filters?.tag_id) params.set('tag_id', String(filters.tag_id))
  if (filters?.favorite !== undefined) params.set('favorite', String(filters.favorite))
  if (filters?.include_inactive) params.set('include_inactive', 'true')
  const query = params.toString()
  return jsonRequest<Recipe[]>(`/api/recipes${query ? `?${query}` : ''}`)
}

export function fetchRecipe(id: number): Promise<Recipe> {
  return jsonRequest<Recipe>(`/api/recipes/${id}`)
}

export function createRecipe(input: RecipeInput): Promise<Recipe> {
  return jsonRequest<Recipe>('/api/recipes', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function updateRecipe(recipe: Recipe, input: RecipeInput): Promise<Recipe> {
  return jsonRequest<Recipe>(`/api/recipes/${recipe.id}`, {
    method: 'PUT',
    body: JSON.stringify({ ...input, active: input.active ?? recipe.active }),
  })
}

export function archiveRecipe(id: number): Promise<void> {
  return jsonRequest<void>(`/api/recipes/${id}`, { method: 'DELETE' })
}

export function scaleRecipe(
  id: number,
  requestedServings: string,
  unitOverrides: Record<number, string> = {},
): Promise<RecipeScaleResponse> {
  return jsonRequest<RecipeScaleResponse>(`/api/recipes/${id}/scale`, {
    method: 'POST',
    body: JSON.stringify({ requested_servings: requestedServings, unit_overrides: unitOverrides }),
  })
}
