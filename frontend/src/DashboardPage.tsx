import { useQuery } from '@tanstack/react-query'
import { fetchMealCycles } from './mealCyclesApi'
import { fetchPrepSchedule } from './prepScheduleApi'
import { fetchInventoryAvailability, fetchProductionAvailability } from './reservationsApi'
import { inventoryDashboardSummary, producedInventoryDashboardSummary, selectCurrentCycle, todaysMealSlots, todaysPrepTasks } from './dashboardSelectors'

function formatServingTime(value: string | null): string {
  if (!value) return 'Unscheduled'
  const [hour, minute] = value.split(':').map(Number)
  return new Date(2000, 0, 1, hour, minute).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
}

export default function DashboardPage() {
  const cycles = useQuery({ queryKey: ['meal-cycles'], queryFn: fetchMealCycles })
  const currentCycle = selectCurrentCycle(cycles.data ?? [])
  const prep = useQuery({
    queryKey: ['prep-schedule', currentCycle?.id ?? null],
    queryFn: () => fetchPrepSchedule(currentCycle!.id),
    enabled: currentCycle !== null,
  })
  const inventory = useQuery({ queryKey: ['inventory-availability'], queryFn: fetchInventoryAvailability })
  const production = useQuery({ queryKey: ['production-inventory-availability'], queryFn: fetchProductionAvailability })

  if (cycles.isPending) return <section className="page-card"><p className="eyebrow">Cycle Meal Planner</p><h1>Dashboard</h1><p>Loading dashboard…</p></section>
  if (cycles.error instanceof Error) return <section className="page-card"><p className="eyebrow">Cycle Meal Planner</p><h1>Dashboard</h1><div className="error-banner">{cycles.error.message}</div></section>

  if (!currentCycle) {
    return <section className="page-card">
      <p className="eyebrow">Cycle Meal Planner</p>
      <h1>Dashboard</h1>
      <p className="muted-line">No Meal Cycle is available yet. Create and schedule a cycle from Meal Plan to populate the dashboard.</p>
    </section>
  }

  const todayMeals = todaysMealSlots(currentCycle)
  const todayPrep = todaysPrepTasks(prep.data?.tasks ?? [])
  const inventorySummary = inventoryDashboardSummary(inventory.data ?? [])
  const producedSummary = producedInventoryDashboardSummary(production.data ?? [])

  return <section className="page-card">
    <p className="eyebrow">Cycle Meal Planner</p>
    <div className="section-heading">
      <div><h1>Dashboard</h1><p className="planning-note">Current operational view for meals, prep, and stock.</p></div>
      <div className="ingredient-meta"><span>{currentCycle.name}</span><span>{currentCycle.status}</span>{currentCycle.start_date && <span>Starts {currentCycle.start_date}</span>}<span>{currentCycle.duration_days} days</span></div>
    </div>

    <div className="advanced-grid" style={{ marginTop: 16 }}>
      <div className="settings-card"><strong>Today's meals</strong><div className="ingredient-meta"><span>{todayMeals.length} scheduled</span></div></div>
      <div className="settings-card"><strong>Today's prep</strong><div className="ingredient-meta"><span>{todayPrep.length} tasks</span></div></div>
      <div className="settings-card"><strong>Ingredient stock</strong><div className="ingredient-meta"><span>{inventorySummary.tracked} tracked</span><span>{inventorySummary.reserved} reserved</span><span>{inventorySummary.shortages} shortages</span></div></div>
      <div className="settings-card"><strong>Produced stock</strong><div className="ingredient-meta"><span>{producedSummary.lots} lots</span><span>{producedSummary.reservedLots} reserved</span><span>{producedSummary.availableLots} available</span></div></div>
    </div>

    <section className="settings-card" style={{ marginTop: 16 }}>
      <h2>Today's Meals</h2>
      {todayMeals.map((slot) => <div className="inventory-history-row" key={slot.id}>
        <strong>{formatServingTime(slot.serving_time)} · {slot.planned_meal?.snapshot_name}</strong>
        <span>{slot.planned_meal?.source_type === 'SAVED_MEAL' ? 'Saved Meal' : slot.planned_meal?.source_type === 'LEFTOVER' ? 'Leftover' : 'Recipe output'}</span>
        <span>{slot.planned_meal?.locked ? 'Locked' : 'Editable'}</span>
      </div>)}
      {todayMeals.length === 0 && <p className="muted-line">No Meals are scheduled for today in {currentCycle.name}.</p>}
    </section>

    <section className="settings-card" style={{ marginTop: 16 }}>
      <h2>Today's Operational Work</h2>
      {todayPrep.map((task) => <div className="inventory-history-row" key={`${task.planned_meal_id}-${task.advance_prep_id}`}>
        <strong>{task.task_type} · {task.title}</strong>
        <span>{task.meal_name} · {task.recipe_name}</span>
        <span>{task.start_datetime ? new Date(task.start_datetime).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : 'Unscheduled'}</span>
        {task.unresolved_reason && <span className="warning-text">{task.unresolved_reason}</span>}
      </div>)}
      {!prep.isPending && todayPrep.length === 0 && <p className="muted-line">No advance-prep tasks are due today.</p>}
    </section>
  </section>
}
