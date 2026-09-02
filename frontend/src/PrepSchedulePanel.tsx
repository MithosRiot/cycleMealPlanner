import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchMealCycles } from './mealCyclesApi'
import { fetchPrepSchedule } from './prepScheduleApi'

function formatDateTime(value: string | null) {
  if (!value) return 'Unscheduled'
  return new Date(value).toLocaleString()
}

export default function PrepSchedulePanel() {
  const cycles = useQuery({ queryKey: ['meal-cycles'], queryFn: fetchMealCycles })
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const effectiveId = selectedId ?? cycles.data?.[0]?.id ?? null
  const schedule = useQuery({
    queryKey: ['prep-schedule', effectiveId],
    queryFn: () => fetchPrepSchedule(effectiveId as number),
    enabled: effectiveId !== null,
  })

  return <section className="panel" style={{ marginTop: 20 }}>
    <div className="section-heading">
      <div><h2>Prep schedule</h2><p className="planning-note">Advance-prep tasks are calculated from each placed Meal's serving date/time.</p></div>
      <div className="header-actions">
        <select value={effectiveId ?? ''} onChange={(event) => setSelectedId(event.target.value ? Number(event.target.value) : null)}>
          <option value="">Select cycle</option>
          {cycles.data?.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.name}</option>)}
        </select>
        <button type="button" className="button-secondary" disabled={schedule.isFetching || effectiveId === null} onClick={() => schedule.refetch()}>Refresh</button>
      </div>
    </div>
    {schedule.error instanceof Error && <div className="error-banner">{schedule.error.message}</div>}
    <div className="recipe-ingredient-list">
      {schedule.data?.tasks.map((task) => <div className="recipe-ingredient-editor" key={`${task.planned_meal_id}-${task.advance_prep_id}`}>
        <strong>{task.title}</strong>
        <div className="ingredient-meta">
          <span>{task.meal_name} · {task.recipe_name}</span>
          {task.prep_group_name && <span>Prep group: {task.prep_group_name}</span>}
          <span>Start: {formatDateTime(task.start_datetime)}</span>
          {task.duration_minutes !== null && <span>End: {formatDateTime(task.end_datetime)} · {task.duration_minutes} min</span>}
          <span>Serve: {formatDateTime(task.serving_datetime)} · lead {task.lead_time_minutes} min</span>
          {task.unresolved_reason && <span className="warning-text">{task.unresolved_reason}</span>}
        </div>
        {task.instructions && <p className="planning-note">{task.instructions}</p>}
      </div>)}
    </div>
    {!schedule.isPending && schedule.data?.tasks.length === 0 && <p className="muted-line">No advance-prep tasks for placed Meals in this cycle.</p>}
  </section>
}
