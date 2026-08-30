export type HealthResponse = { status: string }
export type Household = { id: number; name: string; default_servings: string }
export type MeasurementUnit = { id: number; code: string; name: string; unit_family: string; base_multiplier: string; allows_fraction: boolean }
export type ShoppingCategory = { id: number; household_id: number; name: string; sort_order: number; active: boolean }
export type InventoryLocation = { id: number; household_id: number; parent_location_id: number | null; name: string; location_type: string; sort_order: number; active: boolean }
export type IngredientAlias = { id: number; alias: string }
export type Ingredient = { id: number; household_id: number; name: string; shopping_category_id: number | null; preferred_unit_id: number | null; default_location_id: number | null; perishable: boolean; active: boolean; notes: string | null; aliases: IngredientAlias[] }
export type IngredientInput = { name: string; shopping_category_id: number | null; preferred_unit_id: number | null; default_location_id: number | null; perishable: boolean; notes: string | null; aliases: string[]; active?: boolean }
export type Tag = { id: number; household_id: number; name: string; category: string; active: boolean }
export type RecipePrepGroupInput = { client_key: string; name: string; sort_order: number }
export type RecipePrepGroup = { id: number; recipe_id: number; name: string; sort_order: number }
export type RecipeIngredientInput = { ingredient_id: number; prep_group_key: string | null; quantity: string; unit_id: number; display_text: string | null; preparation: string | null; prep_method: string | null; prep_size: string | null; prep_state: string | null; optional: boolean; scaling_mode: 'LINEAR' | 'FIXED' | 'ROUND_UP' | 'MANUAL'; required_state: string; sort_order: number; notes: string | null }
export type RecipeIngredient = Omit<RecipeIngredientInput, 'prep_group_key'> & { id: number; recipe_id: number; prep_group_id: number | null }
export type RecipeInput = { name: string; description: string | null; base_servings: string; serving_unit: string; yield_quantity: string | null; yield_unit_id: number | null; prep_time_minutes: number | null; cook_time_minutes: number | null; notes: string | null; favorite: boolean; meal_types: string[]; tag_ids: number[]; prep_groups: RecipePrepGroupInput[]; ingredients: RecipeIngredientInput[]; active?: boolean }
export type Recipe = { id: number; household_id: number; name: string; description: string | null; base_servings: string; serving_unit: string; yield_quantity: string | null; yield_unit_id: number | null; prep_time_minutes: number | null; cook_time_minutes: number | null; notes: string | null; favorite: boolean; active: boolean; meal_types: string[]; tags: Tag[]; prep_groups: RecipePrepGroup[]; ingredients: RecipeIngredient[] }
export type ScaledRecipeIngredient = { recipe_ingredient_id: number; ingredient_id: number; prep_group_id: number | null; quantity: string; unit_id: number; unit_code: string; scaling_mode: string; manual_review: boolean; preparation: string | null; prep_method: string | null; prep_size: string | null; prep_state: string | null }
export type RecipeScaleResponse = { recipe_id: number; base_servings: string; requested_servings: string; scale_factor: string; ingredients: ScaledRecipeIngredient[] }
export type InventoryLot = { id: number; household_id: number; ingredient_id: number; location_id: number; quantity: string; unit_id: number; purchase_date: string | null; opened_date: string | null; expiration_date: string | null; frozen_date: string | null; thawed_date: string | null; notes: string | null }
export type InventoryTransaction = { id: number; lot_id: number; transaction_type: string; quantity_delta: string; unit_id: number; from_location_id: number | null; to_location_id: number | null; note: string | null; created_at: string }
export type InventoryLotDetail = InventoryLot & { transactions: InventoryTransaction[] }

async function jsonRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(body?.detail ?? `Request failed: ${response.status}`)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const fetchHealth = (): Promise<HealthResponse> => jsonRequest('/health')
export const fetchHousehold = (): Promise<Household> => jsonRequest('/api/reference/household')
export const updateHousehold = (input: { name: string; default_servings: string }): Promise<Household> => jsonRequest('/api/reference/household', { method: 'PUT', body: JSON.stringify(input) })
export const fetchMeasurementUnits = (): Promise<MeasurementUnit[]> => jsonRequest('/api/reference/units')
export const fetchShoppingCategories = (): Promise<ShoppingCategory[]> => jsonRequest('/api/reference/shopping-categories')
export const createShoppingCategory = (input: { name: string; sort_order: number }): Promise<ShoppingCategory> => jsonRequest('/api/reference/shopping-categories', { method: 'POST', body: JSON.stringify(input) })
export const updateShoppingCategory = (category: ShoppingCategory): Promise<ShoppingCategory> => jsonRequest(`/api/reference/shopping-categories/${category.id}`, { method: 'PUT', body: JSON.stringify({ name: category.name, sort_order: category.sort_order, active: category.active }) })
export const archiveShoppingCategory = (id: number): Promise<void> => jsonRequest(`/api/reference/shopping-categories/${id}`, { method: 'DELETE' })
export const fetchInventoryLocations = (): Promise<InventoryLocation[]> => jsonRequest('/api/reference/inventory-locations')
export const createInventoryLocation = (input: { name: string; parent_location_id: number | null; location_type: string; sort_order: number }): Promise<InventoryLocation> => jsonRequest('/api/reference/inventory-locations', { method: 'POST', body: JSON.stringify(input) })
export const updateInventoryLocation = (location: InventoryLocation): Promise<InventoryLocation> => jsonRequest(`/api/reference/inventory-locations/${location.id}`, { method: 'PUT', body: JSON.stringify({ name: location.name, parent_location_id: location.parent_location_id, location_type: location.location_type, sort_order: location.sort_order, active: location.active }) })
export const archiveInventoryLocation = (id: number): Promise<void> => jsonRequest(`/api/reference/inventory-locations/${id}`, { method: 'DELETE' })
export function fetchIngredients(search = '', includeInactive = false): Promise<Ingredient[]> { const params = new URLSearchParams(); if (search.trim()) params.set('search', search.trim()); if (includeInactive) params.set('include_inactive', 'true'); const query = params.toString(); return jsonRequest(`/api/ingredients${query ? `?${query}` : ''}`) }
export const createIngredient = (input: IngredientInput): Promise<Ingredient> => jsonRequest('/api/ingredients', { method: 'POST', body: JSON.stringify(input) })
export const updateIngredient = (ingredient: Ingredient, input: IngredientInput): Promise<Ingredient> => jsonRequest(`/api/ingredients/${ingredient.id}`, { method: 'PUT', body: JSON.stringify({ ...input, active: input.active ?? ingredient.active }) })
export const archiveIngredient = (id: number): Promise<void> => jsonRequest(`/api/ingredients/${id}`, { method: 'DELETE' })
export const fetchTags = (includeInactive = false): Promise<Tag[]> => jsonRequest(`/api/tags${includeInactive ? '?include_inactive=true' : ''}`)
export const createTag = (input: { name: string; category: string }): Promise<Tag> => jsonRequest('/api/tags', { method: 'POST', body: JSON.stringify(input) })
export const updateTag = (tag: Tag): Promise<Tag> => jsonRequest(`/api/tags/${tag.id}`, { method: 'PUT', body: JSON.stringify({ name: tag.name, category: tag.category, active: tag.active }) })
export const archiveTag = (id: number): Promise<void> => jsonRequest(`/api/tags/${id}`, { method: 'DELETE' })
export function fetchRecipes(filters?: { search?: string; meal_type?: string; tag_id?: number; favorite?: boolean; include_inactive?: boolean }): Promise<Recipe[]> { const params = new URLSearchParams(); if (filters?.search?.trim()) params.set('search', filters.search.trim()); if (filters?.meal_type) params.set('meal_type', filters.meal_type); if (filters?.tag_id) params.set('tag_id', String(filters.tag_id)); if (filters?.favorite !== undefined) params.set('favorite', String(filters.favorite)); if (filters?.include_inactive) params.set('include_inactive', 'true'); const query = params.toString(); return jsonRequest(`/api/recipes${query ? `?${query}` : ''}`) }
export const fetchRecipe = (id: number): Promise<Recipe> => jsonRequest(`/api/recipes/${id}`)
export const createRecipe = (input: RecipeInput): Promise<Recipe> => jsonRequest('/api/recipes', { method: 'POST', body: JSON.stringify(input) })
export const updateRecipe = (recipe: Recipe, input: RecipeInput): Promise<Recipe> => jsonRequest(`/api/recipes/${recipe.id}`, { method: 'PUT', body: JSON.stringify({ ...input, active: input.active ?? recipe.active }) })
export const archiveRecipe = (id: number): Promise<void> => jsonRequest(`/api/recipes/${id}`, { method: 'DELETE' })
export const scaleRecipe = (id: number, requestedServings: string, unitOverrides: Record<number, string> = {}): Promise<RecipeScaleResponse> => jsonRequest(`/api/recipes/${id}/scale`, { method: 'POST', body: JSON.stringify({ requested_servings: requestedServings, unit_overrides: unitOverrides }) })

export function fetchInventory(filters?: { ingredient_id?: number; location_id?: number; include_empty?: boolean }): Promise<InventoryLot[]> { const params = new URLSearchParams(); if (filters?.ingredient_id) params.set('ingredient_id', String(filters.ingredient_id)); if (filters?.location_id) params.set('location_id', String(filters.location_id)); if (filters?.include_empty) params.set('include_empty', 'true'); const query = params.toString(); return jsonRequest(`/api/inventory${query ? `?${query}` : ''}`) }
export const fetchInventoryLot = (id: number): Promise<InventoryLotDetail> => jsonRequest(`/api/inventory/${id}`)
export const createInventoryLot = (input: { ingredient_id: number; location_id: number; quantity: string; unit_id: number; purchase_date: string | null; opened_date: string | null; expiration_date: string | null; frozen_date: string | null; thawed_date: string | null; notes: string | null; transaction_type: 'PURCHASE' | 'MANUAL_ADD' }): Promise<InventoryLot> => jsonRequest('/api/inventory', { method: 'POST', body: JSON.stringify(input) })
export const addInventory = (id: number, quantity: string, note?: string): Promise<InventoryLot> => jsonRequest(`/api/inventory/${id}/add`, { method: 'POST', body: JSON.stringify({ quantity, note: note || null }) })
export const removeInventory = (id: number, quantity: string, note?: string): Promise<InventoryLot> => jsonRequest(`/api/inventory/${id}/remove`, { method: 'POST', body: JSON.stringify({ quantity, note: note || null }) })
export const correctInventory = (id: number, quantity: string, note?: string): Promise<InventoryLot> => jsonRequest(`/api/inventory/${id}/correct`, { method: 'POST', body: JSON.stringify({ quantity, note: note || null }) })
export const transferInventory = (id: number, toLocationId: number, note?: string): Promise<InventoryLot> => jsonRequest(`/api/inventory/${id}/transfer`, { method: 'POST', body: JSON.stringify({ to_location_id: toLocationId, note: note || null }) })
export const updateInventoryMetadata = (id: number, input: { purchase_date: string | null; opened_date: string | null; expiration_date: string | null; frozen_date: string | null; thawed_date: string | null; notes: string | null }): Promise<InventoryLot> => jsonRequest(`/api/inventory/${id}`, { method: 'PUT', body: JSON.stringify(input) })
