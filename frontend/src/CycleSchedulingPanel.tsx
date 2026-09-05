import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchRecipes } from './api'
import { activateMealCycle, assignDirectRecipe, cancelMealCycle, completeMealCycle, fetchMealCycle, fetchMealCycles, updateMealCycleSchedule } from './mealCyclesApi'

export default function CycleSchedulingPanel() {
  const queryClient = useQueryClient()
  const cycles = useQuery({ queryKey: ['meal-cycles'], queryFn: fetchMealCycles })
  const recipes = useQuery({ queryKey: ['recipes', 'direct-recipe-placement'], queryFn: () => fetchRecipes() })
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const effectiveId = selectedId ?? cycles.data?.[0]?.id ?? null
  const cycle = useQuery({ queryKey: ['meal-cycle', effectiveId], queryFn: () => fetchMealCycle(effectiveId as number), enabled: effectiveId !== null })
  const [startDate, setStartDate] = useState('')
  const [times, setTimes] = useState<Record<number, string>>({})
  const [directSlotId, setDirectSlotId] = useState<number | null>(null)
  const [directRecipeId, setDirectRecipeId] = useState<number | null>(null)
  const [directServings, setDirectServings] = useState('4')
  const [directLeftovers, setDirectLeftovers] = useState('0')

  useEffect(() => {
    if (!cycle.data) return
    setStartDate(cycle.data.start_date ?? '')
    setTimes(Object.fromEntries(cycle.data.slot_definitions.map((slot) => [slot.id, (slot.serving_time ?? '').slice(0, 5)])))
  }, [cycle.data])

  const refreshCycleState = async (id: number) => {
    await queryClient.invalidateQueries({ queryKey: ['meal-cycle', id] })
    await queryClient.invalidateQueries({ queryKey: ['meal-cycles'] })
    await queryClient.invalidateQueries({ queryKey: ['expiration-suggestions', id] })
    await queryClient.invalidateQueries({ queryKey: ['prep-schedule', id] })
    await queryClient.invalidateQueries({ queryKey: ['cycle-validation', id] })
    await queryClient.invalidateQueries({ queryKey: ['inventory-availability'] })
    await queryClient.invalidateQueries({ queryKey: ['production-inventory-availability'] })
  }

  const save = useMutation({
    mutationFn: async () => {
      if (effectiveId === null) throw new Error('Select a cycle first')
      return updateMealCycleSchedule(effectiveId, { start_date: startDate || null, serving_times: Object.fromEntries(Object.entries(times).map(([id, value]) => [Number(id), value || null])) })
    },
    onSuccess: async (updated) => refreshCycleState(updated.id),
  })
  const activate = useMutation({ mutationFn: () => activateMealCycle(effectiveId as number), onSuccess: async (updated) => refreshCycleState(updated.id) })
  const complete = useMutation({ mutationFn: () => completeMealCycle(effectiveId as number), onSuccess: async (updated) => refreshCycleState(updated.id) })
  const cancel = useMutation({ mutationFn: () => cancelMealCycle(effectiveId as number), onSuccess: async (updated) => refreshCycleState(updated.id) })
  const placeDirectRecipe = useMutation({
    mutationFn: async () => {
      if (effectiveId === null || directSlotId === null || directRecipeId === null) throw new Error('Choose an empty slot and Recipe')
      return assignDirectRecipe(effectiveId, directSlotId, directRecipeId, directServings, directLeftovers)
    },
    onSuccess: async () => {
      if (effectiveId !== null) await refreshCycleState(effectiveId)
      setDirectSlotId(null)
      setDirectRecipeId(null)
      setDirectServings('4')
      setDirectLeftovers('0')
    },
  })

  const scheduleRows = useMemo(() => {
    if (!cycle.data) return []
    return cycle.data.slots.filter((slot) => slot.planned_meal).map((slot) => ({
      id: slot.id, name: slot.planned_meal?.snapshot_name ?? 'Planned meal', sourceType: slot.planned_meal?.source_type,
      day: slot.day_number, label: cycle.data?.slot_definitions.find((item) => item.id === slot.slot_definition_id)?.label ?? 'Meal',
      scheduledDate: slot.scheduled_date, servingTime: slot.serving_time,
    }))
  }, [cycle.data])
  const emptySlots = useMemo(() => cycle.data?.slots.filter((slot) => slot.planned_meal === null) ?? [], [cycle.data])

  const lifecycleError = activate.error || complete.error || cancel.error
  const draft = cycle.data?.status === 'DRAFT'

  return <section className="panel" style={{ marginTop: 20 }}>
    <div className="section-heading">
      <div><h2>Cycle schedule</h2><p className="planning-note">Set dates/times, place direct Recipes when needed, then activate the validated cycle.</p></div>
      <select value={effectiveId ?? ''} onChange={(event) => setSelectedId(event.target.value ? Number(event.target.value) : null)}><option value="">Select cycle</option>{cycles.data?.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.status}</option>)}</select>
    </div>
    {save.error instanceof Error && <div className="error-banner">{save.error.message}</div>}
    {lifecycleError instanceof Error && <div className="error-banner">{lifecycleError.message}</div>}
    {placeDirectRecipe.error instanceof Error && <div className="error-banner">{placeDirectRecipe.error.message}</div>}
    {cycle.data && <>
      <div className="ingredient-meta" style={{ marginBottom: 12 }}><span>Status: {cycle.data.status}</span>{cycle.data.activated_at && <span>Activated {new Date(cycle.data.activated_at).toLocaleString()}</span>}{cycle.data.completed_at && <span>Completed {new Date(cycle.data.completed_at).toLocaleString()}</span>}{cycle.data.cancelled_at && <span>Cancelled {new Date(cycle.data.cancelled_at).toLocaleString()}</span>}</div>
      <div className="planning-grid">
        <label>Cycle start date<input type="date" disabled={!draft} value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label>
        {cycle.data.slot_definitions.map((slot) => <label key={slot.id}>{slot.label} serving time<input type="time" disabled={!draft} value={times[slot.id] ?? ''} onChange={(event) => setTimes((current) => ({ ...current, [slot.id]: event.target.value }))} /></label>)}
      </div>
      <div className="ingredient-meta" style={{ marginTop: 12 }}>{draft && <button type="button" className="button-secondary" disabled={save.isPending} onClick={() => save.mutate()}>{save.isPending ? 'Saving…' : 'Save schedule'}</button>}{draft && <button type="button" disabled={activate.isPending} onClick={() => activate.mutate()}>{activate.isPending ? 'Activating…' : 'Activate cycle'}</button>}{cycle.data.status === 'ACTIVE' && <button type="button" disabled={complete.isPending} onClick={() => complete.mutate()}>{complete.isPending ? 'Completing…' : 'Complete cycle'}</button>}{(cycle.data.status === 'DRAFT' || cycle.data.status === 'ACTIVE') && <button type="button" className="button-secondary" disabled={cancel.isPending} onClick={() => { if (window.confirm(`Cancel ${cycle.data?.name}? Active reservations will be released.`)) cancel.mutate() }}>{cancel.isPending ? 'Cancelling…' : 'Cancel cycle'}</button>}</div>
      {draft && <section style={{ marginTop: 20 }}>
        <h3>Place a direct Recipe</h3>
        <p className="planning-note">Use a Recipe directly without creating a saved Meal wrapper.</p>
        <div className="planning-grid">
          <label>Empty slot<select value={directSlotId ?? ''} onChange={(event) => setDirectSlotId(event.target.value ? Number(event.target.value) : null)}><option value="">Choose slot…</option>{emptySlots.map((slot) => { const label = cycle.data?.slot_definitions.find((item) => item.id === slot.slot_definition_id)?.label ?? 'Meal'; return <option key={slot.id} value={slot.id}>Day {slot.day_number} · {label}</option> })}</select></label>
          <label>Recipe<select value={directRecipeId ?? ''} onChange={(event) => { const id = event.target.value ? Number(event.target.value) : null; setDirectRecipeId(id); const recipe = recipes.data?.find((item) => item.id === id); if (recipe) setDirectServings(recipe.base_servings) }}><option value="">Choose Recipe…</option>{recipes.data?.map((recipe) => <option key={recipe.id} value={recipe.id}>{recipe.name}</option>)}</select></label>
          <label>Eat servings<input type="number" min="0.001" step="0.001" value={directServings} onChange={(event) => setDirectServings(event.target.value)} /></label>
          <label>Planned leftovers<input type="number" min="0" step="0.001" value={directLeftovers} onChange={(event) => setDirectLeftovers(event.target.value)} /></label>
        </div>
        <button type="button" className="button-secondary" disabled={placeDirectRecipe.isPending || directSlotId === null || directRecipeId === null || Number(directServings) <= 0 || Number(directLeftovers) < 0} onClick={() => placeDirectRecipe.mutate()}>{placeDirectRecipe.isPending ? 'Placing…' : 'Place Recipe'}</button>
      </section>}
      {cycle.data.status === 'ACTIVE' && <p className="planning-note">Schedule and placement settings are locked while the cycle is ACTIVE.</p>}
      <div className="recipe-ingredient-list" style={{ marginTop: 16 }}>{scheduleRows.map((row) => <div className="ingredient-row" key={row.id}><strong>{row.name}</strong><div className="ingredient-meta"><span>{row.sourceType === 'DIRECT_RECIPE' ? 'Direct Recipe · ' : ''}Day {row.day} · {row.label}</span><span>{row.scheduledDate ?? 'No date'}{row.servingTime ? ` · ${row.servingTime.slice(0, 5)}` : ''}</span></div></div>)}</div>
      {scheduleRows.length === 0 && <p className="muted-line">No planned meals in this cycle yet.</p>}
    </>}
  </section>
}
