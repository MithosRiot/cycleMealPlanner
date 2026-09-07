import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchIngredients, fetchInventoryLocations, fetchMeasurementUnits } from './api'
import ManualShoppingPanel from './ManualShoppingPanel'
import { fetchMealCycles } from './mealCyclesApi'
import { adjustShoppingItem, completeShoppingItem, fetchShoppingList, regenerateShoppingList, skipShoppingItem, type ShoppingItem } from './shoppingApi'
import './ShoppingPage.css'

type IntakeDraft = {
  quantity: string
  unitId: string
  ingredientId: string
  satisfiedQuantity: string
  satisfiedUnitId: string
  locationId: string
  purchaseDate: string
  expirationDate: string
  notes: string
}

export default function ShoppingPage() {
  const queryClient = useQueryClient()
  const cycles = useQuery({ queryKey: ['meal-cycles'], queryFn: fetchMealCycles })
  const units = useQuery({ queryKey: ['measurement-units'], queryFn: fetchMeasurementUnits })
  const locations = useQuery({ queryKey: ['inventory-locations'], queryFn: fetchInventoryLocations })
  const ingredients = useQuery({ queryKey: ['ingredients', 'shopping'], queryFn: () => fetchIngredients() })
  const [cycleId, setCycleId] = useState<number | null>(null)
  const [adjustments, setAdjustments] = useState<Record<number, string>>({})
  const [intake, setIntake] = useState<Record<number, IntakeDraft>>({})
  const shopping = useQuery({ queryKey: ['shopping-list', cycleId], queryFn: () => fetchShoppingList(cycleId as number), enabled: cycleId !== null, retry: false })

  const setList = (data: NonNullable<typeof shopping.data>) => queryClient.setQueryData(['shopping-list', cycleId], data)
  const regenerate = useMutation({ mutationFn: () => regenerateShoppingList(cycleId as number), onSuccess: setList })
  const adjust = useMutation({ mutationFn: ({ itemId, value }: { itemId: number; value: string }) => adjustShoppingItem(cycleId as number, itemId, value), onSuccess: setList })
  const complete = useMutation({
    mutationFn: ({ item, draft }: { item: ShoppingItem; draft: IntakeDraft }) => completeShoppingItem(cycleId as number, item.id, {
      actual_quantity: draft.quantity,
      actual_unit_id: Number(draft.unitId),
      purchased_ingredient_id: Number(draft.ingredientId),
      satisfied_quantity: draft.satisfiedQuantity,
      satisfied_unit_id: Number(draft.satisfiedUnitId),
      storage_location_id: Number(draft.locationId),
      purchase_date: draft.purchaseDate || null,
      expiration_date: draft.expirationDate || null,
      notes: draft.notes.trim() || null,
      idempotency_key: crypto.randomUUID(),
    }),
    onSuccess: (data, variables) => {
      setList(data)
      setIntake((current) => { const next = { ...current }; delete next[variables.item.id]; return next })
      queryClient.invalidateQueries({ queryKey: ['inventory'] })
      queryClient.invalidateQueries({ queryKey: ['inventory-availability'] })
      queryClient.invalidateQueries({ queryKey: ['cycle-validation', cycleId] })
    },
  })
  const skip = useMutation({ mutationFn: (itemId: number) => skipShoppingItem(cycleId as number, itemId), onSuccess: setList })

  const grouped = useMemo(() => {
    const result = new Map<string, NonNullable<typeof shopping.data>['items']>()
    for (const item of shopping.data?.items ?? []) { const list = result.get(item.shopping_category_name) ?? []; list.push(item); result.set(item.shopping_category_name, list) }
    return [...result.entries()]
  }, [shopping.data])

  const draftFor = (item: ShoppingItem): IntakeDraft => intake[item.id] ?? {
    quantity: item.final_quantity,
    unitId: String(item.unit_id),
    ingredientId: String(item.ingredient_id),
    satisfiedQuantity: item.final_quantity,
    satisfiedUnitId: String(item.unit_id),
    locationId: '', purchaseDate: '', expirationDate: '', notes: '',
  }
  const patchDraft = (item: ShoppingItem, patch: Partial<IntakeDraft>) => setIntake((current) => ({ ...current, [item.id]: { ...draftFor(item), ...patch } }))

  const error = regenerate.error || adjust.error || complete.error || skip.error
  const purchaseCount = shopping.data?.items.reduce((count, item) => count + item.purchases.length, 0) ?? 0
  const changedCount = shopping.data?.items.filter((item) => Number(item.plan_delta_quantity) !== 0).length ?? 0

  return <section className="shopping-page">
    <header className="page-heading"><div><p className="eyebrow">Inventory-aware</p><h1>Shopping</h1><p>Generate shortages, record partial purchases or substitutions, and keep plan changes separate from purchase history.</p></div></header>
    <section className="settings-card shopping-toolbar">
      <label>Meal cycle<select value={cycleId ?? ''} onChange={(event) => setCycleId(event.target.value ? Number(event.target.value) : null)}><option value="">Choose a cycle…</option>{cycles.data?.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.name}</option>)}</select></label>
      <button type="button" disabled={cycleId === null || regenerate.isPending} onClick={() => regenerate.mutate()}>{shopping.data ? 'Regenerate list' : 'Generate list'}</button>
    </section>
    {cycleId !== null && <ManualShoppingPanel cycleId={cycleId} />}
    {cycleId !== null && shopping.isError && !regenerate.isPending && <div className="empty-state shopping-empty"><p>No generated shopping list for this cycle yet.</p><button type="button" onClick={() => regenerate.mutate()}>Generate shopping list</button></div>}
    {error && <div className="error-banner">{(error as Error).message}</div>}
    {shopping.data && <>
      <div className="shopping-summary"><strong>{shopping.data.meal_cycle_name}</strong><span>{shopping.data.items.filter((item) => item.status === 'PENDING' && Number(item.remaining_quantity) > 0).length} pending generated items</span><span>{purchaseCount} generated purchase record{purchaseCount === 1 ? '' : 's'}</span><span>{changedCount} plan change{changedCount === 1 ? '' : 's'}</span></div>
      <div className="shopping-groups">{grouped.map(([category, items]) => <section className="settings-card shopping-category" key={category}><h2>{category}</h2><div className="shopping-items">{items.map((item) => {
        const draft = draftFor(item); const activeLocations = locations.data?.filter((location) => location.active) ?? []; const terminal = item.status !== 'PENDING'; const delta = Number(item.plan_delta_quantity); const excess = Number(item.purchased_excess_quantity); const substitution = Number(draft.ingredientId) !== item.ingredient_id; const actualIngredient = ingredients.data?.find((value) => value.id === Number(draft.ingredientId)); const actualFamily = units.data?.find((value) => value.id === actualIngredient?.preferred_unit_id)?.unit_family; const purchaseUnits = units.data?.filter((unit) => !substitution || !actualFamily || unit.unit_family === actualFamily) ?? []; const satisfactionUnits = units.data?.filter((unit) => unit.unit_family === item.unit_family) ?? []
        return <article className={`shopping-item ${terminal ? 'shopping-item-terminal' : Number(item.remaining_quantity) <= 0 ? 'covered' : ''}`} key={item.id}>
          <div><div className="shopping-title-row"><strong>{item.ingredient_name}</strong><span className={`shopping-status ${item.status.toLowerCase()}`}>{item.status}</span></div><div className="shopping-math">Need {Number(item.required_quantity).toLocaleString()} {item.unit_code} · Have {Number(item.inventory_quantity).toLocaleString()} {item.unit_code}</div>
            {Number(item.satisfied_quantity) > 0 && <div className="planning-note">Purchased toward demand: {Number(item.satisfied_quantity).toLocaleString()} {item.unit_code} · Remaining: {Number(item.remaining_quantity).toLocaleString()} {item.unit_code}</div>}
            {delta !== 0 && <div className={delta > 0 ? 'warning-text' : 'planning-note'}>Plan changed: {delta > 0 ? '+' : ''}{delta.toLocaleString()} {item.unit_code} required since this Shopping list was first generated.</div>}{excess > 0 && <div className="planning-note">Already purchased excess: {excess.toLocaleString()} {item.unit_code} relative to the current plan.</div>}{item.warning && <div className="warning-text">{item.warning}</div>}
            <details><summary>Current sources</summary><ul>{(JSON.parse(item.source_trace) as Array<{ day_number?: number; meal_name?: string; quantity?: string; source?: string }>).map((source, index) => <li key={`${source.day_number ?? source.source}-${source.meal_name ?? ''}-${index}`}>{source.source === 'STAPLE' ? 'Staple stock rule' : `Day ${source.day_number}: ${source.meal_name} (${source.quantity})`}</li>)}</ul></details>
            {item.purchases.length > 0 && <details open><summary>Purchase history ({item.purchases.length})</summary>{item.purchases.map((purchase) => <div className="purchase-record" key={purchase.id}>{purchase.purchase_kind === 'SUBSTITUTION' ? `Substituted ${purchase.purchased_ingredient_name}: ` : 'Purchased '}{Number(purchase.actual_quantity).toLocaleString()} {purchase.actual_unit_code} · satisfies {Number(purchase.satisfied_quantity).toLocaleString()} {purchase.satisfied_unit_code} · Inventory lot #{purchase.inventory_lot_id}</div>)}</details>}
          </div>
          <div className="shopping-quantity"><span className="generated-quantity">Remaining to buy: {Number(item.remaining_quantity).toLocaleString()} {item.unit_code}</span>{!terminal && <><label>Adjustment<input type="number" step="0.001" value={adjustments[item.id] ?? item.adjustment_quantity} onChange={(event) => setAdjustments({ ...adjustments, [item.id]: event.target.value })} /></label><button type="button" className="button-secondary" onClick={() => adjust.mutate({ itemId: item.id, value: adjustments[item.id] ?? item.adjustment_quantity })}>Save adjustment</button>
            <div className="shopping-intake"><label>Ingredient purchased<select value={draft.ingredientId} onChange={(event) => { const ingredientId = event.target.value; const selected = ingredients.data?.find((value) => value.id === Number(ingredientId)); patchDraft(item, { ingredientId, unitId: selected?.preferred_unit_id ? String(selected.preferred_unit_id) : draft.unitId }) }}><option value={item.ingredient_id}>{item.ingredient_name} (planned)</option>{ingredients.data?.filter((value) => value.id !== item.ingredient_id).map((value) => <option key={value.id} value={value.id}>{value.name}</option>)}</select></label>
              <label>Actually purchased<input type="number" min="0.001" step="0.001" value={draft.quantity} onChange={(event) => patchDraft(item, { quantity: event.target.value })} /></label><label>Purchase unit<select value={draft.unitId} onChange={(event) => patchDraft(item, { unitId: event.target.value })}>{purchaseUnits.map((unit) => <option key={unit.id} value={unit.id}>{unit.code}</option>)}</select></label>
              {substitution && <><label>Satisfies original demand<input type="number" min="0.001" step="0.001" value={draft.satisfiedQuantity} onChange={(event) => patchDraft(item, { satisfiedQuantity: event.target.value })} /></label><label>Original-demand unit<select value={draft.satisfiedUnitId} onChange={(event) => patchDraft(item, { satisfiedUnitId: event.target.value })}>{satisfactionUnits.map((unit) => <option key={unit.id} value={unit.id}>{unit.code}</option>)}</select></label></>}
              <label>Storage location<select value={draft.locationId} onChange={(event) => patchDraft(item, { locationId: event.target.value })}><option value="">Choose…</option>{activeLocations.map((location) => <option key={location.id} value={location.id}>{location.name}</option>)}</select></label><label>Purchase date<input type="date" value={draft.purchaseDate} onChange={(event) => patchDraft(item, { purchaseDate: event.target.value })} /></label><label>Expiration date<input type="date" value={draft.expirationDate} onChange={(event) => patchDraft(item, { expirationDate: event.target.value })} /></label><label>Notes<textarea value={draft.notes} onChange={(event) => patchDraft(item, { notes: event.target.value })} /></label>
              <div className="shopping-intake-actions"><button type="button" disabled={!draft.quantity || !draft.unitId || !draft.locationId || !draft.satisfiedQuantity || !draft.satisfiedUnitId || complete.isPending} onClick={() => complete.mutate({ item, draft })}>Record purchase</button><button type="button" className="button-secondary" disabled={skip.isPending} onClick={() => skip.mutate(item.id)}>Skip</button></div></div></>}</div>
        </article>})}</div></section>)}{shopping.data.items.length === 0 && <div className="empty-state">This cycle has no planned ingredient requirements yet.</div>}</div>
    </>}
  </section>
}