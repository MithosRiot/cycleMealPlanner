import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'

type PrepTask = {
  id: number
  title: string
  task_type: string
  reminder_enabled: boolean
  reminder_offset_minutes: number | null
}
type RecipeWithPrep = { id: number; advance_prep: PrepTask[] }

async function fetchRecipePrep(recipeId: number): Promise<RecipeWithPrep> {
  const response = await fetch(`/api/recipes/${recipeId}`)
  if (!response.ok) throw new Error(`Recipe request failed: ${response.status}`)
  return response.json() as Promise<RecipeWithPrep>
}

async function updateReminder(recipeId: number, prepId: number, enabled: boolean, offsetMinutes: number | null): Promise<RecipeWithPrep> {
  const params = new URLSearchParams({ enabled: String(enabled) })
  if (offsetMinutes !== null) params.set('offset_minutes', String(offsetMinutes))
  const response = await fetch(`/api/recipes/${recipeId}/advance-prep/${prepId}/reminder?${params.toString()}`, { method: 'PUT' })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(body?.detail ?? `Reminder update failed: ${response.status}`)
  }
  return response.json() as Promise<RecipeWithPrep>
}

export default function PrepReminderPanel() {
  const { recipeId } = useParams()
  const id = Number(recipeId)
  const queryClient = useQueryClient()
  const recipe = useQuery({ queryKey: ['prep-reminders', id], queryFn: () => fetchRecipePrep(id), enabled: Number.isFinite(id) })
  const update = useMutation({
    mutationFn: ({ prepId, enabled, offsetMinutes }: { prepId: number; enabled: boolean; offsetMinutes: number | null }) => updateReminder(id, prepId, enabled, offsetMinutes),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['prep-reminders', id] })
      await queryClient.invalidateQueries({ queryKey: ['typed-advance-prep', id] })
      await queryClient.invalidateQueries({ queryKey: ['recipe', id] })
      await queryClient.invalidateQueries({ queryKey: ['recipes'] })
      await queryClient.invalidateQueries({ queryKey: ['prep-schedule'] })
    },
  })

  if (!recipe.data || recipe.data.advance_prep.length === 0) return null
  return <section className="panel" style={{ marginTop: 20 }}>
    <div className="section-heading"><div><h2>Prep reminders</h2><p className="planning-note">Optional local reminders are calculated relative to each scheduled prep task.</p></div></div>
    {update.error instanceof Error && <div className="error-banner">{update.error.message}</div>}
    <div className="recipe-ingredient-list">{recipe.data.advance_prep.map((task) => <div className="ingredient-row" key={task.id}>
      <strong>{task.task_type} · {task.title}</strong>
      <label className="checkbox-label"><input type="checkbox" checked={task.reminder_enabled} disabled={update.isPending} onChange={(event) => update.mutate({ prepId: task.id, enabled: event.target.checked, offsetMinutes: event.target.checked ? (task.reminder_offset_minutes ?? 15) : null })} />Reminder enabled</label>
      <label>Minutes before prep start<input type="number" min="0" defaultValue={task.reminder_offset_minutes ?? 15} disabled={!task.reminder_enabled || update.isPending} onBlur={(event) => task.reminder_enabled && update.mutate({ prepId: task.id, enabled: true, offsetMinutes: Math.max(0, Number(event.target.value) || 0) })} /></label>
    </div>)}</div>
  </section>
}
