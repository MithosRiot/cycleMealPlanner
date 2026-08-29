export type ShoppingItem = {
  id: number
  ingredient_id: number
  ingredient_name: string
  shopping_category_id: number | null
  shopping_category_name: string
  shopping_category_sort_order: number
  unit_id: number
  unit_code: string
  unit_family: string
  required_quantity: string
  inventory_quantity: string
  generated_quantity: string
  adjustment_quantity: string
  final_quantity: string
  source_trace: string
  warning: string | null
}

export type ShoppingList = {
  id: number
  meal_cycle_id: number
  meal_cycle_name: string
  generated_at: string
  items: ShoppingItem[]
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(body?.detail ?? `Request failed: ${response.status}`)
  }
  return response.json() as Promise<T>
}

export const fetchShoppingList = (cycleId: number): Promise<ShoppingList> => request(`/api/shopping/${cycleId}`)
export const regenerateShoppingList = (cycleId: number): Promise<ShoppingList> => request(`/api/shopping/${cycleId}/regenerate`, { method: 'POST' })
export const adjustShoppingItem = (cycleId: number, itemId: number, adjustmentQuantity: string): Promise<ShoppingList> => request(`/api/shopping/${cycleId}/items/${itemId}`, { method: 'PUT', body: JSON.stringify({ adjustment_quantity: adjustmentQuantity }) })
