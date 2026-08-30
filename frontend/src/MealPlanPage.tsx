import { FormEvent, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchRecipes, fetchTags, type Recipe, type Tag } from './api'
import {
  assignPlannedMeal,
  createMealCycle,
  deleteMealCycle,
  fetchExpirationSuggestions,
  fetchMealCycle,
  fetchMealCycles,
  type MealCycleInput,
  type PlannedMeal,
  type PopulationRules,
  type SmartPlanningPreferences,
  movePlannedMeal,
  randomFillMealCycle,
  removePlannedMeal,
  setPlannedMealLock,
  updateMealCycle,
  updatePlannedMealPlanning,
  updatePopulationRules,
  updateSmartPlanningPreferences,
} from './mealCyclesApi'
import { fetchMeals, type Meal } from './mealsApi'
import './MealPlanPage.css'

const DEFAULT_SLOTS = ['Breakfast', 'Lunch', 'Dinner']

type PlanningInput = {
  planned_servings: string
  planned_leftover_servings: string
  component_serving_overrides: Record<number, string>
}

type RuleMode = 'ANY' | 'INCLUDE' | 'EXCLUDE'

function makeDraft(): MealCycleInput {
  return {
    name: '',
    duration_days: 7,
    start_date: null,
    notes: null,
    slot_definitions: DEFAULT_SLOTS.map((label, index) => ({ label, sort_order: index })),
  }
}

function emptyPopulationRules(): PopulationRules {
  return { include_meal_ids: [], exclude_meal_ids: [], slot_rules: {} }
}

function defaultSmartPreferences(): SmartPlanningPreferences {
  return { repeat_spacing_days: 0, favorite_boost: 1, history_penalty: 0, tag_weights: {} }
}

function normalizeSlotLabel(label: string): string {
  return label.trim().toLocaleLowerCase().replace(/\s+/g, ' ')
}

function parsePopulationRules(value: string): PopulationRules {
  try {
    const parsed = JSON.parse(value || '{}') as Partial<PopulationRules>
    return {
      include_meal_ids: parsed.include_meal_ids ?? [],
      exclude_meal_ids: parsed.exclude_meal_ids ?? [],
      slot_rules: parsed.slot_rules ?? {},
    }
  } catch {
    return emptyPopulationRules()
  }
}

function parseSmartPreferences(value: string): SmartPlanningPreferences {
  try {
    const parsed = JSON.parse(value || '{}') as Partial<SmartPlanningPreferences> & { tag_weights?: Record<string, number> }
    return {
      repeat_spacing_days: parsed.repeat_spacing_days ?? 0,
      favorite_boost: parsed.favorite_boost ?? 1,
      history_penalty: parsed.history_penalty ?? 0,
      tag_weights: Object.fromEntries(Object.entries(parsed.tag_weights ?? {}).map(([key, weight]) => [Number(key), Number(weight)])),
    }
  } catch {
    return defaultSmartPreferences()
  }
}

function ruleMode(includeIds: number[], excludeIds: number[], mealId: number): RuleMode {
  if (includeIds.includes(mealId)) return 'INCLUDE'
  if (excludeIds.includes(mealId)) return 'EXCLUDE'
  return 'ANY'
}

function applyRuleMode(includeIds: number[], excludeIds: number[], mealId: number, mode: RuleMode) {
  const include = includeIds.filter((id) => id !== mealId)
  const exclude = excludeIds.filter((id) => id !== mealId)
  if (mode === 'INCLUDE') include.push(mealId)
  if (mode === 'EXCLUDE') exclude.push(mealId)
  return { include_meal_ids: include, exclude_meal_ids: exclude }
}

function componentKey(component: { meal_recipe_id?: number; sort_order?: number }): number {
  return component.meal_recipe_id ?? -((component.sort_order ?? 0) + 1)
}

function PlanningControls({ placement, recipes, onSave, disabled }: { placement: PlannedMeal; recipes: Recipe[]; onSave: (input: PlanningInput) => void; disabled: boolean }) {
  const initialOverrides = useMemo(() => JSON.parse(placement.component_serving_overrides || '{}') as Record<string, string>, [placement.component_serving_overrides])
  const components = useMemo(() => JSON.parse(placement.snapshot_components || '[]') as Array<{ meal_recipe_id?: number; recipe_id: number; serving_multiplier: string; sort_order?: number }>, [placement.snapshot_components])
  const scaled = useMemo(() => JSON.parse(placement.scaled_components || '[]') as Array<{ meal_recipe_id: number; recipe_id: number; requested_servings: string }>, [placement.scaled_components])
  const [servings, setServings] = useState(placement.planned_servings)
  const [leftovers, setLeftovers] = useState(placement.planned_leftover_servings)
  const [overrides, setOverrides] = useState<Record<number, string>>(() => Object.fromEntries(Object.entries(initialOverrides).map(([key, value]) => [Number(key), value])))

  return (
    <details className="planning-controls">
      <summary>Plan quantities</summary>
      <div className="planning-grid">
        <label>Eat servings<input type="number" min="0.001" step="0.001" value={servings} onChange={(event) => setServings(event.target.value)} /></label>
        <label>Planned leftovers<input type="number" min="0" step="0.001" value={leftovers} onChange={(event) => setLeftovers(event.target.value)} /></label>
      </div>
      <p className="planning-note">Recipe requirements are calculated for {Number(servings || 0) + Number(leftovers || 0)} total servings to produce.</p>
      <details className="component-overrides">
        <summary>Component serving overrides</summary>
        <div className="component-override-list">
          {components.map((component) => {
            const key = componentKey(component)
            const recipe = recipes.find((item) => item.id === component.recipe_id)
            const calculated = scaled.find((item) => item.meal_recipe_id === key)?.requested_servings
            return (
              <label key={key}>
                <span>{recipe?.name ?? `Recipe ${component.recipe_id}`} <small>({calculated ?? '—'} calculated)</small></span>
                <input type="number" min="0.001" step="0.001" placeholder="Use calculated" value={overrides[key] ?? ''} onChange={(event) => {
                  const value = event.target.value
                  setOverrides((current) => {
                    const next = { ...current }
                    if (value) next[key] = value
                    else delete next[key]
                    return next
                  })
                }} />
              </label>
            )
          })}
        </div>
      </details>
      <button type="button" className="button-secondary" disabled={disabled || !servings || Number(servings) <= 0 || Number(leftovers) < 0} onClick={() => onSave({ planned_servings: servings, planned_leftover_servings: leftovers || '0', component_serving_overrides: overrides })}>Save quantities</button>
    </details>
  )
}

function PopulationRulesControls({ initialRules, meals, slotLabels, disabled, onSave }: { initialRules: PopulationRules; meals: Meal[]; slotLabels: string[]; disabled: boolean; onSave: (rules: PopulationRules) => void }) {
  const [rules, setRules] = useState<PopulationRules>(initialRules)

  function setGlobal(mealId: number, mode: RuleMode) {
    setRules((current) => ({ ...current, ...applyRuleMode(current.include_meal_ids, current.exclude_meal_ids, mealId, mode) }))
  }

  function setSlot(label: string, mealId: number, mode: RuleMode) {
    const key = normalizeSlotLabel(label)
    setRules((current) => {
      const existing = current.slot_rules[key] ?? { include_meal_ids: [], exclude_meal_ids: [] }
      return { ...current, slot_rules: { ...current.slot_rules, [key]: applyRuleMode(existing.include_meal_ids, existing.exclude_meal_ids, mealId, mode) } }
    })
  }

  return (
    <details className="population-rules">
      <summary>Population rules</summary>
      <p className="planning-note">Include creates an allow-list when at least one Meal is included. Exclude always removes a Meal. Slot rules narrow the cycle rule further.</p>
      <div className="population-rule-section">
        <h4>Whole cycle</h4>
        <div className="population-rule-list">
          {meals.map((meal) => <label key={meal.id}><span>{meal.name}</span><select value={ruleMode(rules.include_meal_ids, rules.exclude_meal_ids, meal.id)} onChange={(event) => setGlobal(meal.id, event.target.value as RuleMode)}><option value="ANY">Any</option><option value="INCLUDE">Include</option><option value="EXCLUDE">Exclude</option></select></label>)}
        </div>
      </div>
      {slotLabels.map((label) => {
        const key = normalizeSlotLabel(label)
        const slotRule = rules.slot_rules[key] ?? { include_meal_ids: [], exclude_meal_ids: [] }
        return (
          <details className="population-slot-rules" key={key}>
            <summary>{label} rules</summary>
            <div className="population-rule-list">
              {meals.map((meal) => <label key={meal.id}><span>{meal.name}</span><select value={ruleMode(slotRule.include_meal_ids, slotRule.exclude_meal_ids, meal.id)} onChange={(event) => setSlot(label, meal.id, event.target.value as RuleMode)}><option value="ANY">Any</option><option value="INCLUDE">Include</option><option value="EXCLUDE">Exclude</option></select></label>)}
            </div>
          </details>
        )
      })}
      <button type="button" className="button-secondary" disabled={disabled} onClick={() => onSave(rules)}>Save population rules</button>
    </details>
  )
}

function SmartPlanningControls({ initial, tags, disabled, onSave }: { initial: SmartPlanningPreferences; tags: Tag[]; disabled: boolean; onSave: (preferences: SmartPlanningPreferences) => void }) {
  const [preferences, setPreferences] = useState<SmartPlanningPreferences>(initial)

  return (
    <details className="population-rules smart-preferences">
      <summary>Smart planning preferences</summary>
      <p className="planning-note">These settings affect random selection after meal-type and population-pool eligibility are applied.</p>
      <div className="smart-preference-grid">
        <label>Repeat spacing (days)<input type="number" min="0" max="365" value={preferences.repeat_spacing_days} onChange={(event) => setPreferences({ ...preferences, repeat_spacing_days: Number(event.target.value) })} /></label>
        <label>Favorite boost<select value={preferences.favorite_boost} onChange={(event) => setPreferences({ ...preferences, favorite_boost: Number(event.target.value) })}><option value={1}>Off (1×)</option><option value={1.5}>1.5×</option><option value={2}>2×</option><option value={3}>3×</option></select></label>
        <label>History penalty<select value={preferences.history_penalty} onChange={(event) => setPreferences({ ...preferences, history_penalty: Number(event.target.value) })}><option value={0}>Off</option><option value={0.25}>Light</option><option value={0.5}>Medium</option><option value={1}>Strong</option></select></label>
      </div>
      <div className="population-rule-section">
        <h4>Tag preference weights</h4>
        <p className="planning-note">1× is neutral. Higher weights make Meals with that tag more likely when they are otherwise eligible.</p>
        <div className="population-rule-list">
          {tags.map((tag) => <label key={tag.id}><span>{tag.name}</span><select value={preferences.tag_weights[tag.id] ?? 1} onChange={(event) => {
            const weight = Number(event.target.value)
            setPreferences((current) => {
              const tag_weights = { ...current.tag_weights }
              if (weight === 1) delete tag_weights[tag.id]
              else tag_weights[tag.id] = weight
              return { ...current, tag_weights }
            })
          }}><option value={1}>1×</option><option value={1.5}>1.5×</option><option value={2}>2×</option><option value={3}>3×</option><option value={5}>5×</option></select></label>)}
        </div>
      </div>
      <button type="button" className="button-secondary" disabled={disabled} onClick={() => onSave(preferences)}>Save smart preferences</button>
    </details>
  )
}

export default function MealPlanPage() {
  const queryClient = useQueryClient()
  const cycles = useQuery({ queryKey: ['meal-cycles'], queryFn: fetchMealCycles })
  const meals = useQuery({ queryKey: ['meals', 'planner'], queryFn: () => fetchMeals() })
  const recipes = useQuery({ queryKey: ['recipes', 'planner'], queryFn: () => fetchRecipes() })
  const tags = useQuery({ queryKey: ['tags', 'planner'], queryFn: () => fetchTags() })
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const selected = useQuery({ queryKey: ['meal-cycle', selectedId], queryFn: () => fetchMealCycle(selectedId as number), enabled: selectedId !== null })
  const expiration = useQuery({
    queryKey: ['expiration-suggestions', selectedId],
    queryFn: () => fetchExpirationSuggestions(selectedId as number),
    enabled: selectedId !== null && Boolean(selected.data?.start_date),
    retry: false,
  })
  const [draft, setDraft] = useState<MealCycleInput>(makeDraft())
  const [editingId, setEditingId] = useState<number | null>(null)
  const [mealChoices, setMealChoices] = useState<Record<number, number>>({})
  const [moveTargets, setMoveTargets] = useState<Record<number, number>>({})

  const slotGrid = useMemo(() => {
    const cycle = selected.data
    if (!cycle) return []
    return Array.from({ length: cycle.duration_days }, (_, index) => {
      const day = index + 1
      return { day, slots: cycle.slots.filter((slot) => slot.day_number === day) }
    })
  }, [selected.data])

  async function refreshCycle(cycleId: number) {
    await queryClient.invalidateQueries({ queryKey: ['meal-cycles'] })
    await queryClient.invalidateQueries({ queryKey: ['meal-cycle', cycleId] })
    await queryClient.invalidateQueries({ queryKey: ['expiration-suggestions', cycleId] })
  }

  const saveMutation = useMutation({
    mutationFn: () => editingId === null ? createMealCycle(draft) : updateMealCycle(editingId, draft),
    onSuccess: async (cycle) => { await refreshCycle(cycle.id); setSelectedId(cycle.id); setEditingId(null); setDraft(makeDraft()) },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteMealCycle(id),
    onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ['meal-cycles'] }); setSelectedId(null); setEditingId(null); setDraft(makeDraft()) },
  })

  const populationMutation = useMutation({
    mutationFn: (rules: PopulationRules) => { if (selectedId === null) throw new Error('Select a cycle first'); return updatePopulationRules(selectedId, rules) },
    onSuccess: async () => { if (selectedId !== null) await refreshCycle(selectedId) },
  })

  const smartMutation = useMutation({
    mutationFn: (preferences: SmartPlanningPreferences) => { if (selectedId === null) throw new Error('Select a cycle first'); return updateSmartPlanningPreferences(selectedId, preferences) },
    onSuccess: async () => { if (selectedId !== null) await refreshCycle(selectedId) },
  })

  type PlacementAction =
    | { type: 'assign'; slotId: number; mealId: number }
    | { type: 'remove'; slotId: number }
    | { type: 'lock'; slotId: number; locked: boolean }
    | { type: 'move'; slotId: number; targetSlotId: number }
    | { type: 'planning'; slotId: number; input: PlanningInput }
    | { type: 'random' }

  const placementMutation = useMutation({
    mutationFn: async (action: PlacementAction) => {
      if (selectedId === null) throw new Error('Select a cycle first')
      if (action.type === 'assign') return assignPlannedMeal(selectedId, action.slotId, action.mealId)
      if (action.type === 'remove') return removePlannedMeal(selectedId, action.slotId)
      if (action.type === 'lock') return setPlannedMealLock(selectedId, action.slotId, action.locked)
      if (action.type === 'move') return movePlannedMeal(selectedId, action.slotId, action.targetSlotId)
      if (action.type === 'planning') return updatePlannedMealPlanning(selectedId, action.slotId, action.input)
      return randomFillMealCycle(selectedId)
    },
    onSuccess: async () => { if (selectedId !== null) await refreshCycle(selectedId) },
  })

  function startEdit() {
    if (!selected.data) return
    const cycle = selected.data
    setEditingId(cycle.id)
    setDraft({ name: cycle.name, duration_days: cycle.duration_days, start_date: cycle.start_date, notes: cycle.notes, slot_definitions: cycle.slot_definitions.map((slot) => ({ label: slot.label, sort_order: slot.sort_order })) })
  }

  function addSlot() { setDraft((current) => ({ ...current, slot_definitions: [...current.slot_definitions, { label: '', sort_order: current.slot_definitions.length }] })) }
  function updateSlot(index: number, label: string) { setDraft((current) => ({ ...current, slot_definitions: current.slot_definitions.map((slot, slotIndex) => slotIndex === index ? { ...slot, label } : slot) })) }
  function removeSlot(index: number) { setDraft((current) => ({ ...current, slot_definitions: current.slot_definitions.filter((_, slotIndex) => slotIndex !== index).map((slot, slotIndex) => ({ ...slot, sort_order: slotIndex })) })) }
  function moveSlot(index: number, direction: -1 | 1) {
    const target = index + direction
    if (target < 0 || target >= draft.slot_definitions.length) return
    const copy = [...draft.slot_definitions]
    ;[copy[index], copy[target]] = [copy[target], copy[index]]
    setDraft((current) => ({ ...current, slot_definitions: copy.map((slot, slotIndex) => ({ ...slot, sort_order: slotIndex })) }))
  }
  function submit(event: FormEvent) { event.preventDefault(); saveMutation.mutate() }

  const emptySlots = selected.data?.slots.filter((slot) => slot.planned_meal === null) ?? []

  return (
    <section className="meal-plan-page">
      <header className="page-heading"><div><p className="eyebrow">Cycle Planning</p><h1>Meal Plan</h1><p>Place Meals, configure smart population, set serving targets and planned leftovers, or fill eligible empty slots.</p></div></header>
      <div className="meal-plan-layout">
        <aside className="cycle-list panel">
          <h2>Cycles</h2>
          {cycles.data?.map((cycle) => <button type="button" className={selectedId === cycle.id ? 'cycle-select active' : 'cycle-select'} key={cycle.id} onClick={() => setSelectedId(cycle.id)}><strong>{cycle.name}</strong><span>{cycle.duration_days} days · {cycle.slot_definitions.length} slots/day</span></button>)}
          {!cycles.isPending && cycles.data?.length === 0 && <p>No cycles yet.</p>}
        </aside>
        <div className="cycle-workspace">
          <form className="panel cycle-editor" onSubmit={submit}>
            <div className="section-heading"><h2>{editingId === null ? 'New cycle' : 'Edit cycle'}</h2>{editingId !== null && <button type="button" className="button-secondary" onClick={() => { setEditingId(null); setDraft(makeDraft()) }}>Cancel edit</button>}</div>
            <div className="form-grid">
              <label>Cycle name<input required value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></label>
              <label>Duration (days)<input type="number" min="1" max="365" required value={draft.duration_days} onChange={(event) => setDraft({ ...draft, duration_days: Number(event.target.value) })} /></label>
              <label>Start date (optional)<input type="date" value={draft.start_date ?? ''} onChange={(event) => setDraft({ ...draft, start_date: event.target.value || null })} /></label>
              <label className="wide-field">Notes<textarea value={draft.notes ?? ''} onChange={(event) => setDraft({ ...draft, notes: event.target.value || null })} /></label>
            </div>
            <div className="section-heading"><h3>Meal slots</h3><button type="button" className="button-secondary" onClick={addSlot}>Add slot</button></div>
            <div className="slot-editor-list">{draft.slot_definitions.map((slot, index) => <div className="slot-editor-row" key={`${index}-${slot.sort_order}`}><span className="slot-order">{index + 1}</span><input required placeholder="Slot label" value={slot.label} onChange={(event) => updateSlot(index, event.target.value)} /><button type="button" className="button-secondary" disabled={index === 0} onClick={() => moveSlot(index, -1)}>↑</button><button type="button" className="button-secondary" disabled={index === draft.slot_definitions.length - 1} onClick={() => moveSlot(index, 1)}>↓</button><button type="button" className="button-secondary" disabled={draft.slot_definitions.length === 1} onClick={() => removeSlot(index)}>Remove</button></div>)}</div>
            {saveMutation.isError && <div className="error-banner">{(saveMutation.error as Error).message}</div>}
            <button className="button-link" type="submit" disabled={saveMutation.isPending}>{editingId === null ? 'Create cycle' : 'Save changes'}</button>
          </form>
          {selected.data && (
            <section className="panel cycle-preview">
              <div className="section-heading">
                <div><p className="eyebrow">{selected.data.status}</p><h2>{selected.data.name}</h2><p>{selected.data.duration_days} days · {selected.data.start_date ? `Starts ${selected.data.start_date}` : 'No start date yet'}</p></div>
                <div className="button-row"><button type="button" className="button-secondary" onClick={() => placementMutation.mutate({ type: 'random' })}>Random fill empty</button><button type="button" className="button-secondary" onClick={startEdit}>Edit cycle</button><button type="button" className="button-secondary" onClick={() => deleteMutation.mutate(selected.data!.id)}>Delete cycle</button></div>
              </div>
              <PopulationRulesControls key={`${selected.data.id}-${selected.data.population_rules}`} initialRules={parsePopulationRules(selected.data.population_rules)} meals={meals.data ?? []} slotLabels={selected.data.slot_definitions.map((slot) => slot.label)} disabled={populationMutation.isPending} onSave={(rules) => populationMutation.mutate(rules)} />
              <SmartPlanningControls key={`${selected.data.id}-${selected.data.smart_preferences}`} initial={parseSmartPreferences(selected.data.smart_preferences)} tags={tags.data ?? []} disabled={smartMutation.isPending} onSave={(preferences) => smartMutation.mutate(preferences)} />
              <section className="expiration-suggestions">
                <div className="section-heading">
                  <div><h3>Expiration-aware suggestions</h3><p className="planning-note">Uses dated Inventory lots and the cycle start date to identify Meals that can use expiring ingredients sooner.</p></div>
                  {selected.data.start_date && <button type="button" className="button-secondary" disabled={expiration.isFetching} onClick={() => expiration.refetch()}>Refresh suggestions</button>}
                </div>
                {!selected.data.start_date && <div className="planning-warning">Set a cycle start date to evaluate expiration timing.</div>}
                {selected.data.start_date && expiration.isPending && <p className="planning-note">Checking expiring Inventory…</p>}
                {selected.data.start_date && expiration.isError && <div className="error-banner">{(expiration.error as Error).message}</div>}
                {selected.data.start_date && expiration.data?.suggestions.length === 0 && <p className="planning-note">No planned Meals currently match usable dated Inventory before expiration.</p>}
                <div className="expiration-suggestion-list">
                  {expiration.data?.suggestions.map((suggestion) => (
                    <article className="expiration-suggestion-card" key={suggestion.planned_meal_id}>
                      <div className="expiration-suggestion-heading"><strong>{suggestion.meal_name}</strong><span>Day {suggestion.day_number} · {suggestion.planned_date}</span></div>
                      <div className="expiration-match-list">
                        {suggestion.expiring_matches.map((match) => <div key={`${match.inventory_lot_id}-${match.ingredient_id}`}><strong>{match.ingredient_name}</strong><span>Lot #{match.inventory_lot_id}: {match.usable_quantity} {match.unit_code} usable · expires {match.expiration_date} ({match.days_until_expiration_on_planned_date} days after planned date)</span></div>)}
                      </div>
                      {suggestion.can_move_earlier && <p className="expiration-action">Earlier empty same-slot day{suggestion.suggested_empty_day_numbers.length === 1 ? '' : 's'}: {suggestion.suggested_empty_day_numbers.join(', ')}</p>}
                      {suggestion.can_swap_earlier && <p className="expiration-action">Earlier unlocked same-slot swap day{suggestion.suggested_swap_day_numbers.length === 1 ? '' : 's'}: {suggestion.suggested_swap_day_numbers.join(', ')}</p>}
                      {!suggestion.can_move_earlier && !suggestion.can_swap_earlier && <p className="planning-note">No earlier same-slot move or unlocked swap opportunity is currently available.</p>}
                    </article>
                  ))}
                </div>
              </section>
              {populationMutation.isError && <div className="error-banner">{(populationMutation.error as Error).message}</div>}
              {smartMutation.isError && <div className="error-banner">{(smartMutation.error as Error).message}</div>}
              {placementMutation.isError && <div className="error-banner">{(placementMutation.error as Error).message}</div>}
              <div className="cycle-grid">
                {slotGrid.map(({ day, slots }) => (
                  <div className="cycle-day" key={day}><h3>Day {day}</h3>{slots.map((slot) => {
                    const definition = selected.data!.slot_definitions.find((item) => item.id === slot.slot_definition_id)
                    const placement = slot.planned_meal
                    return (
                      <div className={placement?.locked ? 'cycle-slot planned locked' : placement ? 'cycle-slot planned' : 'cycle-slot'} key={slot.id}>
                        <strong>{definition?.label ?? 'Slot'}</strong>
                        {placement ? (
                          <div className="placement-card">
                            <span>{placement.snapshot_name}</span>
                            <small>{placement.planned_servings} servings + {placement.planned_leftover_servings} leftover · {placement.locked ? 'Locked' : 'Unlocked'}</small>
                            <PlanningControls key={`${placement.id}-${placement.planned_servings}-${placement.planned_leftover_servings}-${placement.component_serving_overrides}`} placement={placement} recipes={recipes.data ?? []} disabled={placementMutation.isPending} onSave={(input) => placementMutation.mutate({ type: 'planning', slotId: slot.id, input })} />
                            <div className="placement-actions"><button type="button" className="button-secondary" onClick={() => placementMutation.mutate({ type: 'lock', slotId: slot.id, locked: !placement.locked })}>{placement.locked ? 'Unlock' : 'Lock'}</button><button type="button" className="button-secondary" disabled={placement.locked} onClick={() => placementMutation.mutate({ type: 'remove', slotId: slot.id })}>Remove</button></div>
                            {!placement.locked && emptySlots.length > 0 && <div className="move-control"><select value={moveTargets[slot.id] ?? ''} onChange={(event) => setMoveTargets({ ...moveTargets, [slot.id]: Number(event.target.value) })}><option value="">Move to…</option>{emptySlots.map((target) => { const targetDefinition = selected.data!.slot_definitions.find((item) => item.id === target.slot_definition_id); return <option key={target.id} value={target.id}>Day {target.day_number} · {targetDefinition?.label ?? 'Slot'}</option> })}</select><button type="button" className="button-secondary" disabled={!moveTargets[slot.id]} onClick={() => placementMutation.mutate({ type: 'move', slotId: slot.id, targetSlotId: moveTargets[slot.id] })}>Move</button></div>}
                          </div>
                        ) : (
                          <div className="assign-control"><select value={mealChoices[slot.id] ?? ''} onChange={(event) => setMealChoices({ ...mealChoices, [slot.id]: Number(event.target.value) })}><option value="">Choose meal…</option>{meals.data?.map((meal) => <option key={meal.id} value={meal.id}>{meal.name}</option>)}</select><button type="button" className="button-secondary" disabled={!mealChoices[slot.id]} onClick={() => placementMutation.mutate({ type: 'assign', slotId: slot.id, mealId: mealChoices[slot.id] })}>Place</button></div>
                        )}
                      </div>
                    )
                  })}</div>
                ))}
              </div>
            </section>
          )}
        </div>
      </div>
    </section>
  )
}
