import { FormEvent, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createMealCycle,
  deleteMealCycle,
  fetchMealCycle,
  fetchMealCycles,
  MealCycleInput,
  updateMealCycle,
} from './mealCyclesApi'
import './MealPlanPage.css'

const DEFAULT_SLOTS = ['Breakfast', 'Lunch', 'Dinner']

function makeDraft(): MealCycleInput {
  return {
    name: '',
    duration_days: 7,
    start_date: null,
    notes: null,
    slot_definitions: DEFAULT_SLOTS.map((label, index) => ({ label, sort_order: index })),
  }
}

export default function MealPlanPage() {
  const queryClient = useQueryClient()
  const cycles = useQuery({ queryKey: ['meal-cycles'], queryFn: fetchMealCycles })
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const selected = useQuery({
    queryKey: ['meal-cycle', selectedId],
    queryFn: () => fetchMealCycle(selectedId as number),
    enabled: selectedId !== null,
  })
  const [draft, setDraft] = useState<MealCycleInput>(makeDraft())
  const [editingId, setEditingId] = useState<number | null>(null)

  const slotGrid = useMemo(() => {
    const cycle = selected.data
    if (!cycle) return []
    return Array.from({ length: cycle.duration_days }, (_, index) => {
      const day = index + 1
      return {
        day,
        slots: cycle.slots.filter((slot) => slot.day_number === day),
      }
    })
  }, [selected.data])

  const saveMutation = useMutation({
    mutationFn: () => editingId === null ? createMealCycle(draft) : updateMealCycle(editingId, draft),
    onSuccess: async (cycle) => {
      await queryClient.invalidateQueries({ queryKey: ['meal-cycles'] })
      await queryClient.invalidateQueries({ queryKey: ['meal-cycle', cycle.id] })
      setSelectedId(cycle.id)
      setEditingId(null)
      setDraft(makeDraft())
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteMealCycle(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['meal-cycles'] })
      setSelectedId(null)
      setEditingId(null)
      setDraft(makeDraft())
    },
  })

  function startEdit() {
    if (!selected.data) return
    const cycle = selected.data
    setEditingId(cycle.id)
    setDraft({
      name: cycle.name,
      duration_days: cycle.duration_days,
      start_date: cycle.start_date,
      notes: cycle.notes,
      slot_definitions: cycle.slot_definitions.map((slot) => ({ label: slot.label, sort_order: slot.sort_order })),
    })
  }

  function addSlot() {
    setDraft((current) => ({
      ...current,
      slot_definitions: [...current.slot_definitions, { label: '', sort_order: current.slot_definitions.length }],
    }))
  }

  function updateSlot(index: number, label: string) {
    setDraft((current) => ({
      ...current,
      slot_definitions: current.slot_definitions.map((slot, slotIndex) => slotIndex === index ? { ...slot, label } : slot),
    }))
  }

  function removeSlot(index: number) {
    setDraft((current) => ({
      ...current,
      slot_definitions: current.slot_definitions
        .filter((_, slotIndex) => slotIndex !== index)
        .map((slot, slotIndex) => ({ ...slot, sort_order: slotIndex })),
    }))
  }

  function moveSlot(index: number, direction: -1 | 1) {
    const target = index + direction
    if (target < 0 || target >= draft.slot_definitions.length) return
    const copy = [...draft.slot_definitions]
    ;[copy[index], copy[target]] = [copy[target], copy[index]]
    setDraft((current) => ({
      ...current,
      slot_definitions: copy.map((slot, slotIndex) => ({ ...slot, sort_order: slotIndex })),
    }))
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    saveMutation.mutate()
  }

  return (
    <section className="meal-plan-page">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Cycle Planning</p>
          <h1>Meal Plan</h1>
          <p>Create reusable draft cycles with any duration up to one year and define the ordered meal slots used on each day.</p>
        </div>
      </header>

      <div className="meal-plan-layout">
        <aside className="cycle-list panel">
          <h2>Cycles</h2>
          {cycles.data?.map((cycle) => (
            <button
              type="button"
              className={selectedId === cycle.id ? 'cycle-select active' : 'cycle-select'}
              key={cycle.id}
              onClick={() => setSelectedId(cycle.id)}
            >
              <strong>{cycle.name}</strong>
              <span>{cycle.duration_days} days · {cycle.slot_definitions.length} slots/day</span>
            </button>
          ))}
          {!cycles.isPending && cycles.data?.length === 0 && <p>No cycles yet.</p>}
        </aside>

        <div className="cycle-workspace">
          <form className="panel cycle-editor" onSubmit={submit}>
            <div className="section-heading">
              <h2>{editingId === null ? 'New cycle' : 'Edit cycle'}</h2>
              {editingId !== null && <button type="button" className="button-secondary" onClick={() => { setEditingId(null); setDraft(makeDraft()) }}>Cancel edit</button>}
            </div>

            <div className="form-grid">
              <label>
                Cycle name
                <input required value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} />
              </label>
              <label>
                Duration (days)
                <input type="number" min="1" max="365" required value={draft.duration_days} onChange={(event) => setDraft({ ...draft, duration_days: Number(event.target.value) })} />
              </label>
              <label>
                Start date (optional)
                <input type="date" value={draft.start_date ?? ''} onChange={(event) => setDraft({ ...draft, start_date: event.target.value || null })} />
              </label>
              <label className="wide-field">
                Notes
                <textarea value={draft.notes ?? ''} onChange={(event) => setDraft({ ...draft, notes: event.target.value || null })} />
              </label>
            </div>

            <div className="section-heading">
              <h3>Meal slots</h3>
              <button type="button" className="button-secondary" onClick={addSlot}>Add slot</button>
            </div>
            <div className="slot-editor-list">
              {draft.slot_definitions.map((slot, index) => (
                <div className="slot-editor-row" key={`${index}-${slot.sort_order}`}>
                  <span className="slot-order">{index + 1}</span>
                  <input required placeholder="Slot label" value={slot.label} onChange={(event) => updateSlot(index, event.target.value)} />
                  <button type="button" className="button-secondary" disabled={index === 0} onClick={() => moveSlot(index, -1)}>↑</button>
                  <button type="button" className="button-secondary" disabled={index === draft.slot_definitions.length - 1} onClick={() => moveSlot(index, 1)}>↓</button>
                  <button type="button" className="button-secondary" disabled={draft.slot_definitions.length === 1} onClick={() => removeSlot(index)}>Remove</button>
                </div>
              ))}
            </div>
            {saveMutation.isError && <div className="error-banner">{(saveMutation.error as Error).message}</div>}
            <button className="button-link" type="submit" disabled={saveMutation.isPending}>{editingId === null ? 'Create cycle' : 'Save changes'}</button>
          </form>

          {selected.data && (
            <section className="panel cycle-preview">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">{selected.data.status}</p>
                  <h2>{selected.data.name}</h2>
                  <p>{selected.data.duration_days} days · {selected.data.start_date ? `Starts ${selected.data.start_date}` : 'No start date yet'}</p>
                </div>
                <div className="button-row">
                  <button type="button" className="button-secondary" onClick={startEdit}>Edit</button>
                  <button type="button" className="button-secondary" onClick={() => deleteMutation.mutate(selected.data!.id)}>Delete</button>
                </div>
              </div>
              <div className="cycle-grid">
                {slotGrid.map(({ day, slots }) => (
                  <div className="cycle-day" key={day}>
                    <h3>Day {day}</h3>
                    {slots.map((slot) => {
                      const definition = selected.data!.slot_definitions.find((item) => item.id === slot.slot_definition_id)
                      return <div className="cycle-slot" key={slot.id}>{definition?.label ?? 'Slot'}</div>
                    })}
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      </div>
    </section>
  )
}
