import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { fetchIngredients, fetchInventoryLocations, fetchMeasurementUnits } from './api'
import { fetchMealCycles } from './mealCyclesApi'
import {
  commitCompletionProduction,
  fetchCompletionProduction,
  fetchProductionPreview,
  finalizeCompletion,
  refreshCompletion,
  saveCompletion,
  startCompletion,
  type CompletionOutputCommitInput,
  type CompletionProduction,
  type CompletionProductionPreview,
  type CompletionUsage,
  type MealCompletion,
} from './completionApi'

function draftRows(completion: MealCompletion | null): CompletionUsage[] {
  return completion ? completion.usages.map((row) => ({ ...row })) : []
}

type OutputDraft = CompletionOutputCommitInput & { output_name: string; calculated_quantity: string; unit_code: string }

export default function MealCompletionPanel() {
  const cycles = useQuery({ queryKey: ['meal-cycles'], queryFn: fetchMealCycles })
  const ingredients = useQuery({ queryKey: ['ingredients', 'completion'], queryFn: () => fetchIngredients('', true) })
  const units = useQuery({ queryKey: ['reference-units'], queryFn: fetchMeasurementUnits })
  const locations = useQuery({ queryKey: ['inventory-locations'], queryFn: fetchInventoryLocations })
  const [plannedMealId, setPlannedMealId] = useState<number | null>(null)
  const [completion, setCompletion] = useState<MealCompletion | null>(null)
  const [draft, setDraft] = useState<CompletionUsage[]>([])
  const [preview, setPreview] = useState<CompletionProductionPreview | null>(null)
  const [production, setProduction] = useState<CompletionProduction | null>(null)
  const [produced, setProduced] = useState('')
  const [eaten, setEaten] = useState('')
  const [leftoverLocationId, setLeftoverLocationId] = useState('')
  const [leftoverExpiration, setLeftoverExpiration] = useState('')
  const [leftoverNotes, setLeftoverNotes] = useState('')
  const [outputDrafts, setOutputDrafts] = useState<OutputDraft[]>([])

  const plannedMeals = useMemo(() => (cycles.data ?? []).flatMap((cycle) => cycle.slots
    .filter((slot) => slot.planned_meal && !['MANUAL', 'EATING_OUT', 'SKIPPED'].includes(slot.planned_meal.source_type))
    .map((slot) => ({ cycleName: cycle.name, day: slot.day_number, meal: slot.planned_meal! }))), [cycles.data])

  useEffect(() => {
    setCompletion(null); setDraft([]); setPreview(null); setProduction(null); setProduced(''); setEaten(''); setOutputDrafts([])
    setLeftoverLocationId(''); setLeftoverExpiration(''); setLeftoverNotes('')
  }, [plannedMealId])

  const applyPreview = (value: CompletionProductionPreview) => {
    setPreview(value)
    if (!produced) setProduced(value.default_actual_servings_produced)
    if (!eaten) setEaten(value.default_actual_servings_eaten)
    setOutputDrafts(value.outputs.map((row) => ({
      recipe_output_id: row.recipe_output_id,
      component_key: row.component_key,
      actual_quantity: row.calculated_quantity,
      location_id: null,
      expiration_date: null,
      notes: null,
      output_name: row.output_name,
      calculated_quantity: row.calculated_quantity,
      unit_code: row.unit_code,
    })))
  }

  const loadProduction = async (mealId: number, value: MealCompletion) => {
    if (value.status !== 'FINALIZED') return
    if (value.production_committed_at) {
      const committed = await fetchCompletionProduction(mealId)
      setProduction(committed)
      setCompletion(committed.completion)
      return
    }
    const valuePreview = await fetchProductionPreview(mealId)
    applyPreview(valuePreview)
  }

  const start = useMutation({
    mutationFn: () => startCompletion(plannedMealId as number),
    onSuccess: async (value) => { setCompletion(value); setDraft(draftRows(value)); await loadProduction(plannedMealId as number, value) },
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
    onSuccess: async (value) => {
      if (value.completion) {
        setCompletion(value.completion)
        setDraft(draftRows(value.completion))
        await loadProduction(plannedMealId as number, value.completion)
      }
    },
  })
  const recalc = useMutation({
    mutationFn: () => fetchProductionPreview(plannedMealId as number, produced),
    onSuccess: (value) => {
      setPreview(value)
      setOutputDrafts(value.outputs.map((row) => ({
        recipe_output_id: row.recipe_output_id,
        component_key: row.component_key,
        actual_quantity: row.calculated_quantity,
        location_id: null,
        expiration_date: null,
        notes: null,
        output_name: row.output_name,
        calculated_quantity: row.calculated_quantity,
        unit_code: row.unit_code,
      })))
    },
  })
  const commitProduction = useMutation({
    mutationFn: () => commitCompletionProduction(plannedMealId as number, {
      actual_servings_produced: produced,
      actual_servings_eaten: eaten,
      leftover_location_id: Number(produced) - Number(eaten) > 0 && leftoverLocationId ? Number(leftoverLocationId) : null,
      leftover_expiration_date: leftoverExpiration || null,
      leftover_notes: leftoverNotes || null,
      outputs: outputDrafts.map(({ output_name: _outputName, calculated_quantity: _calculated, unit_code: _unitCode, ...row }) => row),
    }),
    onSuccess: (value) => { setProduction(value); setCompletion(value.completion) },
  })

  const patch = (id: number, update: Partial<CompletionUsage>) => setDraft((rows) => rows.map((row) => row.id === id ? { ...row, ...update } : row))
  const patchOutput = (index: number, update: Partial<OutputDraft>) => setOutputDrafts((rows) => rows.map((row, rowIndex) => rowIndex === index ? { ...row, ...update } : row))
  const error = start.error || save.error || refresh.error || finalize.error || recalc.error || commitProduction.error
  const finalized = completion?.status === 'FINALIZED'
  const leftoverQty = Math.max(0, Number(produced || 0) - Number(eaten || 0))

  return <section className="panel" style={{ marginTop: 20 }}>
    <div className="section-heading">
      <div><h2>Meal completion</h2><p className="planning-note">Reconcile actual ingredient usage, then record what the Meal actually produced.</p></div>
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
            {row.allocations.length > 0 && <p className="planning-note">Consumed from lots: {row.allocations.map((item) => `Lot ${item.lot_id}: ${item.source_quantity} ${item.source_unit_code}`).join(', ')}</p>}
          </div>
        })}
      </div>
      {!finalized && <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <button type="button" disabled={save.isPending || draft.some((row) => Number(row.actual_quantity) < 0 || row.actual_quantity === '')} onClick={() => save.mutate()}>Save completion draft</button>
        <button type="button" disabled={finalize.isPending || completion.stale || save.isPending || draft.some((row) => Number(row.actual_quantity) < 0 || row.actual_quantity === '')} onClick={() => finalize.mutate()}>Finalize and deduct Inventory</button>
      </div>}
      {!finalized && <p className="planning-note">Inventory finalization is atomic. If actual usage is short, nothing is deducted.</p>}

      {finalized && !production && preview && <section className="settings-card" style={{ marginTop: 16 }}>
        <div className="section-heading"><div><h3>Production and leftovers</h3><p className="planning-note">Planned values remain historical. Record what was actually produced and eaten.</p></div></div>
        <div className="advanced-grid">
          <label>Actual servings produced<input type="number" min="0" step="0.1" value={produced} onChange={(e) => setProduced(e.target.value)} /></label>
          <label>Actual servings eaten<input type="number" min="0" step="0.1" value={eaten} onChange={(e) => setEaten(e.target.value)} /></label>
          <label>Calculated leftovers<input readOnly value={Number.isFinite(leftoverQty) ? String(leftoverQty) : ''} /></label>
        </div>
        <button type="button" className="button-secondary" disabled={recalc.isPending || produced === '' || Number(produced) < 0} onClick={() => recalc.mutate()}>Recalculate Recipe outputs</button>
        {leftoverQty > 0 && <div className="advanced-grid" style={{ marginTop: 12 }}>
          <label>Leftover location<select required value={leftoverLocationId} onChange={(e) => setLeftoverLocationId(e.target.value)}><option value="">Select location</option>{locations.data?.filter((item) => item.active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <label>Leftover use-by<input type="date" value={leftoverExpiration} onChange={(e) => setLeftoverExpiration(e.target.value)} /></label>
          <label>Leftover notes<input value={leftoverNotes} onChange={(e) => setLeftoverNotes(e.target.value)} /></label>
        </div>}
        {outputDrafts.map((row, index) => <div className="recipe-ingredient-editor" key={`${row.component_key}-${row.recipe_output_id}`}>
          <strong>{row.output_name}</strong>
          <p className="planning-note">Calculated: {row.calculated_quantity} {row.unit_code}. Adjust actual output if needed.</p>
          <div className="advanced-grid">
            <label>Actual output quantity<input type="number" min="0" step="any" value={row.actual_quantity} onChange={(e) => patchOutput(index, { actual_quantity: e.target.value })} /></label>
            <label>Storage location<select disabled={Number(row.actual_quantity) <= 0} value={row.location_id ?? ''} onChange={(e) => patchOutput(index, { location_id: e.target.value ? Number(e.target.value) : null })}><option value="">Select location</option>{locations.data?.filter((item) => item.active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
            <label>Use-by<input disabled={Number(row.actual_quantity) <= 0} type="date" value={row.expiration_date ?? ''} onChange={(e) => patchOutput(index, { expiration_date: e.target.value || null })} /></label>
            <label>Notes<input value={row.notes ?? ''} onChange={(e) => patchOutput(index, { notes: e.target.value || null })} /></label>
          </div>
        </div>)}
        <button type="button" disabled={commitProduction.isPending || produced === '' || eaten === '' || Number(produced) < 0 || Number(eaten) < 0 || Number(eaten) > Number(produced) || (leftoverQty > 0 && !leftoverLocationId) || outputDrafts.some((row) => Number(row.actual_quantity) > 0 && !row.location_id)} onClick={() => commitProduction.mutate()}>Commit production and create leftovers</button>
      </section>}

      {production && <section className="settings-card" style={{ marginTop: 16 }}>
        <h3>Production committed</h3>
        <p className="planning-note">Produced {production.leftover.actual_servings_produced} servings · ate {production.leftover.actual_servings_eaten} · leftovers {production.leftover.leftover_servings}.</p>
        <p className="planning-note">Leftover status: {production.leftover.status}{production.leftover.inventory_lot_id ? ` · Inventory Lot ${production.leftover.inventory_lot_id}` : ' · no leftover lot created'}.</p>
        {production.outputs.map((row) => <p className="planning-note" key={row.id}>{row.output_name}: {row.actual_quantity} {row.unit_code}{row.quantity_overridden ? ' (adjusted)' : ''}{row.inventory_lot_id ? ` · Inventory Lot ${row.inventory_lot_id}` : ' · no lot created'}</p>)}
        <p className="planning-note">Committed {new Date(production.completion.production_committed_at as string).toLocaleString()}. Production records are locked and repeated commit requests are idempotent.</p>
      </section>}
    </>}
  </section>
}
