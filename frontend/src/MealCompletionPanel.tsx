import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { fetchIngredients, fetchMeasurementUnits } from './api'
import { fetchMealCycles } from './mealCyclesApi'
import { finalizeCompletion, refreshCompletion, saveCompletion, startCompletion, type CompletionUsage, type MealCompletion } from './completionApi'

function draftRows(completion: MealCompletion | null): CompletionUsage[] {
  return completion ? completion.usages.map((row) => ({ ...row })) : []
}

export default function MealCompletionPanel() {
  const cycles = useQuery({ queryKey: ['meal-cycles'], queryFn: fetchMealCycles })
  const ingredients = useQuery({ queryKey: ['ingredients', 'completion'], queryFn: () => fetchIngredients('', true) })
  const units = useQuery({ queryKey: ['reference-units'], queryFn: fetchMeasurementUnits })
  const [plannedMealId, setPlannedMealId] = useState<number | null>(null)
  const [completion, setCompletion] = useState<MealCompletion | null>(null)
  const [draft, setDraft] = useState<CompletionUsage[]>([])

  const plannedMeals = useMemo(() => (cycles.data ?? []).flatMap((cycle) => cycle.slots
    .filter((slot) => slot.planned_meal)
    .map((slot) => ({ cycleName: cycle.name, day: slot.day_number, meal: slot.planned_meal! }))), [cycles.data])

  useEffect(() => { setCompletion(null); setDraft([]) }, [plannedMealId])

  const start = useMutation({
    mutationFn: () => startCompletion(plannedMealId as number),
    onSuccess: (value) => { setCompletion(value); setDraft(draftRows(value)) },
  })
  const save = useMutation({
    mutationFn: () => saveCompletion(plannedMealId as number, draft.map((row) => ({
      usage_id: row.id,
      actual_ingredient_id: row.actual_ingredient_id,
      actual_quantity: row.actual_quantity,
      actual_unit_id: row.actual_unit_id,
      notes: row.notes,
    }))),
    onSuccess: (value) => { setCompletion(value); setDraft(draftRows(value)) },
  })
  const refresh = useMutation({
    mutationFn: () => refreshCompletion(plannedMealId as number),
    onSuccess: (value) => { setCompletion(value); setDraft(draftRows(value)) },
  })
  const finalize = useMutation({
    mutationFn: () => finalizeCompletion(plannedMealId as number),
    onSuccess: (value) => {
      if (value.completion) {
        setCompletion(value.completion)
        setDraft(draftRows(value.completion))
      }
    },
  })

  const patch = (id: number, update: Partial<CompletionUsage>) => setDraft((rows) => rows.map((row) => row.id === id ? { ...row, ...update } : row))
  const error = start.error || save.error || refresh.error || finalize.error
  const finalized = completion?.status === 'FINALIZED'

  return <section className="panel" style={{ marginTop: 20 }}>
    <div className="section-heading">
      <div><h2>Meal completion</h2><p className="planning-note">Review actual ingredient usage, then finalize to deduct physical Inventory.</p></div>
      <select value={plannedMealId ?? ''} onChange={(event) => setPlannedMealId(event.target.value ? Number(event.target.value) : null)}>
        <option value="">Select planned Meal</option>
        {plannedMeals.map(({ cycleName, day, meal }) => <option value={meal.id} key={meal.id}>{cycleName} · Day {day} · {meal.snapshot_name}</option>)}
      </select>
    </div>
    {error instanceof Error && <div className="error-banner">{error.message}</div>}
    {plannedMealId && !completion && <button type="button" disabled={start.isPending} onClick={() => start.mutate()}>Start / open completion draft</button>}
    {completion && <>
      <div className="ingredient-meta"><span>{completion.meal_name}</span><span>{completion.snapshot_planned_servings} planned + {completion.snapshot_planned_leftover_servings} planned leftovers</span><span>{completion.status}</span>{completion.finalized_at && <span>Finalized {new Date(completion.finalized_at).toLocaleString()}</span>}</div>
      {completion.stale && !finalized && <div className="error-banner">The Meal Plan changed after this draft was started. Review and refresh the draft before finalization. <button type="button" className="button-secondary" disabled={refresh.isPending} onClick={() => refresh.mutate()}>Refresh from current plan</button></div>}
      <div className="recipe-ingredient-list">
        {draft.map((row) => {
          const actualIngredient = ingredients.data?.find((item) => item.id === row.actual_ingredient_id)
          const actualUnit = units.data?.find((item) => item.id === row.actual_unit_id)
          const compatibleUnits = (units.data ?? []).filter((item) => !actualUnit || item.unit_family === actualUnit.unit_family)
          const selectableIngredients = (ingredients.data ?? []).filter((item) => item.active || item.id === row.actual_ingredient_id)
          return <div className="recipe-ingredient-editor" key={row.id}>
            <div><strong>{row.recipe_name} · {row.planned_ingredient_name}</strong><div className="ingredient-meta"><span>Planned: {row.planned_quantity} {row.planned_unit_code}</span>{row.preparation && <span>{row.preparation}</span>}</div></div>
            {row.substitutions.length > 0 && !finalized && <p className="planning-note">Configured substitutes: {row.substitutions.map((item) => `${item.ingredient_name}${item.preferred ? ' (preferred)' : ''}`).join(', ')}</p>}
            <div className="advanced-grid">
              <label>Actual ingredient<select disabled={finalized} value={row.actual_ingredient_id} onChange={(event) => {
                const id = Number(event.target.value)
                const selected = ingredients.data?.find((item) => item.id === id)
                patch(row.id, { actual_ingredient_id: id, actual_ingredient_name: selected?.name ?? `Ingredient ${id}` })
              }}>{selectableIngredients.map((item) => <option key={item.id} value={item.id}>{item.name}{item.active ? '' : ' (archived)'}</option>)}</select></label>
              <label>Actual quantity<input disabled={finalized} type="number" min="0" step="0.01" value={row.actual_quantity} onChange={(event) => patch(row.id, { actual_quantity: event.target.value })} /></label>
              <label>Unit<select disabled={finalized} value={row.actual_unit_id} onChange={(event) => patch(row.id, { actual_unit_id: Number(event.target.value), actual_unit_code: units.data?.find((item) => item.id === Number(event.target.value))?.code ?? '' })}>{compatibleUnits.map((item) => <option value={item.id} key={item.id}>{item.code}</option>)}</select></label>
              <label>Notes<input disabled={finalized} value={row.notes ?? ''} onChange={(event) => patch(row.id, { notes: event.target.value || null })} /></label>
            </div>
            {actualIngredient && !actualIngredient.active && <p className="planning-note">This historical Ingredient is archived. It can remain on this completion but cannot be newly selected elsewhere.</p>}
            {row.allocations.length > 0 && <p className="planning-note">Consumed from lots: {row.allocations.map((item) => `#${item.lot_id}: ${item.source_quantity} ${item.source_unit_code}`).join(', ')}</p>}
          </div>
        })}
      </div>
      {!finalized && <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <button type="button" disabled={save.isPending || draft.some((row) => Number(row.actual_quantity) < 0 || row.actual_quantity === '')} onClick={() => save.mutate()}>Save completion draft</button>
        <button type="button" disabled={finalize.isPending || completion.stale || save.isPending || draft.some((row) => Number(row.actual_quantity) < 0 || row.actual_quantity === '')} onClick={() => finalize.mutate()}>Finalize and deduct Inventory</button>
      </div>}
      {!finalized && <p className="planning-note">Finalization is atomic. If any actual usage is short, no Inventory is deducted and this completion stays DRAFT.</p>}
      {finalized && <p className="planning-note">Inventory consumption is finalized and locked. Leftover creation and reservation release are handled by the next v0.8 issues.</p>}
    </>}
  </section>
}
