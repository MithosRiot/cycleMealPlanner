import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { dashboardShoppingShortages, dashboardValidationAlerts } from './dashboardAlerts'
import { fetchUseSoon } from './dashboardApi'
import { fetchCycleValidation, fetchMealCycles } from './mealCyclesApi'
import { fetchPrepSchedule } from './prepScheduleApi'
import { fetchInventoryAvailability, fetchProductionAvailability } from './reservationsApi'
import { fetchShoppingList } from './shoppingApi'
import { inventoryDashboardSummary, producedInventoryDashboardSummary, selectCurrentCycle, todaysMealSlots, todaysPrepTasks } from './dashboardSelectors'

function formatServingTime(value: string | null): string {
  if (!value) return 'Unscheduled'
  const [hour, minute] = value.split(':').map(Number)
  return new Date(2000, 0, 1, hour, minute).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
}

function useSoonLabel(days: number): string {
  if (days === 0) return 'Use today'
  if (days === 1) return '1 day left'
  return `${days} days left`
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
  const useSoon = useQuery({ queryKey: ['dashboard-use-soon', 7], queryFn: () => fetchUseSoon(7) })
  const validation = useQuery({
    queryKey: ['cycle-validation', currentCycle?.id ?? null],
    queryFn: () => fetchCycleValidation(currentCycle!.id),
    enabled: currentCycle !== null,
    refetchInterval: 5_000,
  })
  const shopping = useQuery({
    queryKey: ['shopping-list', currentCycle?.id ?? null],
    queryFn: () => fetchShoppingList(currentCycle!.id),
    enabled: currentCycle !== null,
    retry: false,
    refetchInterval: 5_000,
  })

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
  const validationAlerts = dashboardValidationAlerts(validation.data?.issues ?? [])
  const shoppingShortages = dashboardShoppingShortages(shopping.data?.items ?? [])

  return <section className="page-card">
    <p className="eyebrow">Cycle Meal Planner</p>
    <div className="section-heading">
      <div><h1>Dashboard</h1><p className="planning-note">Current operational view for meals, prep, stock, and plan alerts.</p></div>
      <div className="ingredient-meta"><span>{currentCycle.name}</span><span>{currentCycle.status}</span>{currentCycle.start_date && <span>Starts {currentCycle.start_date}</span>}<span>{currentCycle.duration_days} days</span></div>
    </div>

    <div className="advanced-grid" style={{ marginTop: 16 }}>
      <div className="settings-card"><strong>Today's meals</strong><div className="ingredient-meta"><span>{todayMeals.length} scheduled</span></div></div>
      <div className="settings-card"><strong>Today's prep</strong><div className="ingredient-meta"><span>{todayPrep.length} tasks</span></div></div>
      <div className="settings-card"><strong>Ingredient stock</strong><div className="ingredient-meta"><span>{inventorySummary.tracked} tracked</span><span>{inventorySummary.reserved} reserved</span><span>{inventorySummary.shortages} shortages</span></div></div>
      <div className="settings-card"><strong>Produced stock</strong><div className="ingredient-meta"><span>{producedSummary.lots} lots</span><span>{producedSummary.reservedLots} reserved</span><span>{producedSummary.availableLots} available</span></div></div>
    </div>

    <section className="settings-card" style={{ marginTop: 16 }}>
      <div className="section-heading">
        <div><h2>Plan alerts</h2><p className="planning-note">Current-cycle validation and generated Shopping shortages. This section refreshes automatically.</p></div>
        <div className="ingredient-meta"><span>{validationAlerts.length} validation</span><span>{shoppingShortages.length} shopping</span></div>
      </div>
      {validation.error instanceof Error && <div className="error-banner">{validation.error.message}</div>}
      {validationAlerts.map((issue) => <div className="inventory-history-row" key={issue.key}>
        <strong>{issue.severity} · {issue.code.replaceAll('_', ' ')}</strong>
        <span>{issue.message}</span>
        <Link to="/meal-plan/validation">Open Plan Validation</Link>
      </div>)}
      {!validation.isPending && !validation.error && validationAlerts.length === 0 && <p className="muted-line">No current cycle validation issues.</p>}

      {shopping.isError && <p className="muted-line">No generated Shopping list for {currentCycle.name}. <Link to="/shopping">Generate it in Shopping.</Link></p>}
      {shoppingShortages.map((item) => <div className="inventory-history-row" key={`shopping-${item.id}`}>
        <strong>SHOPPING · {item.ingredient_name}</strong>
        <span>Need {Number(item.required_quantity).toLocaleString()} {item.unit_code} · Have {Number(item.inventory_quantity).toLocaleString()} {item.unit_code} · Missing {Number(item.generated_quantity).toLocaleString()} {item.unit_code}</span>
        {item.warning && <span className="warning-text">{item.warning}</span>}
        <Link to="/shopping">Open Shopping</Link>
      </div>)}
      {shopping.data && shoppingShortages.length === 0 && <p className="muted-line">No current Shopping shortages.</p>}
    </section>

    <section className="settings-card" style={{ marginTop: 16 }}>
      <h2>Use Soon</h2>
      <p className="planning-note">Available Inventory expiring within the next 7 days, ordered by urgency.</p>
      {useSoon.error instanceof Error && <div className="error-banner">{useSoon.error.message}</div>}
      {useSoon.data?.recommendations.map((row) => <div className="inventory-history-row" key={`${row.source_type}-${row.lot_id}`}>
        <strong>{useSoonLabel(row.days_remaining)} · {row.source_name}</strong>
        <span>{row.source_type === 'INGREDIENT' ? 'Ingredient' : row.source_type === 'LEFTOVER' ? 'Leftover' : 'Recipe output'} · Lot {row.lot_id}</span>
        <span>{row.available_quantity} {row.unit_code} available · {row.location_name}</span>
        <span>Expires {row.expiration_date}</span>
      </div>)}
      {!useSoon.isPending && !useSoon.error && useSoon.data?.recommendations.length === 0 && <p className="muted-line">No available Inventory expires within the next 7 days.</p>}
    </section>

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
