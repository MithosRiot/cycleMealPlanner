import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { fetchCycleAllocationPreview } from './allocationApi'
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

function CycleAllocationPanel() {
  const cycles = useQuery({ queryKey: ['meal-cycles'], queryFn: fetchMealCycles })
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const effectiveId = selectedId ?? cycles.data?.[0]?.id ?? null
  const preview = useQuery({
    queryKey: ['cycle-allocation-preview', effectiveId],
    queryFn: () => fetchCycleAllocationPreview(effectiveId as number),
    enabled: effectiveId !== null,
  })
  return <section className="panel" style={{ marginTop: 20 }}>
    <div className="section-heading"><div><h2>Allocation preview</h2><p className="planning-note">Shows which lots should be used first. This preview does not change Inventory.</p></div><div className="header-actions"><select value={effectiveId ?? ''} onChange={(event) => setSelectedId(event.target.value ? Number(event.target.value) : null)}><option value="">Select cycle</option>{cycles.data?.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.name}</option>)}</select><button type="button" className="button-secondary" disabled={preview.isFetching || effectiveId === null} onClick={() => preview.refetch()}>Refresh</button></div></div>
    {preview.error instanceof Error && <div className="error-banner">{preview.error.message}</div>}
    <div className="recipe-ingredient-list">{preview.data?.requirements.map((requirement, index) => <div className="recipe-ingredient-editor" key={`${requirement.planned_meal_id}-${requirement.recipe_id}-${requirement.ingredient_id}-${index}`}>
      <strong>{requirement.ingredient_name ?? `Ingredient ${requirement.ingredient_id}`}</strong>
      <div className="ingredient-meta"><span>{requirement.meal_name ?? 'Planned meal'}{requirement.day_number ? ` · Day ${requirement.day_number}` : ''}{requirement.slot_label ? ` · ${requirement.slot_label}` : ''}</span><span>Need {requirement.requested_quantity} {requirement.unit_code}</span><span>Allocated {requirement.allocated_quantity} {requirement.unit_code}</span>{Number(requirement.reserved_elsewhere_quantity) > 0 && <span>Reserved elsewhere {requirement.reserved_elsewhere_quantity} {requirement.unit_code}</span>}{Number(requirement.shortage_quantity) > 0 && <span className="warning-text">Short {requirement.shortage_quantity} {requirement.unit_code}</span>}</div>
      <div className="recipe-ingredient-list" style={{ marginTop: 10 }}>{requirement.allocations.map((lot) => <div className="ingredient-row" key={lot.lot_id}><strong>Lot #{lot.lot_id}</strong><div className="ingredient-meta"><span>Use {lot.allocated_quantity} {lot.unit_code}</span><span>Source {lot.source_quantity} {lot.source_unit_code}</span><span>{lot.location_name ?? `Location ${lot.location_id}`}</span><span>{lot.expiration_date ? `Expires ${lot.expiration_date}` : 'No expiration date'}</span>{lot.opened_date && <span>Opened {lot.opened_date}</span>}{lot.thawed_date ? <span>Thawed {lot.thawed_date}</span> : lot.frozen_date ? <span>Frozen {lot.frozen_date}</span> : null}</div></div>)}</div>
      {requirement.allocations.length === 0 && <p className="muted-line">No usable lot allocation.</p>}
    </div>)}</div>
    {!preview.isPending && preview.data?.requirements.length === 0 && <p className="muted-line">No planned ingredient requirements to allocate.</p>}
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

export function MealPlanWithReservationsPage() { return <><MealPlanPage /><CycleReservationPanel /><CycleAllocationPanel /></> }
export function InventoryWithReservationsPage() { return <><InventoryPage /><InventoryAvailabilityPanel /></> }
