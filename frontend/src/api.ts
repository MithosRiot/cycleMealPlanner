export type HealthResponse = {
  status: string
}

export type Household = {
  id: number
  name: string
  default_servings: string
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

export function fetchShoppingCategories(): Promise<ShoppingCategory[]> {
  return jsonRequest<ShoppingCategory[]>('/api/reference/shopping-categories')
}

export function createShoppingCategory(input: { name: string; sort_order: number }): Promise<ShoppingCategory> {
  return jsonRequest<ShoppingCategory>('/api/reference/shopping-categories', {
    method: 'POST',
    body: JSON.stringify(input),
  })
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
