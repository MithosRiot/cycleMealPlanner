import { FormEvent, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  addInventory,
  correctInventory,
  createInventoryLot,
  fetchIngredients,
  fetchInventory,
  fetchInventoryLocations,
  fetchMeasurementUnits,
  InventoryLot,
  removeInventory,
  transferInventory,
} from './api'

type ViewMode = 'ingredient' | 'location'

export default function InventoryPage() {
  const queryClient = useQueryClient()
  const [viewMode, setViewMode] = useState<ViewMode>('ingredient')
  const [ingredientFilter, setIngredientFilter] = useState('')
  const [locationFilter, setLocationFilter] = useState('')
  const [ingredientId, setIngredientId] = useState('')
  const [locationId, setLocationId] = useState('')
  const [quantity, setQuantity] = useState('')
  const [unitId, setUnitId] = useState('')
  const [purchaseDate, setPurchaseDate] = useState('')
  const [expirationDate, setExpirationDate] = useState('')
  const [notes, setNotes] = useState('')
  const [purchase, setPurchase] = useState(true)

  const ingredients = useQuery({ queryKey: ['ingredients', 'inventory'], queryFn: () => fetchIngredients() })
  const locations = useQuery({ queryKey: ['inventory-locations'], queryFn: fetchInventoryLocations })
  const units = useQuery({ queryKey: ['measurement-units'], queryFn: fetchMeasurementUnits })
  const lots = useQuery({
    queryKey: ['inventory', ingredientFilter, locationFilter],
    queryFn: () => fetchInventory({
      ingredient_id: ingredientFilter ? Number(ingredientFilter) : undefined,
      location_id: locationFilter ? Number(locationFilter) : undefined,
    }),
  })

  const refresh = async () => queryClient.invalidateQueries({ queryKey: ['inventory'] })
  const createLot = useMutation({
    mutationFn: createInventoryLot,
    onSuccess: async () => {
      setQuantity('')
      setNotes('')
      setExpirationDate('')
      await refresh()
    },
  })
  const adjust = useMutation({
    mutationFn: async (action: { lot: InventoryLot; kind: 'add' | 'remove' | 'correct'; value: string }) => {
      if (action.kind === 'add') return addInventory(action.lot.id, action.value)
      if (action.kind === 'remove') return removeInventory(action.lot.id, action.value)
      return correctInventory(action.lot.id, action.value)
    },
    onSuccess: refresh,
  })
  const move = useMutation({
    mutationFn: ({ lot, target }: { lot: InventoryLot; target: number }) => transferInventory(lot.id, target),
    onSuccess: refresh,
  })

  const ingredientNames = useMemo(() => new Map((ingredients.data ?? []).map((item) => [item.id, item.name])), [ingredients.data])
  const locationNames = useMemo(() => new Map((locations.data ?? []).map((item) => [item.id, item.name])), [locations.data])
  const unitCodes = useMemo(() => new Map((units.data ?? []).map((item) => [item.id, item.code])), [units.data])

  function submitLot(event: FormEvent) {
    event.preventDefault()
    createLot.mutate({
      ingredient_id: Number(ingredientId),
      location_id: Number(locationId),
      quantity,
      unit_id: Number(unitId),
      purchase_date: purchaseDate || null,
      opened_date: null,
      expiration_date: expirationDate || null,
      frozen_date: null,
      thawed_date: null,
      notes: notes || null,
      transaction_type: purchase ? 'PURCHASE' : 'MANUAL_ADD',
    })
  }

  const grouped = useMemo(() => {
    const data = lots.data ?? []
    const groups = new Map<string, InventoryLot[]>()
    for (const lot of data) {
      const key = viewMode === 'ingredient'
        ? ingredientNames.get(lot.ingredient_id) ?? `Ingredient ${lot.ingredient_id}`
        : locationNames.get(lot.location_id) ?? `Location ${lot.location_id}`
      groups.set(key, [...(groups.get(key) ?? []), lot])
    }
    return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b))
  }, [lots.data, viewMode, ingredientNames, locationNames])

  const error = createLot.error ?? adjust.error ?? move.error

  return (
    <section className="inventory-page">
      <div className="page-card">
        <p className="eyebrow">Inventory</p>
        <h1>Physical Inventory</h1>
        <p>Track distinct lots across pantry, refrigerator, freezer, and other storage locations.</p>
      </div>

      {error instanceof Error && <div className="error-banner">{error.message}</div>}

      <section className="settings-card">
        <div className="section-heading">
          <div>
            <h2>Add inventory</h2>
            <p className="muted-line">Record an actual purchase or manual starting quantity.</p>
          </div>
        </div>
        <form className="inventory-add-form" onSubmit={submitLot}>
          <select value={ingredientId} onChange={(e) => setIngredientId(e.target.value)} required>
            <option value="">Ingredient</option>
            {ingredients.data?.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
          <select value={locationId} onChange={(e) => setLocationId(e.target.value)} required>
            <option value="">Location</option>
            {locations.data?.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
          <input type="number" min="0.000001" step="any" placeholder="Quantity" value={quantity} onChange={(e) => setQuantity(e.target.value)} required />
          <select value={unitId} onChange={(e) => setUnitId(e.target.value)} required>
            <option value="">Unit</option>
            {units.data?.map((item) => <option key={item.id} value={item.id}>{item.code}</option>)}
          </select>
          <label>Purchase date<input type="date" value={purchaseDate} onChange={(e) => setPurchaseDate(e.target.value)} /></label>
          <label>Expiration date<input type="date" value={expirationDate} onChange={(e) => setExpirationDate(e.target.value)} /></label>
          <input placeholder="Notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
          <label className="check-label"><input type="checkbox" checked={purchase} onChange={(e) => setPurchase(e.target.checked)} /> Purchase</label>
          <button type="submit" disabled={createLot.isPending}>Add lot</button>
        </form>
      </section>

      <section className="settings-card">
        <div className="inventory-toolbar">
          <div className="segmented-control">
            <button type="button" className={viewMode === 'ingredient' ? '' : 'button-secondary'} onClick={() => setViewMode('ingredient')}>By ingredient</button>
            <button type="button" className={viewMode === 'location' ? '' : 'button-secondary'} onClick={() => setViewMode('location')}>By location</button>
          </div>
          <select value={ingredientFilter} onChange={(e) => setIngredientFilter(e.target.value)}>
            <option value="">All ingredients</option>
            {ingredients.data?.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
          <select value={locationFilter} onChange={(e) => setLocationFilter(e.target.value)}>
            <option value="">All locations</option>
            {locations.data?.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </div>

        <div className="inventory-groups">
          {grouped.map(([group, groupLots]) => (
            <div className="inventory-group" key={group}>
              <h3>{group}</h3>
              {groupLots.map((lot) => (
                <InventoryLotRow
                  key={lot.id}
                  lot={lot}
                  ingredientName={ingredientNames.get(lot.ingredient_id) ?? 'Unknown'}
                  locationName={locationNames.get(lot.location_id) ?? 'Unknown'}
                  unitCode={unitCodes.get(lot.unit_id) ?? ''}
                  locations={locations.data ?? []}
                  onAdjust={(kind, value) => adjust.mutate({ lot, kind, value })}
                  onMove={(target) => move.mutate({ lot, target })}
                />
              ))}
            </div>
          ))}
          {!lots.isPending && grouped.length === 0 && <p className="muted-line">No inventory lots match the current filters.</p>}
        </div>
      </section>
    </section>
  )
}

function InventoryLotRow({ lot, ingredientName, locationName, unitCode, locations, onAdjust, onMove }: {
  lot: InventoryLot
  ingredientName: string
  locationName: string
  unitCode: string
  locations: { id: number; name: string }[]
  onAdjust: (kind: 'add' | 'remove' | 'correct', value: string) => void
  onMove: (target: number) => void
}) {
  const [value, setValue] = useState('')
  const [target, setTarget] = useState(String(lot.location_id))
  return (
    <div className="inventory-lot-row">
      <div>
        <strong>{ingredientName}</strong>
        <div className="muted-line">{lot.quantity} {unitCode} · {locationName}{lot.expiration_date ? ` · expires ${lot.expiration_date}` : ''}</div>
        {lot.notes && <div className="muted-line">{lot.notes}</div>}
      </div>
      <div className="inventory-actions">
        <input type="number" min="0" step="any" placeholder="Qty" value={value} onChange={(e) => setValue(e.target.value)} />
        <button type="button" disabled={!value} onClick={() => { onAdjust('add', value); setValue('') }}>Add</button>
        <button type="button" className="button-secondary" disabled={!value} onClick={() => { onAdjust('remove', value); setValue('') }}>Remove</button>
        <button type="button" className="button-secondary" disabled={!value} onClick={() => { onAdjust('correct', value); setValue('') }}>Correct to</button>
      </div>
      <div className="inventory-actions">
        <select value={target} onChange={(e) => setTarget(e.target.value)}>
          {locations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
        <button type="button" className="button-secondary" disabled={Number(target) === lot.location_id} onClick={() => onMove(Number(target))}>Move</button>
      </div>
    </div>
  )
}
