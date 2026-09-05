import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { activateMealCycle, cancelMealCycle, completeMealCycle, fetchMealCycle, fetchMealCycles, updateMealCycleSchedule } from './mealCyclesApi'

export default function CycleSchedulingPanel() {
  const queryClient = useQueryClient()
  const cycles = useQuery({ queryKey: ['meal-cycles'], queryFn: fetchMealCycles })
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const effectiveId = selectedId ?? cycles.data?.[0]?.id ?? null
  const cycle = useQuery({ queryKey: ['meal-cycle', effectiveId], queryFn: () => fetchMealCycle(effectiveId as number), enabled: effectiveId !== null })
  const [startDate, setStartDate] = useState('')
  const [times, setTimes] = useState<Record<number, string>>({})

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
      return updateMealCycleSchedule(effectiveId, {
        start_date: startDate || null,
        serving_times: Object.fromEntries(Object.entries(times).map(([id, value]) => [Number(id), value || null])),
      })
    },
    onSuccess: async (updated) => refreshCycleState(updated.id),
  })
  const activate = useMutation({
    mutationFn: () => activateMealCycle(effectiveId as number),
    onSuccess: async (updated) => refreshCycleState(updated.id),
  })
  const complete = useMutation({
    mutationFn: () => completeMealCycle(effectiveId as number),
    onSuccess: async (updated) => refreshCycleState(updated.id),
  })
  const cancel = useMutation({
    mutationFn: () => cancelMealCycle(effectiveId as number),
    onSuccess: async (updated) => refreshCycleState(updated.id),
  })

  const scheduleRows = useMemo(() => {
    if (!cycle.data) return []
    return cycle.data.slots
      .filter((slot) => slot.planned_meal)
      .map((slot) => ({
        id: slot.id,
        name: slot.planned_meal?.snapshot_name ?? 'Planned meal',
        day: slot.day_number,
        label: cycle.data?.slot_definitions.find((item) => item.id === slot.slot_definition_id)?.label ?? 'Meal',
        scheduledDate: slot.scheduled_date,
        servingTime: slot.serving_time,
      }))
  }, [cycle.data])

  const lifecycleError = activate.error || complete.error || cancel.error
  const draft = cycle.data?.status === 'DRAFT'

  return <section className="panel" style={{ marginTop: 20 }}>
    <div className="section-heading">
      <div><h2>Cycle schedule</h2><p className="planning-note">Set dates/times, then activate the validated cycle. Active-cycle revisions are handled separately.</p></div>
      <select value={effectiveId ?? ''} onChange={(event) => setSelectedId(event.target.value ? Number(event.target.value) : null)}>
        <option value="">Select cycle</option>{cycles.data?.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.status}</option>)}
      </select>
    </div>
    {save.error instanceof Error && <div className="error-banner">{save.error.message}</div>}
    {lifecycleError instanceof Error && <div className="error-banner">{lifecycleError.message}</div>}
    {cycle.data && <>
      <div className="ingredient-meta" style={{ marginBottom: 12 }}>
        <span>Status: {cycle.data.status}</span>
        {cycle.data.activated_at && <span>Activated {new Date(cycle.data.activated_at).toLocaleString()}</span>}
        {cycle.data.completed_at && <span>Completed {new Date(cycle.data.completed_at).toLocaleString()}</span>}
        {cycle.data.cancelled_at && <span>Cancelled {new Date(cycle.data.cancelled_at).toLocaleString()}</span>}
      </div>
      <div className="planning-grid">
        <label>Cycle start date<input type="date" disabled={!draft} value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label>
        {cycle.data.slot_definitions.map((slot) => <label key={slot.id}>{slot.label} serving time<input type="time" disabled={!draft} value={times[slot.id] ?? ''} onChange={(event) => setTimes((current) => ({ ...current, [slot.id]: event.target.value }))} /></label>)}
      </div>
      <div className="ingredient-meta" style={{ marginTop: 12 }}>
        {draft && <button type="button" className="button-secondary" disabled={save.isPending} onClick={() => save.mutate()}>{save.isPending ? 'Saving…' : 'Save schedule'}</button>}
        {draft && <button type="button" disabled={activate.isPending} onClick={() => activate.mutate()}>{activate.isPending ? 'Activating…' : 'Activate cycle'}</button>}
        {cycle.data.status === 'ACTIVE' && <button type="button" disabled={complete.isPending} onClick={() => complete.mutate()}>{complete.isPending ? 'Completing…' : 'Complete cycle'}</button>}
        {(cycle.data.status === 'DRAFT' || cycle.data.status === 'ACTIVE') && <button type="button" className="button-secondary" disabled={cancel.isPending} onClick={() => { if (window.confirm(`Cancel ${cycle.data?.name}? Active reservations will be released.`)) cancel.mutate() }}>{cancel.isPending ? 'Cancelling…' : 'Cancel cycle'}</button>}
      </div>
      {cycle.data.status === 'ACTIVE' && <p className="planning-note">Schedule settings are locked while the cycle is ACTIVE. Complete or cancel the cycle to end its operational lifecycle.</p>}
      <div className="recipe-ingredient-list" style={{ marginTop: 16 }}>
        {scheduleRows.map((row) => <div className="ingredient-row" key={row.id}><strong>{row.name}</strong><div className="ingredient-meta"><span>Day {row.day} · {row.label}</span><span>{row.scheduledDate ?? 'No date'}{row.servingTime ? ` · ${row.servingTime.slice(0, 5)}` : ''}</span></div></div>)}
      </div>
      {scheduleRows.length === 0 && <p className="muted-line">No planned meals in this cycle yet.</p>}
    </>}
  </section>
}
