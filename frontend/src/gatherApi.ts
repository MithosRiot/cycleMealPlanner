export type GatherLot = {
  lot_id: number
  quantity: string
  unit_id: number
  unit_code: string
  location_id: number
  location_name: string | null
  expiration_date: string | null
  opened_date: string | null
  frozen_date: string | null
  thawed_date: string | null
}

export type GatherCandidate = GatherLot & { available_quantity: string }

export type GatherRequirement = {
  planned_meal_id: number
  meal_name: string
  day_number: number
  slot_label: string
  meal_recipe_id: number
  recipe_id: number
  recipe_ingredient_id: number
  ingredient_id: number
  ingredient_name: string
  required_quantity: string
  unit_id: number
  unit_code: string
  use_date: string | null
  selected_quantity: string
  shortage_quantity: string
  selections: GatherLot[]
  suggestions: GatherLot[]
  candidates: GatherCandidate[]
}

export type GatherCycle = { meal_cycle_id: number; meal_cycle_name: string; requirements: GatherRequirement[] }

export type GatherPickSource = {
  planned_meal_id: number
  meal_name: string
  day_number: number
  slot_label: string
  meal_recipe_id: number
  recipe_id: number
  recipe_ingredient_id: number
  ingredient_id: number
  ingredient_name: string
  quantity: string
  unit_id: number
  unit_code: string
}

export type GatherLocationPick = {
  lot_id: number
  ingredient_id: number
  ingredient_name: string
  quantity: string
  unit_id: number
  unit_code: string
  expiration_date: string | null
  opened_date: string | null
  frozen_date: string | null
  thawed_date: string | null
  sources: GatherPickSource[]
}

export type GatherLocationGroup = {
  location_id: number
  location_name: string
  location_path: string
  picks: GatherLocationPick[]
}

export type GatherIncompleteRequirement = {
  planned_meal_id: number
  meal_name: string
  day_number: number
  slot_label: string
  meal_recipe_id: number
  recipe_id: number
  recipe_ingredient_id: number
  ingredient_id: number
  ingredient_name: string
  required_quantity: string
  selected_quantity: string
  remaining_quantity: string
  unit_id: number
  unit_code: string
}

export type GatherByLocation = {
  meal_cycle_id: number
  meal_cycle_name: string
  complete: boolean
  locations: GatherLocationGroup[]
  incomplete_requirements: GatherIncompleteRequirement[]
}

async function checked<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(body?.detail ?? `Request failed: ${response.status}`)
  }
  return response.json() as Promise<T>
}

export function fetchGather(cycleId: number): Promise<GatherCycle> {
  return fetch(`/api/meal-cycles/${cycleId}/gather`).then(checked<GatherCycle>)
}

export function fetchGatherByLocation(cycleId: number): Promise<GatherByLocation> {
  return fetch(`/api/meal-cycles/${cycleId}/gather/by-location`).then(checked<GatherByLocation>)
}

export function applyGatherSuggestions(cycleId: number): Promise<GatherCycle> {
  return fetch(`/api/meal-cycles/${cycleId}/gather/apply-suggestions`, { method: 'POST' }).then(checked<GatherCycle>)
}

export function replaceGatherWithLot(cycleId: number, requirement: GatherRequirement, lotId: number, quantity: string): Promise<GatherCycle> {
  return fetch(`/api/meal-cycles/${cycleId}/gather/${requirement.planned_meal_id}/${requirement.meal_recipe_id}/${requirement.recipe_ingredient_id}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ selections: [{ lot_id: lotId, quantity }] }),
  }).then(checked<GatherCycle>)
}

export function clearGatherRequirement(cycleId: number, requirement: GatherRequirement): Promise<GatherCycle> {
  return fetch(`/api/meal-cycles/${cycleId}/gather/${requirement.planned_meal_id}/${requirement.meal_recipe_id}/${requirement.recipe_ingredient_id}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ selections: [] }),
  }).then(checked<GatherCycle>)
}
