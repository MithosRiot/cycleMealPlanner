import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchMealCycle, fetchMealCycles } from './mealCyclesApi'
import { applyGatherSuggestions, clearGatherRequirement, fetchGather, fetchGatherByLocation, replaceGatherWithLot, type GatherRequirement } from './gatherApi'

function lotLabel(lot: { lot_id: number; location_name: string | null; expiration_date: string | null }) {
  return `Lot #${lot.lot_id}${lot.location_name ? ` · ${lot.location_name}` : ''}${lot.expiration_date ? ` · exp ${lot.expiration_date}` : ''}`
}

function formatQuantity(value: string | number): string {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return String(value)
  if (Object.is(numeric, -0) || numeric === 0) return '0'
  return numeric.toLocaleString(undefined, { useGrouping: false, maximumFractionDigits: 6 })
}

function RequirementCard({ cycleId, requirement, disabled, onDone }: { cycleId: number; requirement: GatherRequirement; disabled: boolean; onDone: () => Promise<void> }) {
  const [lotId, setLotId] = useState<number | null>(requirement.candidates[0]?.lot_id ?? null)
  const candidate = requirement.candidates.find((item) => item.lot_id === lotId)
  const [quantity, setQuantity] = useState(candidate?.available_quantity ?? '')
  const replace = useMutation({
    mutationFn: () => {
      if (lotId === null || !quantity) throw new Error('Choose a lot and quantity')
      return replaceGatherWithLot(cycleId, requirement, lotId, quantity)
    },
    onSuccess: onDone,
  })
  const clear = useMutation({ mutationFn: () => clearGatherRequirement(cycleId, requirement), onSuccess: onDone })
  const busy = disabled || replace.isPending || clear.isPending

  return <div className="recipe-ingredient-editor">
    <strong>Day {requirement.day_number} · {requirement.slot_label} · {requirement.meal_name}</strong>
    <div className="ingredient-meta">
      <span>{requirement.ingredient_name}: need {formatQuantity(requirement.required_quantity)} {requirement.unit_code}</span>
      <span>Selected {formatQuantity(requirement.selected_quantity)} {requirement.unit_code} · remaining {formatQuantity(requirement.shortage_quantity)} {requirement.unit_code}</span>
    </div>
    {requirement.selections.length > 0 && <div className="ingredient-meta">{requirement.selections.map((selection) => <span key={selection.lot_id}>{lotLabel(selection)} · {formatQuantity(selection.quantity)} {selection.unit_code}</span>)}</div>}
    {requirement.suggestions.length > 0 && <p className="planning-note">Suggested: {requirement.suggestions.map((lot) => `${lotLabel(lot)} (${formatQuantity(lot.quantity)} ${lot.unit_code})`).join(' + ')}</p>}
    <div className="planning-grid">
      <label>Override lot<select value={lotId ?? ''} onChange={(event) => {
        const nextId = event.target.value ? Number(event.target.value) : null
        setLotId(nextId)
        const next = requirement.candidates.find((item) => item.lot_id === nextId)
        setQuantity(next?.available_quantity ?? '')
      }}><option value="">Choose lot</option>{requirement.candidates.map((lot) => <option key={lot.lot_id} value={lot.lot_id}>{lotLabel(lot)} · available {formatQuantity(lot.available_quantity)} {lot.unit_code}</option>)}</select></label>
      <label>Quantity in lot unit<input type="number" min="0.000001" step="0.000001" value={quantity} onChange={(event) => setQuantity(event.target.value)} /></label>
    </div>
    {(replace.error ?? clear.error) instanceof Error && <div className="error-banner">{(replace.error ?? clear.error as Error).message}</div>}
    <div className="header-actions"><button type="button" className="button-secondary" disabled={busy || lotId === null || !quantity} onClick={() => replace.mutate()}>Replace with lot</button><button type="button" className="button-secondary" disabled={busy || requirement.selections.length === 0} onClick={() => clear.mutate()}>Clear selection</button></div>
  </div>
}

export default function GatherPanel() {
  const queryClient = useQueryClient()
  const cycles = useQuery({ queryKey: ['meal-cycles'], queryFn: fetchMealCycles })
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const effectiveId = selectedId ?? cycles.data?.[0]?.id ?? null
  const cycle = useQuery({ queryKey: ['meal-cycle', effectiveId], queryFn: () => fetchMealCycle(effectiveId as number), enabled: effectiveId !== null })
  const cycleVersion = cycle.dataUpdatedAt
  const gather = useQuery({ queryKey: ['gather', effectiveId, cycleVersion], queryFn: () => fetchGather(effectiveId as number), enabled: effectiveId !== null })
  const byLocation = useQuery({ queryKey: ['gather-by-location', effectiveId, cycleVersion], queryFn: () => fetchGatherByLocation(effectiveId as number), enabled: effectiveId !== null })
  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ['gather', effectiveId] })
    await queryClient.invalidateQueries({ queryKey: ['gather-by-location', effectiveId] })
    await queryClient.invalidateQueries({ queryKey: ['cycle-allocation-preview', effectiveId] })
  }
  const suggest = useMutation({ mutationFn: () => applyGatherSuggestions(effectiveId as number), onSuccess: refresh })

  return <>
    <section className="panel" style={{ marginTop: 20 }}>
      <div className="section-heading"><div><h2>Gather exact lots</h2><p className="planning-note">Choose the exact Inventory lots to gather. Selections are planning state only and do not consume Inventory.</p></div><div className="header-actions"><select value={effectiveId ?? ''} onChange={(event) => setSelectedId(event.target.value ? Number(event.target.value) : null)}><option value="">Select cycle</option>{cycles.data?.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.name}</option>)}</select><button type="button" className="button-secondary" disabled={effectiveId === null || suggest.isPending} onClick={() => suggest.mutate()}>Apply suggested lots</button></div></div>
      {(gather.error ?? suggest.error) instanceof Error && <div className="error-banner">{(gather.error ?? suggest.error as Error).message}</div>}
      <div className="recipe-ingredient-list">{gather.data?.requirements.map((requirement) => <RequirementCard key={`${requirement.planned_meal_id}-${requirement.meal_recipe_id}-${requirement.recipe_ingredient_id}`} cycleId={effectiveId as number} requirement={requirement} disabled={suggest.isPending} onDone={refresh} />)}</div>
      {!gather.isPending && gather.data?.requirements.length === 0 && <p className="muted-line">No ingredient requirements for placed Meals in this cycle.</p>}
    </section>

    <section className="panel" style={{ marginTop: 20 }}>
      <div className="section-heading"><div><h2>Gather by location</h2><p className="planning-note">Pick list generated from the exact lot selections above. Repeated picks from the same lot are combined.</p></div><strong>{byLocation.data?.complete ? 'Complete' : 'Incomplete'}</strong></div>
      {byLocation.error instanceof Error && <div className="error-banner">{byLocation.error.message}</div>}
      {byLocation.data?.locations.map((location) => <div className="recipe-ingredient-editor" key={location.location_id}>
        <h3>{location.location_path}</h3>
        <div className="recipe-ingredient-list">{location.picks.map((pick) => <div key={`${pick.lot_id}-${pick.unit_id}`}>
          <strong>{pick.ingredient_name} · Lot #{pick.lot_id} · {formatQuantity(pick.quantity)} {pick.unit_code}</strong>
          <div className="ingredient-meta">
            {pick.expiration_date && <span>Expires {pick.expiration_date}</span>}
            {pick.opened_date && <span>Opened {pick.opened_date}</span>}
            {pick.frozen_date && !pick.thawed_date && <span>Frozen</span>}
            {pick.thawed_date && <span>Thawed {pick.thawed_date}</span>}
          </div>
          <details><summary>{pick.sources.length} source{pick.sources.length === 1 ? '' : 's'}</summary>{pick.sources.map((source) => <p className="planning-note" key={`${source.planned_meal_id}-${source.meal_recipe_id}-${source.recipe_ingredient_id}`}>Day {source.day_number} · {source.slot_label} · {source.meal_name}: {formatQuantity(source.quantity)} {source.unit_code}</p>)}</details>
        </div>)}</div>
      </div>)}
      {byLocation.data && byLocation.data.locations.length === 0 && <p className="muted-line">No exact lot selections yet.</p>}
      {byLocation.data && byLocation.data.incomplete_requirements.length > 0 && <div className="recipe-ingredient-editor">
        <h3>Still needs exact lots</h3>
        {byLocation.data.incomplete_requirements.map((row) => <p className="planning-note" key={`${row.planned_meal_id}-${row.meal_recipe_id}-${row.recipe_ingredient_id}`}>Day {row.day_number} · {row.slot_label} · {row.meal_name} · {row.ingredient_name}: {formatQuantity(row.remaining_quantity)} {row.unit_code} remaining</p>)}
      </div>}
    </section>
  </>
}
