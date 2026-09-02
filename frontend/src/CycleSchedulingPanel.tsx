import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchMealCycle, fetchMealCycles, updateMealCycleSchedule } from './mealCyclesApi'

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

  const save = useMutation({
    mutationFn: async () => {
      if (effectiveId === null) throw new Error('Select a cycle first')
      return updateMealCycleSchedule(effectiveId, {
        start_date: startDate || null,
        serving_times: Object.fromEntries(Object.entries(times).map(([id, value]) => [Number(id), value || null])),
      })
    },
    onSuccess: async (updated) => {
      await queryClient.invalidateQueries({ queryKey: ['meal-cycle', updated.id] })
      await queryClient.invalidateQueries({ queryKey: ['meal-cycles'] })
      await queryClient.invalidateQueries({ queryKey: ['expiration-suggestions', updated.id] })
      await queryClient.invalidateQueries({ queryKey: ['prep-schedule', updated.id] })
    },
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

  return <section className="panel" style={{ marginTop: 20 }}>
    <div className="section-heading">
      <div><h2>Cycle schedule</h2><p className="planning-note">Set the cycle start date and serving times without rebuilding slots or deleting placements.</p></div>
      <select value={effectiveId ?? ''} onChange={(event) => setSelectedId(event.target.value ? Number(event.target.value) : null)}>
        <option value="">Select cycle</option>{cycles.data?.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select>
    </div>
    {save.error instanceof Error && <div className="error-banner">{save.error.message}</div>}
    {cycle.data && <>
      <div className="planning-grid">
        <label>Cycle start date<input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label>
        {cycle.data.slot_definitions.map((slot) => <label key={slot.id}>{slot.label} serving time<input type="time" value={times[slot.id] ?? ''} onChange={(event) => setTimes((current) => ({ ...current, [slot.id]: event.target.value }))} /></label>)}
      </div>
      <button type="button" className="button-secondary" disabled={save.isPending} onClick={() => save.mutate()}>{save.isPending ? 'Saving…' : 'Save schedule'}</button>
      <div className="recipe-ingredient-list" style={{ marginTop: 16 }}>
        {scheduleRows.map((row) => <div className="ingredient-row" key={row.id}><strong>{row.name}</strong><div className="ingredient-meta"><span>Day {row.day} · {row.label}</span><span>{row.scheduledDate ?? 'No date'}{row.servingTime ? ` · ${row.servingTime.slice(0, 5)}` : ''}</span></div></div>)}
      </div>
      {scheduleRows.length === 0 && <p className="muted-line">No planned meals in this cycle yet.</p>}
    </>}
  </section>
}
