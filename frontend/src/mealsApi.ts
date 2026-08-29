import type { Tag } from './api'

export type MealRecipeInput = {
  recipe_id: number
  serving_multiplier: string
  default_servings: string | null
  sort_order: number
  notes: string | null
}

export type MealRecipe = MealRecipeInput & { id: number; meal_id: number }

export type MealInput = {
  name: string
  description: string | null
  favorite: boolean
  meal_types: string[]
  tag_ids: number[]
  recipes: MealRecipeInput[]
  active?: boolean
}

export type Meal = {
  id: number
  household_id: number
  name: string
  description: string | null
  favorite: boolean
  active: boolean
  meal_types: string[]
  tags: Tag[]
  recipes: MealRecipe[]
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

export function fetchMeals(filters?: { search?: string; meal_type?: string; tag_id?: number; favorite?: boolean; include_inactive?: boolean }): Promise<Meal[]> {
  const params = new URLSearchParams()
  if (filters?.search?.trim()) params.set('search', filters.search.trim())
  if (filters?.meal_type) params.set('meal_type', filters.meal_type)
  if (filters?.tag_id) params.set('tag_id', String(filters.tag_id))
  if (filters?.favorite !== undefined) params.set('favorite', String(filters.favorite))
  if (filters?.include_inactive) params.set('include_inactive', 'true')
  const query = params.toString()
  return request(`/api/meals${query ? `?${query}` : ''}`)
}

export const fetchMeal = (id: number): Promise<Meal> => request(`/api/meals/${id}`)
export const createMeal = (input: MealInput): Promise<Meal> => request('/api/meals', { method: 'POST', body: JSON.stringify(input) })
export const updateMeal = (meal: Meal, input: MealInput): Promise<Meal> => request(`/api/meals/${meal.id}`, { method: 'PUT', body: JSON.stringify({ ...input, active: input.active ?? meal.active }) })
export const archiveMeal = (id: number): Promise<void> => request(`/api/meals/${id}`, { method: 'DELETE' })
