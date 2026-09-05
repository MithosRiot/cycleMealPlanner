export type UseSoonRecommendation = {
  lot_id: number
  source_type: 'INGREDIENT' | 'LEFTOVER' | 'RECIPE_OUTPUT'
  source_id: number | null
  source_name: string
  ingredient_id: number | null
  location_id: number
  location_name: string
  available_quantity: string
  unit_id: number
  unit_code: string
  expiration_date: string
  days_remaining: number
}

export type UseSoonResponse = {
  horizon_days: number
  recommendations: UseSoonRecommendation[]
}

export async function fetchUseSoon(days = 7): Promise<UseSoonResponse> {
  const response = await fetch(`/api/dashboard/use-soon?days=${days}`)
  if (!response.ok) throw new Error(`Use-soon request failed: ${response.status}`)
  return response.json() as Promise<UseSoonResponse>
}
