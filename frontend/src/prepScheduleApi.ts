export type PrepScheduleTask = {
  planned_meal_id: number
  cycle_slot_id: number
  meal_id: number
  meal_name: string
  recipe_id: number
  recipe_name: string
  advance_prep_id: number
  title: string
  instructions: string | null
  prep_group_id: number | null
  prep_group_name: string | null
  lead_time_minutes: number
  duration_minutes: number | null
  serving_datetime: string | null
  start_datetime: string | null
  end_datetime: string | null
  unresolved_reason: string | null
}

export type PrepSchedule = {
  meal_cycle_id: number
  meal_cycle_name: string
  tasks: PrepScheduleTask[]
}

export async function fetchPrepSchedule(cycleId: number): Promise<PrepSchedule> {
  const response = await fetch(`/api/meal-cycles/${cycleId}/prep-schedule`)
  if (!response.ok) throw new Error(`Prep schedule request failed: ${response.status}`)
  return response.json() as Promise<PrepSchedule>
}
