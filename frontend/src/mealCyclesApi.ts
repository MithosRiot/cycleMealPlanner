export type MealSlotDefinitionInput = {
  label: string
  sort_order: number
}

export type MealSlotDefinition = MealSlotDefinitionInput & {
  id: number
  cycle_id: number
}

export type CycleSlot = {
  id: number
  cycle_id: number
  slot_definition_id: number
  day_number: number
  sort_order: number
}

export type MealCycleInput = {
  name: string
  duration_days: number
  start_date: string | null
  notes: string | null
  slot_definitions: MealSlotDefinitionInput[]
}

export type MealCycle = {
  id: number
  household_id: number
  name: string
  duration_days: number
  status: 'DRAFT'
  start_date: string | null
  notes: string | null
  slot_definitions: MealSlotDefinition[]
  slots: CycleSlot[]
}

async function jsonRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(body?.detail ?? `Request failed: ${response.status}`)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const fetchMealCycles = (): Promise<MealCycle[]> => jsonRequest('/api/meal-cycles')
export const fetchMealCycle = (id: number): Promise<MealCycle> => jsonRequest(`/api/meal-cycles/${id}`)
export const createMealCycle = (input: MealCycleInput): Promise<MealCycle> => jsonRequest('/api/meal-cycles', { method: 'POST', body: JSON.stringify(input) })
export const updateMealCycle = (id: number, input: MealCycleInput): Promise<MealCycle> => jsonRequest(`/api/meal-cycles/${id}`, { method: 'PUT', body: JSON.stringify(input) })
export const deleteMealCycle = (id: number): Promise<void> => jsonRequest(`/api/meal-cycles/${id}`, { method: 'DELETE' })
