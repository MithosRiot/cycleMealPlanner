export type CombinedPrepSource = {
  planned_meal_id: number
  meal_recipe_id: number
  recipe_id: number
  recipe_name: string
  recipe_ingredient_id: number | null
  advance_prep_id: number | null
  quantity: string | null
  unit_code: string | null
}

export type CombinedIngredientPrep = {
  planned_meal_id: number
  meal_name: string
  day_number: number
  slot_label: string
  ingredient_id: number
  ingredient_name: string
  prep_group_name: string | null
  preparation: string | null
  prep_method: string | null
  prep_size: string | null
  prep_state: string | null
  quantity: string
  unit_id: number
  unit_code: string
  sources: CombinedPrepSource[]
}

export type CombinedAdvancePrep = {
  planned_meal_id: number
  meal_name: string
  day_number: number
  slot_label: string
  task_type: string
  title: string
  instructions: string | null
  prep_group_name: string | null
  lead_time_minutes: number
  duration_minutes: number | null
  serving_datetime: string | null
  start_datetime: string | null
  end_datetime: string | null
  reminder_enabled: boolean
  reminder_offset_minutes: number | null
  reminder_at: string | null
  sources: CombinedPrepSource[]
}

export type CombinedPrep = {
  meal_cycle_id: number
  meal_cycle_name: string
  ingredient_prep: CombinedIngredientPrep[]
  advance_prep: CombinedAdvancePrep[]
}

async function checked<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(body?.detail ?? `Request failed: ${response.status}`)
  }
  return response.json() as Promise<T>
}

export function fetchCombinedPrep(cycleId: number): Promise<CombinedPrep> {
  return fetch(`/api/meal-cycles/${cycleId}/combined-prep`).then(checked<CombinedPrep>)
}
