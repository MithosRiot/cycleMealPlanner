export type AllocationLot = {
  lot_id: number
  allocated_quantity: string
  unit_id: number
  unit_code: string
  source_quantity: string
  source_unit_id: number
  source_unit_code: string
  location_id: number
  location_name: string | null
  purchase_date: string | null
  opened_date: string | null
  expiration_date: string | null
  frozen_date: string | null
  thawed_date: string | null
}

export type AllocationRequirement = {
  ingredient_id: number
  ingredient_name: string | null
  requested_quantity: string
  unit_id: number
  unit_code: string
  unit_family: string
  use_date: string | null
  reserved_elsewhere_quantity: string
  allocated_quantity: string
  shortage_quantity: string
  allocations: AllocationLot[]
  planned_meal_id: number | null
  meal_name: string | null
  day_number: number | null
  slot_label: string | null
  recipe_id: number | null
}

export type CycleAllocationPreview = {
  meal_cycle_id: number
  meal_cycle_name: string
  requirements: AllocationRequirement[]
}

async function jsonRequest<T>(url: string): Promise<T> {
  const response = await fetch(url)
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(body?.detail ?? `Request failed: ${response.status}`)
  }
  return response.json() as Promise<T>
}

export const fetchCycleAllocationPreview = (cycleId: number): Promise<CycleAllocationPreview> =>
  jsonRequest(`/api/meal-cycles/${cycleId}/allocation-preview`)
