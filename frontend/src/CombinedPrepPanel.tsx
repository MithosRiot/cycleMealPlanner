import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchMealCycles } from './mealCyclesApi'
import { fetchCombinedPrep } from './combinedPrepApi'

function formatQuantity(value: string | number): string {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return String(value)
  if (Object.is(numeric, -0) || numeric === 0) return '0'
  return numeric.toLocaleString(undefined, { useGrouping: false, maximumFractionDigits: 6 })
}

function prepDescription(item: { prep_method: string | null; prep_size: string | null; prep_state: string | null; preparation: string | null }) {
  return [item.prep_method, item.prep_size, item.prep_state, item.preparation].filter(Boolean).join(' · ')
}

export default function CombinedPrepPanel() {
  const cycles = useQuery({ queryKey: ['meal-cycles'], queryFn: fetchMealCycles })
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const effectiveId = selectedId ?? cycles.data?.[0]?.id ?? null
  const combined = useQuery({
    queryKey: ['combined-prep', effectiveId],
    queryFn: () => fetchCombinedPrep(effectiveId as number),
    enabled: effectiveId !== null,
  })

  return <section className="panel" style={{ marginTop: 20 }}>
    <div className="section-heading">
      <div><h2>Combined prep</h2><p className="planning-note">Compatible prep work is combined across Recipe components within each placed Meal.</p></div>
      <div className="header-actions">
        <select value={effectiveId ?? ''} onChange={(event) => setSelectedId(event.target.value ? Number(event.target.value) : null)}>
          <option value="">Select cycle</option>
          {cycles.data?.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.name}</option>)}
        </select>
        <button type="button" className="button-secondary" disabled={combined.isFetching || effectiveId === null} onClick={() => combined.refetch()}>Refresh</button>
      </div>
    </div>
    {combined.error instanceof Error && <div className="error-banner">{combined.error.message}</div>}

    <h3>Ingredient prep</h3>
    <div className="recipe-ingredient-list">
      {combined.data?.ingredient_prep.map((item, index) => <div className="recipe-ingredient-editor" key={`${item.planned_meal_id}-${item.ingredient_id}-${index}`}>
        <strong>Day {item.day_number} · {item.slot_label} · {item.meal_name}</strong>
        <div className="ingredient-meta">
          <span>{item.ingredient_name}: {formatQuantity(item.quantity)} {item.unit_code}</span>
          {item.prep_group_name && <span>Prep group: {item.prep_group_name}</span>}
          {prepDescription(item) && <span>{prepDescription(item)}</span>}
          <span>{item.sources.length} source{item.sources.length === 1 ? '' : 's'}</span>
        </div>
        {item.sources.length > 1 && <details><summary>Sources</summary>{item.sources.map((source) => <div className="planning-note" key={`${source.meal_recipe_id}-${source.recipe_ingredient_id}`}>{source.recipe_name}: {source.quantity !== null ? formatQuantity(source.quantity) : ''} {source.unit_code ?? ''}</div>)}</details>}
      </div>)}
    </div>
    {!combined.isPending && combined.data?.ingredient_prep.length === 0 && <p className="muted-line">No structured ingredient prep for placed Meals in this cycle.</p>}

    <h3>Advance prep tasks</h3>
    <div className="recipe-ingredient-list">
      {combined.data?.advance_prep.map((task, index) => <div className="recipe-ingredient-editor" key={`${task.planned_meal_id}-${task.title}-${index}`}>
        <strong>{task.task_type} · {task.title}</strong>
        <div className="ingredient-meta">
          <span>Day {task.day_number} · {task.slot_label} · {task.meal_name}</span>
          {task.prep_group_name && <span>Prep group: {task.prep_group_name}</span>}
          <span>{task.sources.length} source{task.sources.length === 1 ? '' : 's'}</span>
        </div>
        {task.instructions && <p className="planning-note">{task.instructions}</p>}
        {task.sources.length > 1 && <details><summary>Sources</summary>{task.sources.map((source) => <div className="planning-note" key={`${source.meal_recipe_id}-${source.advance_prep_id}`}>{source.recipe_name}</div>)}</details>}
      </div>)}
    </div>
    {!combined.isPending && combined.data?.advance_prep.length === 0 && <p className="muted-line">No advance-prep tasks for placed Meals in this cycle.</p>}
  </section>
}
