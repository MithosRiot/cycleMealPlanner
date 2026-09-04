import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchMeasurementUnits } from './api'
import { assignProducedSource, fetchMealCycle, fetchMealCycles, fetchProducedSourceOptions, removePlannedMeal, type ProducedSourceOption } from './mealCyclesApi'
import { fetchProductionAvailability, fetchProductionCoverage } from './reservationsApi'
import { onProductionInventoryChanged } from './productionEvents'
import { producedSourcePlacements } from './producedStockCoverageSelectors'

export default function ProducedStockCoveragePanel() {
  const queryClient = useQueryClient()
  const cycles = useQuery({ queryKey: ['meal-cycles'], queryFn: fetchMealCycles })
  const options = useQuery({ queryKey: ['produced-source-options'], queryFn: fetchProducedSourceOptions })
  const units = useQuery({ queryKey: ['measurement-units'], queryFn: fetchMeasurementUnits })
  const availability = useQuery({ queryKey: ['production-inventory-availability'], queryFn: fetchProductionAvailability })
  const [cycleId, setCycleId] = useState<number | null>(null)
  const [slotId, setSlotId] = useState<number | null>(null)
  const [optionIndex, setOptionIndex] = useState<number | null>(null)
  const [quantity, setQuantity] = useState('')

  const cycle = useQuery({ queryKey: ['meal-cycle', cycleId], queryFn: () => fetchMealCycle(cycleId as number), enabled: cycleId !== null })
  const coverage = useQuery({ queryKey: ['production-coverage', cycleId], queryFn: () => fetchProductionCoverage(cycleId as number), enabled: cycleId !== null })
  const selectedOption: ProducedSourceOption | null = optionIndex === null ? null : options.data?.[optionIndex] ?? null
  const unitCodes = useMemo(() => new Map((units.data ?? []).map((unit) => [unit.id, unit.code])), [units.data])

  const emptySlots = cycle.data?.slots.filter((slot) => slot.planned_meal === null) ?? []
  const producedPlacements = producedSourcePlacements(cycle.data?.slots ?? [])

  async function refresh() {
    await queryClient.invalidateQueries({ queryKey: ['meal-cycles'] })
    await queryClient.invalidateQueries({ queryKey: ['meal-cycle', cycleId] })
    await queryClient.invalidateQueries({ queryKey: ['produced-source-options'] })
    await queryClient.invalidateQueries({ queryKey: ['production-coverage', cycleId] })
    await queryClient.invalidateQueries({ queryKey: ['production-inventory-availability'] })
    await queryClient.invalidateQueries({ queryKey: ['cycle-validation', cycleId] })
  }

  useEffect(() => onProductionInventoryChanged(() => { void refresh() }), [cycleId, queryClient])

  const place = useMutation({
    mutationFn: () => {
      if (cycleId === null || slotId === null || selectedOption === null || !quantity) throw new Error('Select a cycle, empty slot, produced source, and quantity')
      return assignProducedSource(cycleId, slotId, selectedOption, quantity)
    },
    onSuccess: async () => { setSlotId(null); setOptionIndex(null); setQuantity(''); await refresh() },
  })

  const remove = useMutation({
    mutationFn: (targetSlotId: number) => removePlannedMeal(cycleId as number, targetSlotId),
    onSuccess: refresh,
  })

  const error = place.error ?? remove.error

  return <section className="panel" style={{ marginTop: 20 }}>
    <div className="section-heading">
      <div><h2>Produced stock coverage</h2><p className="planning-note">Plan a future slot from a specific leftover or Recipe output. Coverage reserves only that produced source; unrelated stock is never substituted.</p></div>
      <select value={cycleId ?? ''} onChange={(event) => { setCycleId(event.target.value ? Number(event.target.value) : null); setSlotId(null) }}>
        <option value="">Select cycle</option>
        {cycles.data?.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select>
    </div>

    {error instanceof Error && <div className="error-banner">{error.message}</div>}

    {cycleId !== null && <>
      <div className="advanced-grid">
        <label>Future empty slot<select value={slotId ?? ''} onChange={(event) => setSlotId(event.target.value ? Number(event.target.value) : null)}><option value="">Select slot</option>{emptySlots.map((slot) => { const definition = cycle.data?.slot_definitions.find((item) => item.id === slot.slot_definition_id); return <option key={slot.id} value={slot.id}>Day {slot.day_number} · {definition?.label ?? 'Slot'}</option> })}</select></label>
        <label>Produced source<select value={optionIndex ?? ''} onChange={(event) => { const index = event.target.value === '' ? null : Number(event.target.value); setOptionIndex(index); if (index !== null) setQuantity(options.data?.[index]?.planned_quantity ?? '') }}><option value="">Select source</option>{options.data?.map((option, index) => <option key={`${option.source_type}-${option.source_origin_planned_meal_id}-${option.source_record_id ?? option.source_recipe_output_id ?? 'planned'}`} value={index}>{option.source_name} · planned {option.planned_quantity} {option.unit_code} · available {option.available_quantity}</option>)}</select></label>
        <label>Quantity<input type="number" min="0.001" step="any" value={quantity} onChange={(event) => setQuantity(event.target.value)} /></label>
      </div>
      {selectedOption && <p className="planning-note">Source PlannedMeal {selectedOption.source_origin_planned_meal_id} · physical {selectedOption.physical_quantity} {selectedOption.unit_code} · reserved {selectedOption.reserved_quantity} · available {selectedOption.available_quantity}{selectedOption.lot_id ? ` · Lot ${selectedOption.lot_id}` : ' · not produced yet'}.</p>}
      <button type="button" disabled={place.isPending || slotId === null || selectedOption === null || !quantity || Number(quantity) <= 0} onClick={() => place.mutate()}>Use produced stock in future slot</button>

      <div style={{ marginTop: 16 }}>
        <h3>Active produced-source placements</h3>
        {producedPlacements.map((slot) => {
          const planned = slot.planned_meal
          const row = coverage.data?.reservations.find((item) => item.planned_meal_id === planned.id && item.status === 'ACTIVE')
          const definition = cycle.data?.slot_definitions.find((item) => item.id === slot.slot_definition_id)
          return <div className="inventory-history-row" key={planned.id}>
            <strong>Day {slot.day_number} · {definition?.label ?? 'Slot'} · {planned.snapshot_name}</strong>
            <span>Requested {planned.source_quantity} {unitCodes.get(planned.source_unit_id as number) ?? ''}</span>
            <span>Reserved {row?.reserved_quantity ?? '0'} · Shortage {row?.shortage_quantity ?? planned.source_quantity}</span>
            <span>{row?.lot_id ? `Lot ${row.lot_id}` : 'Waiting for exact produced lot'}</span>
            <button type="button" className="button-secondary" disabled={planned.locked || remove.isPending} onClick={() => remove.mutate(slot.id)}>Remove</button>
          </div>
        })}
        {producedPlacements.length === 0 && <p className="planning-note">No future produced-source placements in this cycle.</p>}
      </div>
    </>}

    <div style={{ marginTop: 16 }}>
      <h3>Produced Inventory availability</h3>
      {availability.data?.map((row) => <p className="planning-note" key={row.lot_id}>{row.source_name ?? `${row.source_type} ${row.source_id ?? ''}`} · Lot {row.lot_id}: Physical {row.physical_quantity} {unitCodes.get(row.unit_id) ?? ''} · Reserved {row.reserved_quantity} · Available {row.available_quantity}{row.expiration_date ? ` · expires ${row.expiration_date}` : ''}</p>)}
      {!availability.isPending && availability.data?.length === 0 && <p className="planning-note">No produced Inventory lots yet.</p>}
    </div>
  </section>
}
