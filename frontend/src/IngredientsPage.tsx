import { FormEvent, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  archiveIngredient,
  archiveTag,
  createIngredient,
  createTag,
  fetchIngredients,
  fetchInventoryLocations,
  fetchMeasurementUnits,
  fetchShoppingCategories,
  fetchTags,
  Ingredient,
  IngredientInput,
  Tag,
  updateIngredient,
  updateTag,
} from './api'

type StapleFields = {
  staple_enabled: boolean
  staple_minimum: string | null
  staple_target: string | null
  staple_unit_id: number | null
}
type StapleIngredient = Ingredient & StapleFields
type StapleIngredientInput = IngredientInput & StapleFields

const EMPTY_FORM: StapleIngredientInput = {
  name: '',
  shopping_category_id: null,
  preferred_unit_id: null,
  default_location_id: null,
  perishable: false,
  staple_enabled: false,
  staple_minimum: null,
  staple_target: null,
  staple_unit_id: null,
  notes: null,
  aliases: [],
}

const TAG_CATEGORIES = ['CUISINE', 'PROTEIN', 'STYLE', 'PREFERENCE', 'CUSTOM']

export default function IngredientsPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [includeInactive, setIncludeInactive] = useState(false)
  const [editing, setEditing] = useState<StapleIngredient | null>(null)
  const [form, setForm] = useState<StapleIngredientInput>(EMPTY_FORM)
  const [aliasText, setAliasText] = useState('')
  const [tagName, setTagName] = useState('')
  const [tagCategory, setTagCategory] = useState('CUSTOM')

  const ingredients = useQuery({
    queryKey: ['ingredients', search, includeInactive],
    queryFn: () => fetchIngredients(search, includeInactive) as Promise<StapleIngredient[]>,
  })
  const categories = useQuery({ queryKey: ['shopping-categories'], queryFn: fetchShoppingCategories })
  const locations = useQuery({ queryKey: ['inventory-locations'], queryFn: fetchInventoryLocations })
  const units = useQuery({ queryKey: ['measurement-units'], queryFn: fetchMeasurementUnits })
  const tags = useQuery({ queryKey: ['tags'], queryFn: () => fetchTags(false) })

  const saveIngredient = useMutation({
    mutationFn: async () => {
      const payload: StapleIngredientInput = {
        ...form,
        aliases: aliasText.split(',').map((value) => value.trim()).filter(Boolean),
      }
      return editing ? updateIngredient(editing, payload) : createIngredient(payload)
    },
    onSuccess: async () => {
      clearForm()
      await queryClient.invalidateQueries({ queryKey: ['ingredients'] })
      await queryClient.invalidateQueries({ queryKey: ['inventory-availability'] })
    },
  })

  const removeIngredient = useMutation({
    mutationFn: archiveIngredient,
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ['ingredients'] }),
  })
  const addTag = useMutation({ mutationFn: createTag, onSuccess: async () => { setTagName(''); setTagCategory('CUSTOM'); await queryClient.invalidateQueries({ queryKey: ['tags'] }) } })
  const editTag = useMutation({ mutationFn: updateTag, onSuccess: async () => queryClient.invalidateQueries({ queryKey: ['tags'] }) })
  const removeTag = useMutation({ mutationFn: archiveTag, onSuccess: async () => queryClient.invalidateQueries({ queryKey: ['tags'] }) })

  const categoryNames = useMemo(() => new Map(categories.data?.map((item) => [item.id, item.name]) ?? []), [categories.data])
  const locationNames = useMemo(() => new Map(locations.data?.map((item) => [item.id, item.name]) ?? []), [locations.data])
  const unitCodes = useMemo(() => new Map(units.data?.map((item) => [item.id, item.code]) ?? []), [units.data])
  const preferredFamily = form.preferred_unit_id ? units.data?.find((item) => item.id === form.preferred_unit_id)?.unit_family : null
  const stapleUnits = units.data?.filter((item) => !preferredFamily || item.unit_family === preferredFamily) ?? []

  function clearForm() { setEditing(null); setForm(EMPTY_FORM); setAliasText('') }
  function beginEdit(ingredient: StapleIngredient) {
    setEditing(ingredient)
    setForm({
      name: ingredient.name,
      shopping_category_id: ingredient.shopping_category_id,
      preferred_unit_id: ingredient.preferred_unit_id,
      default_location_id: ingredient.default_location_id,
      perishable: ingredient.perishable,
      staple_enabled: ingredient.staple_enabled,
      staple_minimum: ingredient.staple_minimum,
      staple_target: ingredient.staple_target,
      staple_unit_id: ingredient.staple_unit_id,
      notes: ingredient.notes,
      aliases: ingredient.aliases.map((item) => item.alias),
      active: ingredient.active,
    })
    setAliasText(ingredient.aliases.map((item) => item.alias).join(', '))
  }
  function submitIngredient(event: FormEvent) { event.preventDefault(); saveIngredient.mutate() }
  function submitTag(event: FormEvent) { event.preventDefault(); addTag.mutate({ name: tagName, category: tagCategory }) }
  const error = saveIngredient.error ?? removeIngredient.error ?? addTag.error ?? editTag.error ?? removeTag.error

  return (
    <section className="settings-page">
      <div className="page-card"><p className="eyebrow">Ingredient Library</p><h1>Ingredients</h1><p>Maintain canonical ingredients, aliases, stock rules, and reusable recipe tags.</p></div>
      {error instanceof Error && <div className="error-banner">{error.message}</div>}
      <div className="settings-grid">
        <section className="settings-card settings-card-wide">
          <div className="section-heading"><h2>Ingredient Library</h2><div className="search-controls"><input placeholder="Search names or aliases" value={search} onChange={(event) => setSearch(event.target.value)} /><label className="check-label"><input type="checkbox" checked={includeInactive} onChange={(event) => setIncludeInactive(event.target.checked)} />Show archived</label></div></div>
          <div className="data-list">
            {ingredients.data?.map((ingredient) => (
              <div className={`ingredient-row ${ingredient.active ? '' : 'is-archived'}`} key={ingredient.id}>
                <div><strong>{ingredient.name}</strong><div className="muted-line">{ingredient.aliases.length ? `Also: ${ingredient.aliases.map((item) => item.alias).join(', ')}` : 'No aliases'}</div></div>
                <div className="ingredient-meta">
                  <span>{ingredient.shopping_category_id ? categoryNames.get(ingredient.shopping_category_id) : 'No category'}</span>
                  <span>{ingredient.preferred_unit_id ? unitCodes.get(ingredient.preferred_unit_id) : 'No unit'}</span>
                  <span>{ingredient.default_location_id ? locationNames.get(ingredient.default_location_id) : 'No default location'}</span>
                  {ingredient.perishable && <span>Perishable</span>}
                  {ingredient.staple_enabled && <span>Staple: min {ingredient.staple_minimum} / target {ingredient.staple_target} {ingredient.staple_unit_id ? unitCodes.get(ingredient.staple_unit_id) : ''}</span>}
                </div>
                <div className="row-actions"><button type="button" className="button-secondary" onClick={() => beginEdit(ingredient)}>Edit</button>{ingredient.active && <button type="button" className="button-danger" onClick={() => removeIngredient.mutate(ingredient.id)}>Archive</button>}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="settings-card settings-card-wide">
          <h2>{editing ? `Edit ${editing.name}` : 'Add Ingredient'}</h2>
          <form onSubmit={submitIngredient} className="ingredient-form">
            <label>Name<input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required /></label>
            <label>Aliases<input value={aliasText} onChange={(event) => setAliasText(event.target.value)} placeholder="scallion, spring onion" /><small>Separate aliases with commas.</small></label>
            <label>Shopping category<select value={form.shopping_category_id ?? ''} onChange={(event) => setForm({ ...form, shopping_category_id: event.target.value ? Number(event.target.value) : null })}><option value="">None</option>{categories.data?.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
            <label>Preferred unit<select value={form.preferred_unit_id ?? ''} onChange={(event) => { const preferred = event.target.value ? Number(event.target.value) : null; const family = preferred ? units.data?.find((item) => item.id === preferred)?.unit_family : null; const currentStaple = form.staple_unit_id ? units.data?.find((item) => item.id === form.staple_unit_id) : null; setForm({ ...form, preferred_unit_id: preferred, staple_unit_id: family && currentStaple && currentStaple.unit_family !== family ? null : form.staple_unit_id }) }}><option value="">None</option>{units.data?.map((item) => <option key={item.id} value={item.id}>{item.name} ({item.code})</option>)}</select></label>
            <label>Default location<select value={form.default_location_id ?? ''} onChange={(event) => setForm({ ...form, default_location_id: event.target.value ? Number(event.target.value) : null })}><option value="">None</option>{locations.data?.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
            <label className="check-label ingredient-check"><input type="checkbox" checked={form.perishable} onChange={(event) => setForm({ ...form, perishable: event.target.checked })} />Perishable</label>
            <label className="check-label ingredient-check"><input type="checkbox" checked={form.staple_enabled} onChange={(event) => setForm({ ...form, staple_enabled: event.target.checked })} />Keep as staple</label>
            <label>Staple minimum<input type="number" min="0" step="any" disabled={!form.staple_enabled} value={form.staple_minimum ?? ''} onChange={(event) => setForm({ ...form, staple_minimum: event.target.value || null })} required={form.staple_enabled} /></label>
            <label>Staple target<input type="number" min="0" step="any" disabled={!form.staple_enabled} value={form.staple_target ?? ''} onChange={(event) => setForm({ ...form, staple_target: event.target.value || null })} required={form.staple_enabled} /></label>
            <label>Staple unit<select disabled={!form.staple_enabled} value={form.staple_unit_id ?? ''} onChange={(event) => setForm({ ...form, staple_unit_id: event.target.value ? Number(event.target.value) : null })} required={form.staple_enabled}><option value="">Select unit</option>{stapleUnits.map((item) => <option key={item.id} value={item.id}>{item.name} ({item.code})</option>)}</select></label>
            <label className="form-wide">Notes<textarea value={form.notes ?? ''} onChange={(event) => setForm({ ...form, notes: event.target.value || null })} rows={3} /></label>
            <div className="form-actions form-wide"><button type="submit" disabled={saveIngredient.isPending}>{editing ? 'Save ingredient' : 'Add ingredient'}</button>{editing && <button type="button" className="button-secondary" onClick={clearForm}>Cancel</button>}</div>
          </form>
        </section>

        <section className="settings-card settings-card-wide">
          <h2>Reusable Tags</h2>
          <form onSubmit={submitTag} className="location-form"><input placeholder="Tag name" value={tagName} onChange={(event) => setTagName(event.target.value)} required /><select value={tagCategory} onChange={(event) => setTagCategory(event.target.value)}>{TAG_CATEGORIES.map((category) => <option key={category}>{category}</option>)}</select><button type="submit" disabled={addTag.isPending}>Add tag</button></form>
          <div className="tag-list">{tags.data?.map((tag) => <TagRow key={tag.id} tag={tag} onSave={(next) => editTag.mutate(next)} onArchive={(id) => removeTag.mutate(id)} />)}</div>
        </section>
      </div>
    </section>
  )
}

function TagRow({ tag, onSave, onArchive }: { tag: Tag; onSave: (tag: Tag) => void; onArchive: (id: number) => void }) {
  const [name, setName] = useState(tag.name)
  const [category, setCategory] = useState(tag.category)
  return <div className="category-row"><input value={name} onChange={(event) => setName(event.target.value)} /><select value={category} onChange={(event) => setCategory(event.target.value)}>{TAG_CATEGORIES.map((value) => <option key={value}>{value}</option>)}</select><div className="row-actions"><button type="button" className="button-secondary" onClick={() => onSave({ ...tag, name, category })}>Save</button><button type="button" className="button-danger" onClick={() => onArchive(tag.id)}>Archive</button></div></div>
}
