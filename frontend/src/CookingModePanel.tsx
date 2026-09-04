import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { fetchMealCycles } from './mealCyclesApi'
import { fetchCycleCookingMode, updateCookingTimer, type CookingTimerRuntime } from './cookingApi'

function quantity(value: string): string {
  const number = Number(value)
  if (!Number.isFinite(number)) return value
  return number.toLocaleString(undefined, { useGrouping: false, maximumFractionDigits: 6 })
}

function timerRemaining(timer: CookingTimerRuntime, nowSeconds: number): number {
  if (timer.status !== 'RUNNING' || timer.ends_at_epoch === null) return timer.remaining_seconds
  return Math.max(timer.ends_at_epoch - nowSeconds, 0)
}

function timerText(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  const remainder = seconds % 60
  return `${minutes}:${String(remainder).padStart(2, '0')}`
}

export default function CookingModePanel() {
  const cycles = useQuery({ queryKey: ['meal-cycles'], queryFn: fetchMealCycles })
  const [selectedCycleId, setSelectedCycleId] = useState<number | null>(null)
  const effectiveCycleId = selectedCycleId ?? cycles.data?.[0]?.id ?? null
  const cooking = useQuery({ queryKey: ['cycle-cooking-mode', effectiveCycleId], queryFn: () => fetchCycleCookingMode(effectiveCycleId as number), enabled: effectiveCycleId !== null })
  const lastCycleDataUpdatedAt = useRef(cycles.dataUpdatedAt)
  const [plannedMealId, setPlannedMealId] = useState<number | null>(null)
  const [stepIndex, setStepIndex] = useState(0)
  const [nowSeconds, setNowSeconds] = useState(() => Math.floor(Date.now() / 1000))

  const selectedMeal = useMemo(() => {
    const meals = cooking.data?.meals ?? []
    return meals.find((meal) => meal.planned_meal_id === plannedMealId) ?? meals[0] ?? null
  }, [cooking.data, plannedMealId])

  const hasRunningTimer = useMemo(() => cooking.data?.meals.some((meal) => meal.steps.some((item) => item.timers.some((timer) => timer.status === 'RUNNING'))) ?? false, [cooking.data])

  useEffect(() => {
    if (!hasRunningTimer) return
    const id = window.setInterval(() => setNowSeconds(Math.floor(Date.now() / 1000)), 1000)
    return () => window.clearInterval(id)
  }, [hasRunningTimer])

  useEffect(() => {
    if (cycles.dataUpdatedAt === 0 || cycles.dataUpdatedAt === lastCycleDataUpdatedAt.current) return
    const previousUpdatedAt = lastCycleDataUpdatedAt.current
    lastCycleDataUpdatedAt.current = cycles.dataUpdatedAt
    if (previousUpdatedAt !== 0 && effectiveCycleId !== null) void cooking.refetch()
  }, [cycles.dataUpdatedAt, effectiveCycleId, cooking.refetch])

  useEffect(() => { setStepIndex(0) }, [selectedMeal?.planned_meal_id])
  const step = selectedMeal?.steps[stepIndex] ?? null

  const timerMutation = useMutation({
    mutationFn: ({ timerId, action }: { timerId: number; action: 'START' | 'PAUSE' | 'RESUME' | 'RESET' | 'DISMISS' }) => {
      if (!selectedMeal) throw new Error('Select a planned Meal first')
      return updateCookingTimer(selectedMeal.planned_meal_id, timerId, action)
    },
    onSuccess: async () => { setNowSeconds(Math.floor(Date.now() / 1000)); await cooking.refetch() },
  })

  return <section className="panel" style={{ marginTop: 20 }}>
    <div className="section-heading">
      <div><h2>Cooking Mode</h2><p className="planning-note">Focused step-by-step execution with equipment, temperature guidance, and persistent timers.</p></div>
      <div className="header-actions">
        <select value={effectiveCycleId ?? ''} onChange={(event) => { setSelectedCycleId(event.target.value ? Number(event.target.value) : null); setPlannedMealId(null) }}><option value="">Select cycle</option>{cycles.data?.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.name}</option>)}</select>
        <select value={selectedMeal?.planned_meal_id ?? ''} onChange={(event) => setPlannedMealId(event.target.value ? Number(event.target.value) : null)}><option value="">Select planned Meal</option>{cooking.data?.meals.map((meal) => <option key={meal.planned_meal_id} value={meal.planned_meal_id}>Day {meal.day_number} · {meal.slot_label} · {meal.meal_name}</option>)}</select>
      </div>
    </div>
    {cooking.error instanceof Error && <div className="error-banner">{cooking.error.message}</div>}
    {timerMutation.error instanceof Error && <div className="error-banner">{timerMutation.error.message}</div>}
    {selectedMeal && <>
      <div className="ingredient-meta"><span>{selectedMeal.meal_name}</span><span>{quantity(selectedMeal.planned_servings)} eating + {quantity(selectedMeal.planned_leftover_servings)} leftover servings</span></div>
      {selectedMeal.components_without_steps.length > 0 && <p className="planning-note">No cooking steps: {selectedMeal.components_without_steps.join(', ')}</p>}
      {step ? <div className="recipe-ingredient-editor" style={{ marginTop: 12 }}>
        <div className="section-heading"><div><p className="eyebrow">Step {step.step_number} of {step.total_steps}</p><h3>{step.title}</h3><p className="planning-note">{step.recipe_name}{step.prep_group_name ? ` · ${step.prep_group_name}` : ''}</p></div></div>
        {step.instructions && <p>{step.instructions}</p>}

        {(step.equipment.length > 0 || step.temperatures.length > 0) && <div className="recipe-ingredient-list" style={{ marginBottom: 12 }}>
          {step.equipment.map((item) => <div className="ingredient-row" key={`equipment-${item.recipe_equipment_id}`}><strong>Equipment: {item.quantity} × {item.equipment_name}</strong>{item.notes && <div className="ingredient-meta"><span>{item.notes}</span></div>}</div>)}
          {step.temperatures.map((item) => <div className="ingredient-row" key={`temperature-${item.id}`}><strong>{item.label}: {quantity(String(item.value))}°{item.unit}</strong>{item.notes && <div className="ingredient-meta"><span>{item.notes}</span></div>}</div>)}
        </div>}

        <div className="recipe-ingredient-list">{step.ingredients.map((ingredient) => <div className="ingredient-row" key={`${step.step_id}-${ingredient.ingredient_id}`}><strong>{ingredient.ingredient_name}</strong><div className="ingredient-meta"><span>{quantity(ingredient.quantity)} {ingredient.unit_code}</span>{ingredient.prep_method && <span>{ingredient.prep_method}</span>}{ingredient.prep_size && <span>{ingredient.prep_size}</span>}{ingredient.prep_state && <span>{ingredient.prep_state}</span>}</div></div>)}</div>
        {step.timers.length > 0 && <div className="recipe-ingredient-list" style={{ marginTop: 12 }}>{step.timers.map((timer) => {
          const remaining = timerRemaining(timer, nowSeconds)
          const effectiveStatus = timer.status === 'RUNNING' && remaining === 0 ? 'COMPLETED' : timer.status
          return <div className="ingredient-row" key={timer.timer_id}>
            <strong>{timer.label}</strong>
            <div className="ingredient-meta"><span>{timerText(remaining)}</span><span>{effectiveStatus}</span>{timer.notes && <span>{timer.notes}</span>}</div>
            <div className="header-actions">
              {(effectiveStatus === 'READY' || effectiveStatus === 'COMPLETED') && <button type="button" disabled={timerMutation.isPending} onClick={() => timerMutation.mutate({ timerId: timer.timer_id, action: 'START' })}>{effectiveStatus === 'COMPLETED' ? 'Restart' : 'Start'}</button>}
              {effectiveStatus === 'RUNNING' && <button type="button" className="button-secondary" disabled={timerMutation.isPending} onClick={() => timerMutation.mutate({ timerId: timer.timer_id, action: 'PAUSE' })}>Pause</button>}
              {effectiveStatus === 'PAUSED' && <button type="button" disabled={timerMutation.isPending} onClick={() => timerMutation.mutate({ timerId: timer.timer_id, action: 'RESUME' })}>Resume</button>}
              <button type="button" className="button-secondary" disabled={timerMutation.isPending} onClick={() => timerMutation.mutate({ timerId: timer.timer_id, action: 'RESET' })}>Reset</button>
              {effectiveStatus === 'COMPLETED' && <button type="button" className="button-secondary" disabled={timerMutation.isPending} onClick={() => timerMutation.mutate({ timerId: timer.timer_id, action: 'DISMISS' })}>Dismiss</button>}
            </div>
          </div>
        })}</div>}
        <div className="header-actions"><button type="button" className="button-secondary" disabled={stepIndex === 0} onClick={() => setStepIndex((value) => Math.max(0, value - 1))}>Previous</button><button type="button" disabled={stepIndex >= selectedMeal.steps.length - 1} onClick={() => setStepIndex((value) => Math.min(selectedMeal.steps.length - 1, value + 1))}>Next</button></div>
      </div> : <p className="muted-line">This planned Meal has no cooking steps yet.</p>}
    </>}
    {!cooking.isPending && cooking.data?.meals.length === 0 && <p className="muted-line">No planned Meals in this cycle.</p>}
  </section>
}
