import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { fetchCycleAllocationPreview } from './allocationApi'
import { fetchIngredients, fetchMeasurementUnits, Ingredient } from './api'
import InventoryPage from './InventoryPage'
import MealPlanPage from './MealPlanPage'
import { fetchMealCycles } from './mealCyclesApi'
import ReservationPanel from './ReservationPanel'
import { fetchInventoryAvailability, fetchProductionAvailability } from './reservationsApi'

type StapleIngredient = Ingredient & {
  staple_enabled: boolean
  staple_minimum: string | null
  staple_target: string | null
  staple_unit_id: number | null
}

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
  const preview = useQuery({ queryKey: ['cycle-allocation-preview', effectiveId], queryFn: () => fetchCycleAllocationPreview(effectiveId as number), enabled: effectiveId !== null })
  return <section className="panel" style={{ marginTop: 20 }}>
    <div className="section-heading"><div><h2>Allocation preview</h2><p className="planning-note">Shows which lots should be used first. This preview does not change Inventory.</p></div><div className="header-actions"><select value={effectiveId ?? ''} onChange={(event) => setSelectedId(event.target.value ? Number(event.target.value) : null)}><option value="">Select cycle</option>{cycles.data?.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.name}</option>)}</select><button type="button" className="button-secondary" disabled={preview.isFetching || effectiveId === null} onClick={() => preview.refetch()}>Refresh</button></div></div>
    {preview.error instanceof Error && <div className="error-banner">{preview.error.message}</div>}
    <div className="recipe-ingredient-list">{preview.data?.requirements.map((requirement, index) => <div className="recipe-ingredient-editor" key={`${requirement.planned_meal_id}-${requirement.recipe_id}-${requirement.ingredient_id}-${index}`}>
      <strong>{requirement.ingredient_name ?? `Ingredient ${requirement.ingredient_id}`}</strong>
      <div className="ingredient-meta"><span>{requirement.meal_name ?? 'Planned meal'}{requirement.day_number ? ` · Day ${requirement.day_number}` : ''}{requirement.slot_label ? ` · ${requirement.slot_label}` : ''}</span><span>Need {requirement.requested_quantity} {requirement.unit_code}</span><span>Allocated {requirement.allocated_quantity} {requirement.unit_code}</span>{Number(requirement.reserved_elsewhere_quantity) > 0 && <span>Reserved elsewhere {requirement.reserved_elsewhere_quantity} {requirement.unit_code}</span>}{Number(requirement.shortage_quantity) > 0 && <span className="warning-text">Short {requirement.shortage_quantity} {requirement.unit_code}</span>}</div>
      <div className="recipe-ingredient-list" style={{ marginTop: 10 }}>{requirement.allocations.map((lot) => <div className="ingredient-row" key={lot.lot_id}><strong>Lot {lot.lot_id}</strong><div className="ingredient-meta"><span>Use {lot.allocated_quantity} {lot.unit_code}</span><span>Source {lot.source_quantity} {lot.source_unit_code}</span><span>{lot.location_name ?? `Location ${lot.location_id}`}</span><span>{lot.expiration_date ? `Expires ${lot.expiration_date}` : 'No expiration date'}</span>{lot.opened_date && <span>Opened {lot.opened_date}</span>}{lot.thawed_date ? <span>Thawed {lot.thawed_date}</span> : lot.frozen_date ? <span>Frozen {lot.frozen_date}</span> : null}</div></div>)}</div>
      {requirement.allocations.length === 0 && <p className="muted-line">No usable lot allocation.</p>}
    </div>)}</div>
    {!preview.isPending && preview.data?.requirements.length === 0 && <p className="muted-line">No planned ingredient requirements to allocate.</p>}
  </section>
}

function InventoryAvailabilityPanel() {
  const ingredients = useQuery({ queryKey: ['ingredients', 'reservation-availability'], queryFn: () => fetchIngredients() as Promise<StapleIngredient[]> })
  const units = useQuery({ queryKey: ['measurement-units', 'staple-availability'], queryFn: fetchMeasurementUnits })
  const availability = useQuery({ queryKey: ['inventory-availability'], queryFn: fetchInventoryAvailability })
  const production = useQuery({ queryKey: ['production-inventory-availability'], queryFn: fetchProductionAvailability })
  const ingredientMap = useMemo(() => new Map((ingredients.data ?? []).map((item) => [item.id, item])), [ingredients.data])
  const unitMap = useMemo(() => new Map((units.data ?? []).map((item) => [item.id, item])), [units.data])

  function stapleStatus(row: { ingredient_id: number; unit_family: string; unit_id: number; available_quantity: string }) {
    const ingredient = ingredientMap.get(row.ingredient_id)
    if (!ingredient?.staple_enabled || ingredient.staple_minimum === null || ingredient.staple_target === null || ingredient.staple_unit_id === null) return null
    const stapleUnit = unitMap.get(ingredient.staple_unit_id)
    const rowUnit = unitMap.get(row.unit_id)
    if (!stapleUnit || !rowUnit || stapleUnit.unit_family !== row.unit_family || rowUnit.unit_family !== row.unit_family) return null
    const minimum = Number(ingredient.staple_minimum) * Number(stapleUnit.base_multiplier) / Number(rowUnit.base_multiplier)
    const target = Number(ingredient.staple_target) * Number(stapleUnit.base_multiplier) / Number(rowUnit.base_multiplier)
    const available = Number(row.available_quantity)
    return { minimum, target, low: available < minimum }
  }

  function compact(value: number) { return Number(value.toFixed(6)) }

  return <section className="settings-card" style={{ marginTop: 20 }}>
    <div className="section-heading"><div><h2>Inventory availability</h2><p className="muted-line">Reservations do not reduce physical lots. Available = Physical − Active reservations. Staple rules compare against Available.</p></div><button type="button" className="button-secondary" disabled={availability.isFetching || production.isFetching} onClick={() => { availability.refetch(); production.refetch() }}>Refresh</button></div>
    {availability.error instanceof Error && <div className="error-banner">{availability.error.message}</div>}
    {production.error instanceof Error && <div className="error-banner">{production.error.message}</div>}
    <h3>Ingredient stock</h3>
    <div className="recipe-ingredient-list">{availability.data?.map((row) => {
      const ingredient = ingredientMap.get(row.ingredient_id)
      const staple = stapleStatus(row)
      return <div className="ingredient-row" key={`${row.ingredient_id}-${row.unit_family}`}><strong>{ingredient?.name ?? `Ingredient ${row.ingredient_id}`}</strong><div className="ingredient-meta"><span>Physical {row.physical_quantity} {row.unit_code}</span><span>Reserved {row.reserved_quantity} {row.unit_code}</span><span>Available {row.available_quantity} {row.unit_code}</span>{Number(row.shortage_quantity) > 0 && <span className="warning-text">Short {row.shortage_quantity} {row.unit_code}</span>}{staple && <span className={staple.low ? 'warning-text' : ''}>Staple min {compact(staple.minimum)} · target {compact(staple.target)} {row.unit_code}{staple.low ? ' · LOW' : ''}</span>}</div></div>
    })}</div>
    {!availability.isPending && availability.data?.length === 0 && <p className="muted-line">No physical Ingredient Inventory or active reservations yet.</p>}

    <h3 style={{ marginTop: 18 }}>Produced stock</h3>
    <div className="recipe-ingredient-list">{production.data?.map((row) => {
      const unit = unitMap.get(row.unit_id)
      return <div className="ingredient-row" key={row.lot_id}><strong>{row.source_name ?? `${row.source_type} ${row.source_id ?? ''}`}</strong><div className="ingredient-meta"><span>Lot {row.lot_id}</span><span>Physical {row.physical_quantity} {unit?.code ?? ''}</span><span>Reserved {row.reserved_quantity} {unit?.code ?? ''}</span><span>Available {row.available_quantity} {unit?.code ?? ''}</span>{row.expiration_date && <span>Expires {row.expiration_date}</span>}</div></div>
    })}</div>
    {!production.isPending && production.data?.length === 0 && <p className="muted-line">No produced leftover or Recipe-output Inventory yet.</p>}
  </section>
}

export function MealPlanWithReservationsPage() { return <><MealPlanPage /><CycleReservationPanel /><CycleAllocationPanel /></> }
export function InventoryWithReservationsPage() { return <><InventoryPage /><InventoryAvailabilityPanel /></> }
