import { FormEvent, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { archiveEquipment, createEquipment, Equipment, fetchEquipment, updateEquipment } from './api'
import './equipment.css'

const CATEGORIES = ['COOKWARE', 'BAKEWARE', 'APPLIANCE', 'UTENSIL', 'CONTAINER', 'OTHER']

function EquipmentRow({ item }: { item: Equipment }) {
  const queryClient = useQueryClient()
  const [name, setName] = useState(item.name)
  const [category, setCategory] = useState(item.category)
  const [notes, setNotes] = useState(item.notes ?? '')
  const update = useMutation({ mutationFn: updateEquipment, onSuccess: async () => queryClient.invalidateQueries({ queryKey: ['equipment'] }) })
  const archive = useMutation({ mutationFn: archiveEquipment, onSuccess: async () => queryClient.invalidateQueries({ queryKey: ['equipment'] }) })
  const error = update.error ?? archive.error

  return <div className="equipment-settings-row">
    <input value={name} onChange={(event) => setName(event.target.value)} />
    <select value={category} onChange={(event) => setCategory(event.target.value)}>{CATEGORIES.map((value) => <option key={value}>{value}</option>)}</select>
    <input placeholder="Notes" value={notes} onChange={(event) => setNotes(event.target.value)} />
    <button type="button" onClick={() => update.mutate({ ...item, name, category, notes: notes || null })}>Save</button>
    <button type="button" className="button-secondary" onClick={() => archive.mutate(item.id)}>Archive</button>
    {error instanceof Error && <small className="field-error">{error.message}</small>}
  </div>
}

export default function EquipmentSettingsCard() {
  const queryClient = useQueryClient()
  const equipment = useQuery({ queryKey: ['equipment'], queryFn: () => fetchEquipment(false) })
  const [name, setName] = useState('')
  const [category, setCategory] = useState('OTHER')
  const [notes, setNotes] = useState('')
  const add = useMutation({ mutationFn: createEquipment, onSuccess: async () => { setName(''); setNotes(''); await queryClient.invalidateQueries({ queryKey: ['equipment'] }) } })
  function submit(event: FormEvent) { event.preventDefault(); add.mutate({ name, category, notes: notes || null }) }

  return <section className="settings-card settings-card-wide">
    <h2>Equipment</h2><p>Reusable tools and appliances that Recipes can require.</p>
    {add.error instanceof Error && <div className="error-banner">{add.error.message}</div>}
    <form className="equipment-settings-row" onSubmit={submit}><input placeholder="Equipment name" value={name} onChange={(event) => setName(event.target.value)} required /><select value={category} onChange={(event) => setCategory(event.target.value)}>{CATEGORIES.map((value) => <option key={value}>{value}</option>)}</select><input placeholder="Notes" value={notes} onChange={(event) => setNotes(event.target.value)} /><button type="submit" disabled={add.isPending}>Add equipment</button></form>
    <div className="editable-list">{equipment.data?.map((item) => <EquipmentRow key={item.id} item={item} />)}</div>
  </section>
}
