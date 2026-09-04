export type InventoryReservation = {
  id: number
  cycle_id: number
  planned_meal_id: number
  meal_recipe_id: number | null
  recipe_id: number
  recipe_ingredient_id: number | null
  ingredient_id: number
  quantity: string
  unit_id: number
  status: 'ACTIVE' | 'RELEASED'
}

export type ReservationCycleSummary = {
  cycle_id: number
  active_count: number
  released_count: number
  reservations: InventoryReservation[]
}

export type InventoryAvailability = {
  ingredient_id: number
  unit_family: string
  unit_id: number
  unit_code: string
  physical_quantity: string
  reserved_quantity: string
  available_quantity: string
  shortage_quantity: string
}

export type ProductionCoverage = {
  id: number
  cycle_id: number
  planned_meal_id: number
  cycle_slot_id: number
  source_origin_planned_meal_id: number
  source_type: 'LEFTOVER' | 'RECIPE_OUTPUT'
  source_record_id: number | null
  source_recipe_output_id: number | null
  lot_id: number | null
  requested_quantity: string
  reserved_quantity: string
  shortage_quantity: string
  unit_id: number
  status: 'ACTIVE' | 'RELEASED'
  release_reason: string | null
  created_at: string
  updated_at: string
  released_at: string | null
}

export type ProductionCoverageCycleSummary = {
  cycle_id: number
  active_count: number
  released_count: number
  shortage_count: number
  reservations: ProductionCoverage[]
}

export type ProductionAvailability = {
  lot_id: number
  source_type: 'LEFTOVER' | 'RECIPE_OUTPUT'
  source_id: number | null
  source_name: string | null
  unit_id: number
  physical_quantity: string
  reserved_quantity: string
  available_quantity: string
  expiration_date: string | null
}

async function jsonRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(body?.detail ?? `Request failed: ${response.status}`)
  }
  return response.json() as Promise<T>
}

export const fetchCycleReservations = (cycleId: number): Promise<ReservationCycleSummary> => jsonRequest(`/api/meal-cycles/${cycleId}/reservations`)
export const regenerateCycleReservations = (cycleId: number): Promise<ReservationCycleSummary> => jsonRequest(`/api/meal-cycles/${cycleId}/reservations/regenerate`, { method: 'POST' })
export const fetchInventoryAvailability = (): Promise<InventoryAvailability[]> => jsonRequest('/api/inventory-availability')
export const fetchProductionCoverage = (cycleId: number): Promise<ProductionCoverageCycleSummary> => jsonRequest(`/api/meal-cycles/${cycleId}/production-coverage`)
export const reconcileProductionCoverage = (cycleId: number): Promise<ProductionCoverageCycleSummary> => jsonRequest(`/api/meal-cycles/${cycleId}/production-coverage/reconcile`, { method: 'POST' })
export const fetchProductionAvailability = (): Promise<ProductionAvailability[]> => jsonRequest('/api/production-inventory-availability')
