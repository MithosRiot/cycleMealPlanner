import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchMealCycles } from './mealCyclesApi'
import { fetchCycleCookingMode } from './cookingApi'

function quantity(value: string): string {
  const number = Number(value)
  if (!Number.isFinite(number)) return value
  return number.toLocaleString(undefined, { useGrouping: false, maximumFractionDigits: 6 })
}

export default function CookingModePanel() {
  const cycles = useQuery({ queryKey: ['meal-cycles'], queryFn: fetchMealCycles })
  const [selectedCycleId, setSelectedCycleId] = useState<number | null>(null)
  const effectiveCycleId = selectedCycleId ?? cycles.data?.[0]?.id ?? null
  const cooking = useQuery({ queryKey: ['cycle-cooking-mode', effectiveCycleId], queryFn: () => fetchCycleCookingMode(effectiveCycleId as number), enabled: effectiveCycleId !== null })
  const lastCycleDataUpdatedAt = useRef(cycles.dataUpdatedAt)
  const [plannedMealId, setPlannedMealId] = useState<number | null>(null)
  const [stepIndex, setStepIndex] = useState(0)

  const selectedMeal = useMemo(() => {
    const meals = cooking.data?.meals ?? []
    return meals.find((meal) => meal.planned_meal_id === plannedMealId) ?? meals[0] ?? null
  }, [cooking.data, plannedMealId])

  useEffect(() => {
    if (cycles.dataUpdatedAt === 0 || cycles.dataUpdatedAt === lastCycleDataUpdatedAt.current) return
    const previousUpdatedAt = lastCycleDataUpdatedAt.current
    lastCycleDataUpdatedAt.current = cycles.dataUpdatedAt
    if (previousUpdatedAt !== 0 && effectiveCycleId !== null) void cooking.refetch()
  }, [cycles.dataUpdatedAt, effectiveCycleId, cooking.refetch])

  useEffect(() => { setStepIndex(0) }, [selectedMeal?.planned_meal_id])
  const step = selectedMeal?.steps[stepIndex] ?? null

  return <section className="panel" style={{ marginTop: 20 }}>
    <div className="section-heading">
      <div><h2>Cooking Mode</h2><p className="planning-note">Focused step-by-step execution for one planned Meal. Navigation is read-only.</p></div>
      <div className="header-actions">
        <select value={effectiveCycleId ?? ''} onChange={(event) => { setSelectedCycleId(event.target.value ? Number(event.target.value) : null); setPlannedMealId(null) }}><option value="">Select cycle</option>{cycles.data?.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.name}</option>)}</select>
        <select value={selectedMeal?.planned_meal_id ?? ''} onChange={(event) => setPlannedMealId(event.target.value ? Number(event.target.value) : null)}><option value="">Select planned Meal</option>{cooking.data?.meals.map((meal) => <option key={meal.planned_meal_id} value={meal.planned_meal_id}>Day {meal.day_number} · {meal.slot_label} · {meal.meal_name}</option>)}</select>
      </div>
    </div>
    {cooking.error instanceof Error && <div className="error-banner">{cooking.error.message}</div>}
    {selectedMeal && <>
      <div className="ingredient-meta"><span>{selectedMeal.meal_name}</span><span>{quantity(selectedMeal.planned_servings)} eating + {quantity(selectedMeal.planned_leftover_servings)} leftover servings</span></div>
      {selectedMeal.components_without_steps.length > 0 && <p className="planning-note">No cooking steps: {selectedMeal.components_without_steps.join(', ')}</p>}
      {step ? <div className="recipe-ingredient-editor" style={{ marginTop: 12 }}>
        <div className="section-heading"><div><p className="eyebrow">Step {step.step_number} of {step.total_steps}</p><h3>{step.title}</h3><p className="planning-note">{step.recipe_name}{step.prep_group_name ? ` · ${step.prep_group_name}` : ''}</p></div></div>
        {step.instructions && <p>{step.instructions}</p>}
        <div className="recipe-ingredient-list">{step.ingredients.map((ingredient) => <div className="ingredient-row" key={`${step.step_id}-${ingredient.ingredient_id}`}><strong>{ingredient.ingredient_name}</strong><div className="ingredient-meta"><span>{quantity(ingredient.quantity)} {ingredient.unit_code}</span>{ingredient.prep_method && <span>{ingredient.prep_method}</span>}{ingredient.prep_size && <span>{ingredient.prep_size}</span>}{ingredient.prep_state && <span>{ingredient.prep_state}</span>}</div></div>)}</div>
        <div className="header-actions"><button type="button" className="button-secondary" disabled={stepIndex === 0} onClick={() => setStepIndex((value) => Math.max(0, value - 1))}>Previous</button><button type="button" disabled={stepIndex >= selectedMeal.steps.length - 1} onClick={() => setStepIndex((value) => Math.min(selectedMeal.steps.length - 1, value + 1))}>Next</button></div>
      </div> : <p className="muted-line">This planned Meal has no cooking steps yet.</p>}
    </>}
    {!cooking.isPending && cooking.data?.meals.length === 0 && <p className="muted-line">No planned Meals in this cycle.</p>}
  </section>
}
