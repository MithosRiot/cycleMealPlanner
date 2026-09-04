import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { fetchEquipment, fetchRecipe } from './api'
import { fetchCookingSteps, saveCookingSteps, type CookingStepInput, type CookingTemperatureInput, type CookingTimerInput } from './cookingApi'

function normalizeTimers(items: CookingTimerInput[]): CookingTimerInput[] {
  return items.map((item, index) => ({ ...item, sort_order: index }))
}

function normalizeTemperatures(items: CookingTemperatureInput[]): CookingTemperatureInput[] {
  return items.map((item, index) => ({ ...item, sort_order: index }))
}

function normalize(items: CookingStepInput[]): CookingStepInput[] {
  return items.map((item, index) => ({
    ...item,
    sort_order: index,
    timers: normalizeTimers(item.timers),
    temperatures: normalizeTemperatures(item.temperatures),
  }))
}

export default function RecipeCookingStepsPanel() {
  const { recipeId } = useParams()
  const id = Number(recipeId)
  const queryClient = useQueryClient()
  const recipe = useQuery({ queryKey: ['recipe', id], queryFn: () => fetchRecipe(id), enabled: Number.isFinite(id) })
  const equipment = useQuery({ queryKey: ['equipment', 'cooking-steps'], queryFn: () => fetchEquipment(true) })
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
      recipe_equipment_ids: item.equipment.map((row) => row.recipe_equipment_id),
      temperatures: item.temperatures.map((temperature) => ({ label: temperature.label, value: String(temperature.value), unit: temperature.unit, notes: temperature.notes, sort_order: temperature.sort_order })),
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
        recipe_equipment_ids: item.equipment.map((row) => row.recipe_equipment_id),
        temperatures: item.temperatures.map((temperature) => ({ label: temperature.label, value: String(temperature.value), unit: temperature.unit, notes: temperature.notes, sort_order: temperature.sort_order })),
      })))
      await queryClient.invalidateQueries({ queryKey: ['recipe-cooking-steps', id] })
      await queryClient.invalidateQueries({ queryKey: ['cycle-cooking-mode'] })
    },
  })

  if (!Number.isFinite(id)) return null
  const items = draft ?? []
  const groups = recipe.data?.prep_groups ?? []
  const recipeEquipment = recipe.data?.equipment ?? []
  const equipmentNames = new Map((equipment.data ?? []).map((item) => [item.id, item.name]))

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
  function patchTemperature(stepIndex: number, temperatureIndex: number, update: Partial<CookingTemperatureInput>) {
    const temperatures = items[stepIndex].temperatures.map((temperature, current) => current === temperatureIndex ? { ...temperature, ...update } : temperature)
    patch(stepIndex, { temperatures })
  }
  function moveTemperature(stepIndex: number, temperatureIndex: number, offset: -1 | 1) {
    const temperatures = [...items[stepIndex].temperatures]
    const target = temperatureIndex + offset
    if (target < 0 || target >= temperatures.length) return
    ;[temperatures[temperatureIndex], temperatures[target]] = [temperatures[target], temperatures[temperatureIndex]]
    patch(stepIndex, { temperatures: normalizeTemperatures(temperatures) })
  }

  return <section className="panel" style={{ marginTop: 20 }}>
    <div className="section-heading">
      <div><h2>Cooking steps</h2><p className="planning-note">Ordered steps used by Cooking Mode. Add timers, Recipe equipment, and temperature cues where they are needed.</p></div>
      <button type="button" onClick={() => setDraft([...items, { title: `Step ${items.length + 1}`, instructions: null, prep_group_id: null, sort_order: items.length, timers: [], recipe_equipment_ids: [], temperatures: [] }])}>Add step</button>
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

        <div className="section-heading"><h4>Equipment</h4></div>
        {recipeEquipment.length === 0 ? <p className="muted-line">This Recipe has no equipment requirements. Add equipment to the Recipe before assigning it to a cooking step.</p> : <div className="recipe-ingredient-list">
          {recipeEquipment.map((requirement) => <label className="ingredient-row" key={requirement.id}>
            <input type="checkbox" checked={item.recipe_equipment_ids.includes(requirement.id)} onChange={(event) => patch(index, { recipe_equipment_ids: event.target.checked ? [...item.recipe_equipment_ids, requirement.id] : item.recipe_equipment_ids.filter((value) => value !== requirement.id) })} />
            <strong>{requirement.quantity} × {equipmentNames.get(requirement.equipment_id) ?? `Equipment ${requirement.equipment_id}`}</strong>
            {requirement.notes && <span className="planning-note">{requirement.notes}</span>}
          </label>)}
        </div>}

        <div className="section-heading"><h4>Temperatures</h4><button type="button" className="button-secondary" onClick={() => patch(index, { temperatures: [...item.temperatures, { label: 'Oven', value: '350', unit: 'F', notes: null, sort_order: item.temperatures.length }] })}>Add temperature</button></div>
        {item.temperatures.map((temperature, temperatureIndex) => <div className="advanced-grid" key={temperatureIndex}>
          <label>Label<input required value={temperature.label} onChange={(event) => patchTemperature(index, temperatureIndex, { label: event.target.value })} /></label>
          <label>Temperature<input type="number" step="0.1" required value={temperature.value} onChange={(event) => patchTemperature(index, temperatureIndex, { value: event.target.value })} /></label>
          <label>Unit<select value={temperature.unit} onChange={(event) => patchTemperature(index, temperatureIndex, { unit: event.target.value as 'F' | 'C' })}><option value="F">°F</option><option value="C">°C</option></select></label>
          <label>Notes<input value={temperature.notes ?? ''} onChange={(event) => patchTemperature(index, temperatureIndex, { notes: event.target.value || null })} /></label>
          <div className="header-actions span-2"><button type="button" className="button-secondary" disabled={temperatureIndex === 0} onClick={() => moveTemperature(index, temperatureIndex, -1)}>Temperature up</button><button type="button" className="button-secondary" disabled={temperatureIndex === item.temperatures.length - 1} onClick={() => moveTemperature(index, temperatureIndex, 1)}>Temperature down</button><button type="button" className="button-secondary" onClick={() => patch(index, { temperatures: normalizeTemperatures(item.temperatures.filter((_temperature, current) => current !== temperatureIndex)) })}>Remove temperature</button></div>
        </div>)}

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
    <button type="button" disabled={save.isPending || items.some((item) => !item.title.trim() || item.timers.some((timer) => !timer.label.trim() || timer.duration_seconds <= 0) || item.temperatures.some((temperature) => !temperature.label.trim() || temperature.value === ''))} onClick={() => save.mutate()}>Save cooking steps</button>
  </section>
}
