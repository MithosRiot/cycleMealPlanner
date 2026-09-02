import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'

const TASK_TYPES = ['PREP', 'THAW', 'MARINATE', 'SOAK', 'PROOF'] as const

type TaskType = typeof TASK_TYPES[number]
type PrepTask = { id: number; task_type: TaskType; title: string; lead_time_minutes: number; duration_minutes: number | null }
type RecipeWithPrep = { id: number; advance_prep: PrepTask[] }

async function fetchRecipePrep(recipeId: number): Promise<RecipeWithPrep> {
  const response = await fetch(`/api/recipes/${recipeId}`)
  if (!response.ok) throw new Error(`Recipe request failed: ${response.status}`)
  return response.json() as Promise<RecipeWithPrep>
}

async function updateTaskType(recipeId: number, prepId: number, taskType: TaskType): Promise<RecipeWithPrep> {
  const response = await fetch(`/api/recipes/${recipeId}/advance-prep/${prepId}/type?task_type=${encodeURIComponent(taskType)}`, { method: 'PUT' })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(body?.detail ?? `Task type update failed: ${response.status}`)
  }
  return response.json() as Promise<RecipeWithPrep>
}

export default function TypedAdvancePrepPanel() {
  const { recipeId } = useParams()
  const id = Number(recipeId)
  const queryClient = useQueryClient()
  const recipe = useQuery({ queryKey: ['typed-advance-prep', id], queryFn: () => fetchRecipePrep(id), enabled: Number.isFinite(id) })
  const update = useMutation({
    mutationFn: ({ prepId, taskType }: { prepId: number; taskType: TaskType }) => updateTaskType(id, prepId, taskType),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['typed-advance-prep', id] })
      await queryClient.invalidateQueries({ queryKey: ['recipe', id] })
      await queryClient.invalidateQueries({ queryKey: ['recipes'] })
      await queryClient.invalidateQueries({ queryKey: ['prep-schedule'] })
    },
  })

  if (!recipe.data || recipe.data.advance_prep.length === 0) return null
  return <section className="panel" style={{ marginTop: 20 }}>
    <div className="section-heading"><div><h2>Advance prep task types</h2><p className="planning-note">Classify time-sensitive prep for scheduling and later reminders.</p></div></div>
    {update.error instanceof Error && <div className="error-banner">{update.error.message}</div>}
    <div className="recipe-ingredient-list">{recipe.data.advance_prep.map((task) => <div className="ingredient-row" key={task.id}>
      <strong>{task.title}</strong>
      <div className="ingredient-meta"><span>Lead {task.lead_time_minutes} min{task.duration_minutes !== null ? ` · duration ${task.duration_minutes} min` : ''}</span></div>
      <select aria-label={`${task.title} task type`} value={task.task_type} disabled={update.isPending} onChange={(event) => update.mutate({ prepId: task.id, taskType: event.target.value as TaskType })}>{TASK_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}</select>
    </div>)}</div>
  </section>
}
