import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { fetchIngredients } from './api'
import InventoryPage from './InventoryPage'
import MealPlanPage from './MealPlanPage'
import { fetchMealCycles } from './mealCyclesApi'
import ReservationPanel from './ReservationPanel'
import { fetchInventoryAvailability } from './reservationsApi'

function CycleReservationPanel() {
  const cycles = useQuery({ queryKey: ['meal-cycles'], queryFn: fetchMealCycles })
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const effectiveId = selectedId ?? cycles.data?.[0]?.id ?? null
  return <section className="panel" style={{ marginTop: 20 }}>
    <div className="section-heading"><div><h2>Cycle reservations</h2><p className="planning-note">Choose a cycle to inspect or refresh its ingredient reservations.</p></div><select value={effectiveId ?? ''} onChange={(event) => setSelectedId(event.target.value ? Number(event.target.value) : null)}><option value="">Select cycle</option>{cycles.data?.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.name}</option>)}</select></div>
    {effectiveId !== null && <ReservationPanel cycleId={effectiveId} />}
  </section>
}

function InventoryAvailabilityPanel() {
  const ingredients = useQuery({ queryKey: ['ingredients', 'reservation-availability'], queryFn: () => fetchIngredients() })
  const availability = useQuery({ queryKey: ['inventory-availability'], queryFn: fetchInventoryAvailability })
  const names = useMemo(() => new Map((ingredients.data ?? []).map((item) => [item.id, item.name])), [ingredients.data])
  return <section className="settings-card" style={{ marginTop: 20 }}>
    <div className="section-heading"><div><h2>Inventory availability</h2><p className="muted-line">Reservations do not reduce physical lots. Available = Physical − Active reservations.</p></div><button type="button" className="button-secondary" disabled={availability.isFetching} onClick={() => availability.refetch()}>Refresh</button></div>
    {availability.error instanceof Error && <div className="error-banner">{availability.error.message}</div>}
    <div className="recipe-ingredient-list">{availability.data?.map((row) => <div className="ingredient-row" key={`${row.ingredient_id}-${row.unit_family}`}><strong>{names.get(row.ingredient_id) ?? `Ingredient ${row.ingredient_id}`}</strong><div className="ingredient-meta"><span>Physical {row.physical_quantity} {row.unit_code}</span><span>Reserved {row.reserved_quantity} {row.unit_code}</span><span>Available {row.available_quantity} {row.unit_code}</span>{Number(row.shortage_quantity) > 0 && <span className="warning-text">Short {row.shortage_quantity} {row.unit_code}</span>}</div></div>)}</div>
    {!availability.isPending && availability.data?.length === 0 && <p className="muted-line">No physical Inventory or active reservations yet.</p>}
  </section>
}

export function MealPlanWithReservationsPage() { return <><MealPlanPage /><CycleReservationPanel /></> }
export function InventoryWithReservationsPage() { return <><InventoryPage /><InventoryAvailabilityPanel /></> }
