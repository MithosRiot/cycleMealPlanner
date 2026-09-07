import { FormEvent, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchIngredients, fetchInventoryLocations, fetchMeasurementUnits, fetchShoppingCategories } from './api'
import {
  completeManualShopping,
  createManualShopping,
  deleteManualShopping,
  fetchManualShopping,
  manualShoppingDisplayQuantity,
  skipManualShopping,
  updateManualShopping,
  type ManualShoppingItem,
  type ManualShoppingWrite,
} from './manualShoppingApi'

type Draft = {
  name: string
  quantity: string
  unitId: string
  categoryId: string
  ingredientId: string
  notes: string
}

type IntakeDraft = {
  createInventory: boolean
  quantity: string
  unitId: string
  locationId: string
  purchaseDate: string
  expirationDate: string
  notes: string
}

const emptyDraft: Draft = { name: '', quantity: '1', unitId: '', categoryId: '', ingredientId: '', notes: '' }

export default function ManualShoppingPanel({ cycleId }: { cycleId: number }) {
  const queryClient = useQueryClient()
  const manual = useQuery({ queryKey: ['manual-shopping', cycleId], queryFn: () => fetchManualShopping(cycleId) })
  const units = useQuery({ queryKey: ['measurement-units'], queryFn: fetchMeasurementUnits })
  const categories = useQuery({ queryKey: ['shopping-categories'], queryFn: fetchShoppingCategories })
  const ingredients = useQuery({ queryKey: ['ingredients', 'manual-shopping'], queryFn: () => fetchIngredients() })
  const locations = useQuery({ queryKey: ['inventory-locations'], queryFn: fetchInventoryLocations })
  const [draft, setDraft] = useState<Draft>(emptyDraft)
  const [editId, setEditId] = useState<number | null>(null)
  const [intake, setIntake] = useState<Record<number, IntakeDraft>>({})

  const toWrite = (value: Draft): ManualShoppingWrite => ({
    name: value.name.trim(),
    quantity: value.quantity,
    unit_id: value.unitId ? Number(value.unitId) : null,
    shopping_category_id: value.categoryId ? Number(value.categoryId) : null,
    ingredient_id: value.ingredientId ? Number(value.ingredientId) : null,
    notes: value.notes.trim() || null,
  })

  const setData = (data: NonNullable<typeof manual.data>) => queryClient.setQueryData(['manual-shopping', cycleId], data)
  const refreshRelated = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['inventory'] }),
      queryClient.invalidateQueries({ queryKey: ['inventory-availability'] }),
      queryClient.invalidateQueries({ queryKey: ['dashboard-use-soon'] }),
      queryClient.invalidateQueries({ queryKey: ['history', 'inventory'] }),
    ])
  }

  const create = useMutation({ mutationFn: (input: ManualShoppingWrite) => createManualShopping(cycleId, input), onSuccess: (data) => { setData(data); setDraft(emptyDraft) } })
  const update = useMutation({ mutationFn: ({ itemId, input }: { itemId: number; input: ManualShoppingWrite }) => updateManualShopping(cycleId, itemId, input), onSuccess: (data) => { setData(data); setEditId(null); setDraft(emptyDraft) } })
  const remove = useMutation({ mutationFn: (itemId: number) => deleteManualShopping(cycleId, itemId), onSuccess: async () => queryClient.invalidateQueries({ queryKey: ['manual-shopping', cycleId] }) })
  const skip = useMutation({ mutationFn: (itemId: number) => skipManualShopping(cycleId, itemId), onSuccess: setData })
  const complete = useMutation({
    mutationFn: ({ item, value }: { item: ManualShoppingItem; value: IntakeDraft }) => completeManualShopping(cycleId, item.id, value.createInventory ? {
      inventory_quantity: value.quantity,
      inventory_unit_id: Number(value.unitId),
      storage_location_id: Number(value.locationId),
      purchase_date: value.purchaseDate || null,
      expiration_date: value.expirationDate || null,
      inventory_notes: value.notes.trim() || null,
    } : {
      inventory_quantity: null,
      inventory_unit_id: null,
      storage_location_id: null,
      purchase_date: null,
      expiration_date: null,
      inventory_notes: null,
    }),
    onSuccess: async (data, variables) => {
      setData(data)
      setIntake((current) => { const next = { ...current }; delete next[variables.item.id]; return next })
      await refreshRelated()
    },
  })

  const startEdit = (item: ManualShoppingItem) => {
    setEditId(item.id)
    setDraft({ name: item.name, quantity: item.quantity, unitId: item.unit_id ? String(item.unit_id) : '', categoryId: item.shopping_category_id ? String(item.shopping_category_id) : '', ingredientId: item.ingredient_id ? String(item.ingredient_id) : '', notes: item.notes ?? '' })
  }

  const intakeFor = (item: ManualShoppingItem): IntakeDraft => intake[item.id] ?? {
    createInventory: false,
    quantity: item.quantity,
    unitId: item.unit_id ? String(item.unit_id) : (ingredients.data?.find((row) => row.id === item.ingredient_id)?.preferred_unit_id ? String(ingredients.data?.find((row) => row.id === item.ingredient_id)?.preferred_unit_id) : ''),
    locationId: '', purchaseDate: '', expirationDate: '', notes: item.notes ?? '',
  }
  const patchIntake = (item: ManualShoppingItem, patch: Partial<IntakeDraft>) => setIntake((current) => ({ ...current, [item.id]: { ...intakeFor(item), ...patch } }))

  const grouped = useMemo(() => {
    const result = new Map<string, ManualShoppingItem[]>()
    for (const item of manual.data?.items ?? []) {
      const rows = result.get(item.shopping_category_name) ?? []
      rows.push(item)
      result.set(item.shopping_category_name, rows)
    }
    return [...result.entries()]
  }, [manual.data])

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (editId === null) create.mutate(toWrite(draft))
    else update.mutate({ itemId: editId, input: toWrite(draft) })
  }

  const error = manual.error ?? create.error ?? update.error ?? remove.error ?? skip.error ?? complete.error

  return <section className="settings-card">
    <div className="section-heading"><div><h2>Manual Shopping items</h2><p className="planning-note">Household items outside generated Meal-cycle demand. Regenerating the list does not change these items.</p></div><div className="ingredient-meta"><span>{manual.data?.items.filter((item) => item.status === 'PENDING').length ?? 0} pending</span></div></div>
    {error instanceof Error && <div className="error-banner">{error.message}</div>}
    <form className="inventory-add-form" onSubmit={submit}>
      <input placeholder="Item name" value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} required />
      <input type="number" min="0.001" step="0.001" placeholder="Quantity" value={draft.quantity} onChange={(event) => setDraft({ ...draft, quantity: event.target.value })} required />
      <select value={draft.unitId} onChange={(event) => setDraft({ ...draft, unitId: event.target.value })}><option value="">No unit</option>{units.data?.map((unit) => <option key={unit.id} value={unit.id}>{unit.code}</option>)}</select>
      <select value={draft.categoryId} onChange={(event) => setDraft({ ...draft, categoryId: event.target.value })}><option value="">Uncategorized</option>{categories.data?.filter((category) => category.active).map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select>
      <select value={draft.ingredientId} onChange={(event) => setDraft({ ...draft, ingredientId: event.target.value })}><option value="">Not linked to Inventory Ingredient</option>{ingredients.data?.filter((ingredient) => ingredient.active).map((ingredient) => <option key={ingredient.id} value={ingredient.id}>{ingredient.name}</option>)}</select>
      <input placeholder="Notes (optional)" value={draft.notes} onChange={(event) => setDraft({ ...draft, notes: event.target.value })} />
      <button type="submit" disabled={!draft.name.trim() || !draft.quantity || create.isPending || update.isPending}>{editId === null ? 'Add manual item' : 'Save manual item'}</button>
      {editId !== null && <button type="button" className="button-secondary" onClick={() => { setEditId(null); setDraft(emptyDraft) }}>Cancel edit</button>}
    </form>

    {manual.isPending && <p className="muted-line">Loading manual Shopping items…</p>}
    <div className="shopping-groups">{grouped.map(([category, items]) => <section className="shopping-category" key={`manual-${category}`}><h3>{category}</h3><div className="shopping-items">{items.map((item) => {
      const value = intakeFor(item)
      const terminal = item.status !== 'PENDING'
      const intakeReady = !value.createInventory || (item.ingredient_id !== null && !!value.quantity && !!value.unitId && !!value.locationId)
      return <article className={`shopping-item ${terminal ? 'shopping-item-terminal' : ''}`} key={`manual-item-${item.id}`}>
        <div>
          <div className="shopping-title-row"><strong>{item.name}</strong><span className={`shopping-status ${item.status.toLowerCase()}`}>{item.status}</span></div>
          <div className="shopping-math">Manual · {manualShoppingDisplayQuantity(item)}{item.ingredient_name ? ` · Linked Ingredient: ${item.ingredient_name}` : ' · No Inventory link'}</div>
          {item.notes && <div className="planning-note">{item.notes}</div>}
          {item.inventory_lot_id && <div className="planning-note">Inventory lot #{item.inventory_lot_id} · {item.storage_location_name ?? 'Unknown location'}{item.purchase_date ? ` · purchased ${item.purchase_date}` : ''}{item.expiration_date ? ` · expires ${item.expiration_date}` : ''}</div>}
          {item.completed_at && <div className="muted-line">Closed {new Date(item.completed_at).toLocaleString()}</div>}
        </div>
        {!terminal && <div className="shopping-quantity">
          <div className="shopping-intake-actions"><button type="button" className="button-secondary" onClick={() => startEdit(item)}>Edit</button><button type="button" className="button-secondary" disabled={remove.isPending} onClick={() => remove.mutate(item.id)}>Remove</button></div>
          {item.ingredient_id !== null && <label className="check-label"><input type="checkbox" checked={value.createInventory} onChange={(event) => patchIntake(item, { createInventory: event.target.checked })} /> Add purchased quantity to Inventory</label>}
          {value.createInventory && item.ingredient_id !== null && <div className="shopping-intake">
            <label>Inventory quantity<input type="number" min="0.001" step="0.001" value={value.quantity} onChange={(event) => patchIntake(item, { quantity: event.target.value })} /></label>
            <label>Inventory unit<select value={value.unitId} onChange={(event) => patchIntake(item, { unitId: event.target.value })}><option value="">Choose…</option>{units.data?.map((unit) => <option key={unit.id} value={unit.id}>{unit.code}</option>)}</select></label>
            <label>Storage location<select value={value.locationId} onChange={(event) => patchIntake(item, { locationId: event.target.value })}><option value="">Choose…</option>{locations.data?.filter((location) => location.active).map((location) => <option key={location.id} value={location.id}>{location.name}</option>)}</select></label>
            <label>Purchase date<input type="date" value={value.purchaseDate} onChange={(event) => patchIntake(item, { purchaseDate: event.target.value })} /></label>
            <label>Expiration date<input type="date" value={value.expirationDate} onChange={(event) => patchIntake(item, { expirationDate: event.target.value })} /></label>
            <label>Inventory notes<textarea value={value.notes} onChange={(event) => patchIntake(item, { notes: event.target.value })} /></label>
          </div>}
          <div className="shopping-intake-actions"><button type="button" disabled={!intakeReady || complete.isPending} onClick={() => complete.mutate({ item, value })}>Complete</button><button type="button" className="button-secondary" disabled={skip.isPending} onClick={() => skip.mutate(item.id)}>Skip</button></div>
        </div>}
      </article>
    })}</div></section>)}{!manual.isPending && (manual.data?.items.length ?? 0) === 0 && <p className="muted-line">No manual Shopping items for this cycle.</p>}</div>
  </section>
}
