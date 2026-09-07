import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchIngredients } from './api'
import { fetchInventoryHistory, fetchMealHistory } from './historyApi'
import { inventoryHistoryName, signedQuantity, usageTitle } from './historySelectors'

const transactionTypes = ['PURCHASE', 'CONSUME', 'TRANSFER', 'MANUAL_ADD', 'MANUAL_REMOVE', 'CORRECTION', 'PRODUCTION', 'WASTE', 'SPOILAGE']

export default function HistoryPage() {
  const meals = useQuery({ queryKey: ['history', 'meals'], queryFn: fetchMealHistory })
  const ingredients = useQuery({ queryKey: ['ingredients', 'history'], queryFn: () => fetchIngredients('', true) })
  const [ingredientId, setIngredientId] = useState('')
  const [lotId, setLotId] = useState('')
  const [transactionType, setTransactionType] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  const filters = useMemo(() => ({
    ingredient_id: ingredientId ? Number(ingredientId) : undefined,
    lot_id: lotId ? Number(lotId) : undefined,
    transaction_type: transactionType || undefined,
    start_date: startDate || undefined,
    end_date: endDate || undefined,
  }), [ingredientId, lotId, transactionType, startDate, endDate])

  const inventory = useQuery({ queryKey: ['history', 'inventory', filters], queryFn: () => fetchInventoryHistory(filters) })
  const error = meals.error ?? inventory.error

  return <section className="page-card">
    <p className="eyebrow">Audit trail</p>
    <h1>History</h1>
    <p className="planning-note">Completed Meals use immutable completion snapshots. Inventory history shows the durable transaction trail for every lot.</p>

    {error instanceof Error && <div className="error-banner">{error.message}</div>}

    <section className="panel">
      <div className="section-heading"><div><h2>Completed Meals</h2><p className="planning-note">Newest finalized Meal first.</p></div></div>
      {meals.isPending && <p>Loading Meal history…</p>}
      {meals.data?.map((entry) => <article className="settings-card" key={entry.completion_id} style={{ marginBottom: 16 }}>
        <div className="section-heading">
          <div><h3>{entry.meal_name}</h3><p className="planning-note">Finalized {new Date(entry.finalized_at).toLocaleString()} · PlannedMeal {entry.planned_meal_id} · Completion {entry.completion_id}</p></div>
        </div>
        <div className="advanced-grid">
          <div><strong>Planned servings</strong><p>{entry.planned_servings}</p></div>
          <div><strong>Planned leftovers</strong><p>{entry.planned_leftover_servings}</p></div>
          <div><strong>Actual produced</strong><p>{entry.actual_servings_produced ?? 'Not recorded'}</p></div>
          <div><strong>Actual eaten</strong><p>{entry.actual_servings_eaten ?? 'Not recorded'}</p></div>
        </div>

        <h4>Actual Ingredient usage</h4>
        {entry.usages.map((usage, index) => <div className="inventory-history-row" key={`${entry.completion_id}-${index}`}>
          <strong>{usageTitle(usage)}</strong>
          <span>Actual {usage.actual_quantity} {usage.actual_unit_code}</span>
          <span>Planned {usage.planned_quantity} {usage.planned_unit_code} {usage.planned_ingredient_name}</span>
          <span>{usage.allocations.length ? `Lots: ${usage.allocations.map((row) => `#${row.lot_id} (${row.source_quantity} ${row.source_unit_code})`).join(', ')}` : 'No Inventory allocation recorded'}</span>
          {usage.notes && <span>Notes: {usage.notes}</span>}
        </div>)}

        {entry.leftover && <div style={{ marginTop: 12 }}>
          <h4>Leftover produced</h4>
          <p className="planning-note">{entry.leftover.leftover_servings} {entry.leftover.serving_unit} · Lot {entry.leftover.inventory_lot_id ?? 'none'} · Use-by {entry.leftover.expiration_date ?? 'not set'}{entry.leftover.notes ? ` · ${entry.leftover.notes}` : ''}</p>
        </div>}

        {entry.outputs.length > 0 && <div style={{ marginTop: 12 }}>
          <h4>Recipe outputs</h4>
          {entry.outputs.map((output) => <p className="planning-note" key={output.id}>{output.recipe_name} · {output.output_name}: {output.actual_quantity} {output.unit_code}{output.quantity_overridden ? ' (adjusted)' : ''} · Lot {output.inventory_lot_id ?? 'none'}</p>)}
        </div>}

        {entry.production_committed_at && <p className="planning-note">Production committed {new Date(entry.production_committed_at).toLocaleString()}.</p>}
      </article>)}
      {!meals.isPending && meals.data?.length === 0 && <p className="planning-note">No finalized Meals yet.</p>}
    </section>

    <section className="panel" style={{ marginTop: 20 }}>
      <div className="section-heading"><div><h2>Inventory transactions</h2><p className="planning-note">Filter the immutable lot transaction trail.</p></div></div>
      <div className="advanced-grid">
        <label>Ingredient<select value={ingredientId} onChange={(event) => setIngredientId(event.target.value)}><option value="">All Ingredients</option>{ingredients.data?.map((item) => <option key={item.id} value={item.id}>{item.name}{item.active ? '' : ' (archived)'}</option>)}</select></label>
        <label>Lot ID<input type="number" min="1" step="1" value={lotId} onChange={(event) => setLotId(event.target.value)} /></label>
        <label>Transaction type<select value={transactionType} onChange={(event) => setTransactionType(event.target.value)}><option value="">All transaction types</option>{transactionTypes.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
        <label>From date<input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label>
        <label>Through date<input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} /></label>
      </div>

      {inventory.isPending && <p>Loading Inventory history…</p>}
      {inventory.data?.map((row) => <div className="inventory-history-row" key={row.transaction_id}>
        <strong>{row.transaction_type} · Lot {row.lot_id} · {inventoryHistoryName(row)}</strong>
        <span>{new Date(row.created_at).toLocaleString()}</span>
        <span>{signedQuantity(row)}</span>
        <span>Source: {row.source_type}{row.source_name ? ` · ${row.source_name}` : ''}{row.source_id ? ` · record ${row.source_id}` : ''}</span>
        {(row.from_location_name || row.to_location_name) && <span>Location: {row.from_location_name ?? '—'} → {row.to_location_name ?? '—'}</span>}
        {row.reason && <span>Reason: {row.reason}</span>}
        {row.note && <span>Note: {row.note}</span>}
        <span>Transaction {row.transaction_id}</span>
      </div>)}
      {!inventory.isPending && inventory.data?.length === 0 && <p className="planning-note">No Inventory transactions match these filters.</p>}
    </section>
  </section>
}
