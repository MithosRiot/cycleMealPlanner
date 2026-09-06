import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { correctInventory, fetchInventory, removeInventory } from './api'
import { assignProducedSource, fetchMealCycles, fetchProducedSourceOptions, type ProducedSourceOption } from './mealCyclesApi'
import { eligibleFutureSlots, leftoverState, sourceSlotFor } from './leftoversSelectors'

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

export default function LeftoversPage() {
  const queryClient = useQueryClient()
  const cycles = useQuery({ queryKey: ['meal-cycles'], queryFn: fetchMealCycles })
  const options = useQuery({ queryKey: ['produced-source-options'], queryFn: fetchProducedSourceOptions })
  const inventory = useQuery({ queryKey: ['inventory', 'produced-leftovers'], queryFn: () => fetchInventory({ include_empty: true }) })
  const [selectedSlot, setSelectedSlot] = useState<Record<number, string>>({})
  const [selectedQuantity, setSelectedQuantity] = useState<Record<number, string>>({})
  const [correctionQuantity, setCorrectionQuantity] = useState<Record<number, string>>({})

  const leftovers = useMemo(() => (options.data ?? []).filter((item) => item.source_type === 'LEFTOVER'), [options.data])
  const lotsById = useMemo(() => new Map((inventory.data ?? []).map((lot) => [lot.id, lot])), [inventory.data])

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['produced-source-options'] }),
      queryClient.invalidateQueries({ queryKey: ['inventory'] }),
      queryClient.invalidateQueries({ queryKey: ['meal-cycles'] }),
      queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
      queryClient.invalidateQueries({ queryKey: ['dashboard-alerts'] }),
      queryClient.invalidateQueries({ queryKey: ['production-inventory-availability'] }),
      queryClient.invalidateQueries({ queryKey: ['cycle-validation'] }),
    ])
  }

  const plan = useMutation({
    mutationFn: ({ option, cycleId, slotId, quantity }: { option: ProducedSourceOption; cycleId: number; slotId: number; quantity: string }) => assignProducedSource(cycleId, slotId, option, quantity),
    onSuccess: refresh,
  })
  const correct = useMutation({
    mutationFn: ({ lotId, quantity }: { lotId: number; quantity: string }) => correctInventory(lotId, quantity, 'Leftovers correction'),
    onSuccess: refresh,
  })
  const discard = useMutation({
    mutationFn: ({ lotId, quantity }: { lotId: number; quantity: string }) => removeInventory(lotId, quantity, 'Discarded from Leftovers'),
    onSuccess: refresh,
  })

  const error = plan.error ?? correct.error ?? discard.error

  return <section className="page-card">
    <p className="eyebrow">Produced food</p>
    <h1>Leftovers</h1>
    <p className="planning-note">View produced leftovers, see what is reserved for future meals, safely correct or discard unreserved quantities, and schedule available leftovers into future meal-plan slots.</p>

    {error instanceof Error && <div className="error-banner">{error.message}</div>}
    {options.isPending && <p>Loading leftovers…</p>}

    <div className="inventory-list">
      {leftovers.map((option) => {
        const source = sourceSlotFor(option, cycles.data ?? [])
        const state = leftoverState(option, todayIso())
        const eligible = eligibleFutureSlots(option, cycles.data ?? [])
        const lot = option.lot_id ? lotsById.get(option.lot_id) : undefined
        const target = selectedSlot[option.source_origin_planned_meal_id] ?? ''
        const targetRow = eligible.find((row) => `${row.cycle.id}:${row.slot.id}` === target)
        const quantity = selectedQuantity[option.source_origin_planned_meal_id] ?? option.available_quantity
        const correction = correctionQuantity[option.source_origin_planned_meal_id] ?? option.physical_quantity
        const canPlan = state === 'AVAILABLE' && Number(option.available_quantity) > 0 && targetRow && Number(quantity) > 0 && Number(quantity) <= Number(option.available_quantity)
        const discardable = Math.max(Number(option.physical_quantity) - Number(option.reserved_quantity), 0)

        return <article className="panel" key={`${option.source_origin_planned_meal_id}-${option.source_record_id ?? 'planned'}`} style={{ marginBottom: 16 }}>
          <div className="section-heading">
            <div>
              <h2>{option.source_name.replace(/^Leftover:\s*/, '')}</h2>
              <p className="planning-note">{source ? `${source.cycle.name} · Day ${source.slot.day_number}${source.slot.scheduled_date ? ` · ${source.slot.scheduled_date}` : ''}` : `Source PlannedMeal ${option.source_origin_planned_meal_id}`}</p>
            </div>
            <strong>{state}</strong>
          </div>

          <div className="advanced-grid">
            <div><strong>Produced / remaining</strong><p>{option.planned_quantity} planned · {option.physical_quantity} remaining {option.unit_code}</p></div>
            <div><strong>Reserved / available</strong><p>{option.reserved_quantity} reserved · {option.available_quantity} available</p></div>
            <div><strong>Expiration</strong><p>{option.expiration_date ?? 'Not set'}</p></div>
            <div><strong>Provenance</strong><p>{option.lot_id ? `Leftover record ${option.source_record_id ?? '—'} · Inventory lot ${option.lot_id}` : 'Planned leftover; not produced yet'}</p></div>
          </div>

          {lot && <div style={{ marginTop: 16 }}>
            <h3>Correct or discard</h3>
            <div className="advanced-grid">
              <label>Correct remaining quantity<input type="number" min={option.reserved_quantity} step="any" value={correction} onChange={(event) => setCorrectionQuantity((current) => ({ ...current, [option.source_origin_planned_meal_id]: event.target.value }))} /></label>
              <div><button type="button" className="button-secondary" disabled={correct.isPending || Number(correction) < Number(option.reserved_quantity)} onClick={() => correct.mutate({ lotId: lot.id, quantity: correction })}>Save correction</button></div>
              <div><button type="button" className="button-secondary" disabled={discard.isPending || discardable <= 0} onClick={() => discard.mutate({ lotId: lot.id, quantity: String(discardable) })}>Discard unreserved ({discardable} {option.unit_code})</button></div>
            </div>
            {Number(option.reserved_quantity) > 0 && <p className="planning-note">Reserved future coverage is protected. Corrections cannot reduce this lot below {option.reserved_quantity} {option.unit_code}, and discard removes only the unreserved portion.</p>}
          </div>}

          <div style={{ marginTop: 16 }}>
            <h3>Plan into a future slot</h3>
            <div className="advanced-grid">
              <label>Future empty slot<select value={target} onChange={(event) => setSelectedSlot((current) => ({ ...current, [option.source_origin_planned_meal_id]: event.target.value }))}><option value="">Select slot</option>{eligible.map((row) => <option key={`${row.cycle.id}:${row.slot.id}`} value={`${row.cycle.id}:${row.slot.id}`}>{row.label}</option>)}</select></label>
              <label>Quantity<input type="number" min="0.001" max={option.available_quantity} step="any" value={quantity} onChange={(event) => setSelectedQuantity((current) => ({ ...current, [option.source_origin_planned_meal_id]: event.target.value }))} /></label>
              <div><button type="button" disabled={!canPlan || plan.isPending} onClick={() => targetRow && plan.mutate({ option, cycleId: targetRow.cycle.id, slotId: targetRow.slot.id, quantity })}>Schedule leftover</button></div>
            </div>
            {state !== 'AVAILABLE' && <p className="planning-note">This leftover cannot be newly scheduled while its state is {state}.</p>}
          </div>
        </article>
      })}
      {!options.isPending && leftovers.length === 0 && <p className="planning-note">No planned or produced leftovers yet.</p>}
    </div>
  </section>
}
