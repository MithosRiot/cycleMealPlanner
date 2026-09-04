import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { fetchRecipe } from './api'
import { fetchCookingSteps, saveCookingSteps, type CookingStepInput, type CookingTimerInput } from './cookingApi'

function normalizeTimers(items: CookingTimerInput[]): CookingTimerInput[] {
  return items.map((item, index) => ({ ...item, sort_order: index }))
}

function normalize(items: CookingStepInput[]): CookingStepInput[] {
  return items.map((item, index) => ({ ...item, sort_order: index, timers: normalizeTimers(item.timers) }))
}

export default function RecipeCookingStepsPanel() {
  const { recipeId } = useParams()
  const id = Number(recipeId)
  const queryClient = useQueryClient()
  const recipe = useQuery({ queryKey: ['recipe', id], queryFn: () => fetchRecipe(id), enabled: Number.isFinite(id) })
  const steps = useQuery({ queryKey: ['recipe-cooking-steps', id], queryFn: () => fetchCookingSteps(id), enabled: Number.isFinite(id) })
  const [draft, setDraft] = useState<CookingStepInput[] | null>(null)

  useEffect(() => {
    if (!steps.data) return
    setDraft(steps.data.map((item) => ({
      title: item.title,
      instructions: item.instructions,
      prep_group_id: item.prep_group_id,
      sort_order: item.sort_order,
      timers: item.timers.map((timer) => ({ label: timer.label, duration_seconds: timer.duration_seconds, notes: timer.notes, sort_order: timer.sort_order })),
    })))
  }, [steps.data])

  const save = useMutation({
    mutationFn: () => saveCookingSteps(id, normalize(draft ?? [])),
    onSuccess: async (saved) => {
      setDraft(saved.map((item) => ({
        title: item.title,
        instructions: item.instructions,
        prep_group_id: item.prep_group_id,
        sort_order: item.sort_order,
        timers: item.timers.map((timer) => ({ label: timer.label, duration_seconds: timer.duration_seconds, notes: timer.notes, sort_order: timer.sort_order })),
      })))
      await queryClient.invalidateQueries({ queryKey: ['recipe-cooking-steps', id] })
      await queryClient.invalidateQueries({ queryKey: ['cycle-cooking-mode'] })
    },
  })

  if (!Number.isFinite(id)) return null
  const items = draft ?? []
  const groups = recipe.data?.prep_groups ?? []

  function patch(index: number, update: Partial<CookingStepInput>) {
    setDraft(items.map((item, current) => current === index ? { ...item, ...update } : item))
  }
  function move(index: number, offset: -1 | 1) {
    const target = index + offset
    if (target < 0 || target >= items.length) return
    const copy = [...items]
    ;[copy[index], copy[target]] = [copy[target], copy[index]]
    setDraft(normalize(copy))
  }
  function patchTimer(stepIndex: number, timerIndex: number, update: Partial<CookingTimerInput>) {
    const timers = items[stepIndex].timers.map((timer, current) => current === timerIndex ? { ...timer, ...update } : timer)
    patch(stepIndex, { timers })
  }
  function moveTimer(stepIndex: number, timerIndex: number, offset: -1 | 1) {
    const timers = [...items[stepIndex].timers]
    const target = timerIndex + offset
    if (target < 0 || target >= timers.length) return
    ;[timers[timerIndex], timers[target]] = [timers[target], timers[timerIndex]]
    patch(stepIndex, { timers: normalizeTimers(timers) })
  }

  return <section className="panel" style={{ marginTop: 20 }}>
    <div className="section-heading">
      <div><h2>Cooking steps</h2><p className="planning-note">Ordered steps used by Cooking Mode. Optional timers can run concurrently while you move between steps.</p></div>
      <button type="button" onClick={() => setDraft([...items, { title: `Step ${items.length + 1}`, instructions: null, prep_group_id: null, sort_order: items.length, timers: [] }])}>Add step</button>
    </div>
    {steps.error instanceof Error && <div className="error-banner">{steps.error.message}</div>}
    {save.error instanceof Error && <div className="error-banner">{save.error.message}</div>}
    <div className="recipe-ingredient-list">
      {items.map((item, index) => <div className="recipe-ingredient-editor" key={index}>
        <div className="advanced-grid">
          <label>Title<input required value={item.title} onChange={(event) => patch(index, { title: event.target.value })} /></label>
          <label>Prep group<select value={item.prep_group_id ?? ''} onChange={(event) => patch(index, { prep_group_id: event.target.value ? Number(event.target.value) : null })}><option value="">All component ingredients</option>{groups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}</select></label>
          <label className="span-2">Instructions<textarea value={item.instructions ?? ''} onChange={(event) => patch(index, { instructions: event.target.value || null })} /></label>
        </div>
        <div className="section-heading"><h4>Timers</h4><button type="button" className="button-secondary" onClick={() => patch(index, { timers: [...item.timers, { label: `Timer ${item.timers.length + 1}`, duration_seconds: 300, notes: null, sort_order: item.timers.length }] })}>Add timer</button></div>
        {item.timers.map((timer, timerIndex) => <div className="advanced-grid" key={timerIndex}>
          <label>Timer label<input required value={timer.label} onChange={(event) => patchTimer(index, timerIndex, { label: event.target.value })} /></label>
          <label>Duration (minutes)<input type="number" min="0.0167" step="0.5" value={timer.duration_seconds / 60} onChange={(event) => patchTimer(index, timerIndex, { duration_seconds: Math.max(1, Math.round(Number(event.target.value) * 60)) })} /></label>
          <label className="span-2">Timer notes<textarea value={timer.notes ?? ''} onChange={(event) => patchTimer(index, timerIndex, { notes: event.target.value || null })} /></label>
          <div className="header-actions span-2"><button type="button" className="button-secondary" disabled={timerIndex === 0} onClick={() => moveTimer(index, timerIndex, -1)}>Timer up</button><button type="button" className="button-secondary" disabled={timerIndex === item.timers.length - 1} onClick={() => moveTimer(index, timerIndex, 1)}>Timer down</button><button type="button" className="button-secondary" onClick={() => patch(index, { timers: normalizeTimers(item.timers.filter((_timer, current) => current !== timerIndex)) })}>Remove timer</button></div>
        </div>)}
        <div className="header-actions"><button type="button" className="button-secondary" disabled={index === 0} onClick={() => move(index, -1)}>Move up</button><button type="button" className="button-secondary" disabled={index === items.length - 1} onClick={() => move(index, 1)}>Move down</button><button type="button" className="button-secondary" onClick={() => setDraft(normalize(items.filter((_item, current) => current !== index)))}>Remove</button></div>
      </div>)}
    </div>
    {!steps.isPending && items.length === 0 && <p className="muted-line">No cooking steps yet.</p>}
    <button type="button" disabled={save.isPending || items.some((item) => !item.title.trim() || item.timers.some((timer) => !timer.label.trim() || timer.duration_seconds <= 0))} onClick={() => save.mutate()}>Save cooking steps</button>
  </section>
}
