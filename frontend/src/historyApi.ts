export type MealHistoryAllocation = { lot_id: number; inventory_transaction_id: number; source_quantity: string; source_unit_code: string }
export type MealHistoryUsage = { recipe_name: string; planned_ingredient_name: string; planned_quantity: string; planned_unit_code: string; actual_ingredient_name: string; actual_quantity: string; actual_unit_code: string; substituted: boolean; notes: string | null; allocations: MealHistoryAllocation[] }
export type MealHistoryLeftover = { id: number; leftover_servings: string; serving_unit: string; expiration_date: string | null; notes: string | null; inventory_lot_id: number | null; created_at: string }
export type MealHistoryOutput = { id: number; recipe_name: string; output_name: string; actual_quantity: string; unit_code: string; quantity_overridden: boolean; expiration_date: string | null; notes: string | null; inventory_lot_id: number | null; created_at: string }
export type MealHistoryEntry = { completion_id: number; planned_meal_id: number; meal_name: string; finalized_at: string; production_committed_at: string | null; planned_servings: string; planned_leftover_servings: string; actual_servings_produced: string | null; actual_servings_eaten: string | null; usages: MealHistoryUsage[]; leftover: MealHistoryLeftover | null; outputs: MealHistoryOutput[] }
export type InventoryHistoryEntry = { transaction_id: number; created_at: string; transaction_type: string; lot_id: number; ingredient_id: number | null; ingredient_name: string | null; source_type: string; source_id: number | null; source_name: string | null; quantity_delta: string; unit_id: number; unit_code: string; from_location_id: number | null; from_location_name: string | null; to_location_id: number | null; to_location_name: string | null; reason: string | null; note: string | null }

async function jsonRequest<T>(url: string): Promise<T> {
  const response = await fetch(url)
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(body?.detail ?? `Request failed: ${response.status}`)
  }
  return response.json() as Promise<T>
}

export const fetchMealHistory = (): Promise<MealHistoryEntry[]> => jsonRequest('/api/history/meals')

export function fetchInventoryHistory(filters: { ingredient_id?: number; lot_id?: number; transaction_type?: string; start_date?: string; end_date?: string }): Promise<InventoryHistoryEntry[]> {
  const params = new URLSearchParams()
  if (filters.ingredient_id) params.set('ingredient_id', String(filters.ingredient_id))
  if (filters.lot_id) params.set('lot_id', String(filters.lot_id))
  if (filters.transaction_type) params.set('transaction_type', filters.transaction_type)
  if (filters.start_date) params.set('start_date', filters.start_date)
  if (filters.end_date) params.set('end_date', filters.end_date)
  const query = params.toString()
  return jsonRequest(`/api/history/inventory${query ? `?${query}` : ''}`)
}
