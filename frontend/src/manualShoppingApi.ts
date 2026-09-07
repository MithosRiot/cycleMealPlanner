export type ManualShoppingItem = {
  id: number
  shopping_list_id: number
  name: string
  quantity: string
  unit_id: number | null
  unit_code: string | null
  shopping_category_id: number | null
  shopping_category_name: string
  shopping_category_sort_order: number
  ingredient_id: number | null
  ingredient_name: string | null
  notes: string | null
  status: 'PENDING' | 'COMPLETED' | 'SKIPPED'
  completed_at: string | null
  inventory_lot_id: number | null
  purchase_date: string | null
  storage_location_id: number | null
  storage_location_name: string | null
  expiration_date: string | null
}

export type ManualShoppingList = {
  meal_cycle_id: number
  shopping_list_id: number
  items: ManualShoppingItem[]
}

export type ManualShoppingWrite = {
  name: string
  quantity: string
  unit_id: number | null
  shopping_category_id: number | null
  ingredient_id: number | null
  notes: string | null
}

export type ManualShoppingComplete = {
  inventory_quantity: string | null
  inventory_unit_id: number | null
  storage_location_id: number | null
  purchase_date: string | null
  expiration_date: string | null
  inventory_notes: string | null
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(body?.detail ?? `Request failed: ${response.status}`)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const fetchManualShopping = (cycleId: number): Promise<ManualShoppingList> => request(`/api/shopping/${cycleId}/manual-items`)
export const createManualShopping = (cycleId: number, input: ManualShoppingWrite): Promise<ManualShoppingList> => request(`/api/shopping/${cycleId}/manual-items`, { method: 'POST', body: JSON.stringify(input) })
export const updateManualShopping = (cycleId: number, itemId: number, input: ManualShoppingWrite): Promise<ManualShoppingList> => request(`/api/shopping/${cycleId}/manual-items/${itemId}`, { method: 'PUT', body: JSON.stringify(input) })
export const deleteManualShopping = (cycleId: number, itemId: number): Promise<void> => request(`/api/shopping/${cycleId}/manual-items/${itemId}`, { method: 'DELETE' })
export const completeManualShopping = (cycleId: number, itemId: number, input: ManualShoppingComplete): Promise<ManualShoppingList> => request(`/api/shopping/${cycleId}/manual-items/${itemId}/complete`, { method: 'POST', body: JSON.stringify(input) })
export const skipManualShopping = (cycleId: number, itemId: number): Promise<ManualShoppingList> => request(`/api/shopping/${cycleId}/manual-items/${itemId}/skip`, { method: 'POST' })

export const manualShoppingDisplayQuantity = (item: Pick<ManualShoppingItem, 'quantity' | 'unit_code'>): string => `${Number(item.quantity).toLocaleString()}${item.unit_code ? ` ${item.unit_code}` : ''}`
export const manualShoppingCreatesInventory = (item: Pick<ManualShoppingItem, 'ingredient_id'>, createInventory: boolean): boolean => createInventory && item.ingredient_id !== null
