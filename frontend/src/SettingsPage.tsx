import { FormEvent, useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import EquipmentSettingsCard from './EquipmentSettingsCard'
import {
  archiveInventoryLocation,
  archiveShoppingCategory,
  createInventoryLocation,
  createShoppingCategory,
  fetchHousehold,
  fetchInventoryLocations,
  fetchShoppingCategories,
  InventoryLocation,
  ShoppingCategory,
  updateHousehold,
  updateInventoryLocation,
  updateShoppingCategory,
} from './api'

const LOCATION_TYPES = ['PANTRY', 'REFRIGERATOR', 'FREEZER', 'SPICE', 'OTHER']

function CategoryRow({ category }: { category: ShoppingCategory }) {
  const queryClient = useQueryClient()
  const [name, setName] = useState(category.name)
  const updateCategory = useMutation({ mutationFn: updateShoppingCategory, onSuccess: async () => queryClient.invalidateQueries({ queryKey: ['shopping-categories'] }) })
  const archiveCategory = useMutation({ mutationFn: archiveShoppingCategory, onSuccess: async () => queryClient.invalidateQueries({ queryKey: ['shopping-categories'] }) })
  return <div className="editable-row">
    <input value={name} onChange={(event) => setName(event.target.value)} />
    <button type="button" onClick={() => updateCategory.mutate({ ...category, name })}>Save</button>
    <button type="button" className="button-secondary" onClick={() => archiveCategory.mutate(category.id)}>Archive</button>
  </div>
}

function LocationRow({ location, locations }: { location: InventoryLocation; locations: InventoryLocation[] }) {
  const queryClient = useQueryClient()
  const [name, setName] = useState(location.name)
  const [type, setType] = useState(location.location_type)
  const [parentId, setParentId] = useState(location.parent_location_id?.toString() ?? '')
  const updateLocation = useMutation({ mutationFn: updateInventoryLocation, onSuccess: async () => queryClient.invalidateQueries({ queryKey: ['inventory-locations'] }) })
  const archiveLocation = useMutation({ mutationFn: archiveInventoryLocation, onSuccess: async () => queryClient.invalidateQueries({ queryKey: ['inventory-locations'] }) })
  const error = updateLocation.error ?? archiveLocation.error
  return <div className="location-edit-row">
    <input value={name} onChange={(event) => setName(event.target.value)} />
    <select value={type} onChange={(event) => setType(event.target.value)}>{LOCATION_TYPES.map((value) => <option key={value}>{value}</option>)}</select>
    <select value={parentId} onChange={(event) => setParentId(event.target.value)}><option value="">Top level</option>{locations.filter((item) => item.id !== location.id).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
    <button type="button" onClick={() => updateLocation.mutate({ ...location, name, location_type: type, parent_location_id: parentId ? Number(parentId) : null })}>Save</button>
    <button type="button" className="button-secondary" onClick={() => archiveLocation.mutate(location.id)}>Archive</button>
    {error instanceof Error && <small className="field-error">{error.message}</small>}
  </div>
}

export default function SettingsPage() {
  const queryClient = useQueryClient()
  const household = useQuery({ queryKey: ['household'], queryFn: fetchHousehold })
  const categories = useQuery({ queryKey: ['shopping-categories'], queryFn: fetchShoppingCategories })
  const locations = useQuery({ queryKey: ['inventory-locations'], queryFn: fetchInventoryLocations })
  const [householdName, setHouseholdName] = useState('')
  const [defaultServings, setDefaultServings] = useState('4')
  const [categoryName, setCategoryName] = useState('')
  const [locationName, setLocationName] = useState('')
  const [locationType, setLocationType] = useState('OTHER')
  const [parentLocationId, setParentLocationId] = useState('')

  useEffect(() => {
    if (household.data) {
      setHouseholdName(household.data.name)
      setDefaultServings(household.data.default_servings)
    }
  }, [household.data])

  const saveHousehold = useMutation({ mutationFn: updateHousehold, onSuccess: (data) => queryClient.setQueryData(['household'], data) })
  const addCategory = useMutation({ mutationFn: createShoppingCategory, onSuccess: async () => { setCategoryName(''); await queryClient.invalidateQueries({ queryKey: ['shopping-categories'] }) } })
  const addLocation = useMutation({ mutationFn: createInventoryLocation, onSuccess: async () => { setLocationName(''); setParentLocationId(''); await queryClient.invalidateQueries({ queryKey: ['inventory-locations'] }) } })

  function submitHousehold(event: FormEvent) { event.preventDefault(); saveHousehold.mutate({ name: householdName, default_servings: defaultServings }) }
  function submitCategory(event: FormEvent) { event.preventDefault(); addCategory.mutate({ name: categoryName, sort_order: (categories.data?.length ?? 0) * 10 + 10 }) }
  function submitLocation(event: FormEvent) { event.preventDefault(); addLocation.mutate({ name: locationName, location_type: locationType, parent_location_id: parentLocationId ? Number(parentLocationId) : null, sort_order: (locations.data?.length ?? 0) * 10 + 10 }) }
  const error = saveHousehold.error ?? addCategory.error ?? addLocation.error

  return <section className="settings-page">
    <div className="page-card"><p className="eyebrow">Settings</p><h1>Household & Reference Data</h1><p>Configure the shared defaults used by recipes, inventory, planning, and shopping.</p></div>
    {error instanceof Error && <div className="error-banner">{error.message}</div>}
    <div className="settings-grid">
      <section className="settings-card"><h2>Ingredients & Tags</h2><p>Manage canonical ingredients, aliases, default storage, units, and reusable recipe tags.</p><a className="settings-link" href="/settings/ingredients">Manage ingredients & tags</a></section>
      <section className="settings-card"><h2>Household</h2><form onSubmit={submitHousehold} className="form-stack"><label>Household name<input value={householdName} onChange={(event) => setHouseholdName(event.target.value)} required /></label><label>Default servings<input type="number" min="0.1" step="0.1" value={defaultServings} onChange={(event) => setDefaultServings(event.target.value)} required /></label><button type="submit" disabled={saveHousehold.isPending}>Save household</button></form></section>
      <section className="settings-card"><h2>Shopping Categories</h2><form onSubmit={submitCategory} className="inline-form"><input placeholder="New category" value={categoryName} onChange={(event) => setCategoryName(event.target.value)} required /><button type="submit" disabled={addCategory.isPending}>Add</button></form><div className="editable-list">{categories.data?.map((category) => <CategoryRow key={category.id} category={category} />)}</div></section>
      <EquipmentSettingsCard />
      <section className="settings-card settings-card-wide"><h2>Inventory Locations</h2><form onSubmit={submitLocation} className="location-form"><input placeholder="Location name" value={locationName} onChange={(event) => setLocationName(event.target.value)} required /><select value={locationType} onChange={(event) => setLocationType(event.target.value)}>{LOCATION_TYPES.map((type) => <option key={type}>{type}</option>)}</select><select value={parentLocationId} onChange={(event) => setParentLocationId(event.target.value)}><option value="">Top level</option>{locations.data?.map((location) => <option key={location.id} value={location.id}>{location.name}</option>)}</select><button type="submit" disabled={addLocation.isPending}>Add location</button></form><div className="location-list">{locations.data?.map((location) => <LocationRow key={location.id} location={location} locations={locations.data ?? []} />)}</div></section>
    </div>
  </section>
}
