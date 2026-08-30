import { Equipment, RecipeEquipmentInput } from './api'
import './equipment.css'
import './substitutions.css'

export default function RecipeEquipmentEditor({ items, equipment, onChange }: { items: RecipeEquipmentInput[]; equipment: Equipment[]; onChange: (items: RecipeEquipmentInput[]) => void }) {
  function normalize(next: RecipeEquipmentInput[]) { return next.map((item, index) => ({ ...item, sort_order: index })) }
  function patch(index: number, update: Partial<RecipeEquipmentInput>) { onChange(items.map((item, currentIndex) => currentIndex === index ? { ...item, ...update } : item)) }
  const usedIds = new Set(items.map((item) => item.equipment_id))
  const available = equipment.filter((item) => !usedIds.has(item.id))

  return <section className="editor-card">
    <div className="section-heading-row"><div><h2>Equipment</h2><p>Tools and appliances required by this Recipe. Quantities do not scale with servings.</p></div><button type="button" disabled={!available.length} onClick={() => { const item = available[0]; if (item) onChange([...items, { equipment_id: item.id, quantity: 1, notes: null, sort_order: items.length }]) }}>Add equipment</button></div>
    {!equipment.length && <p>Add reusable Equipment under Settings first.</p>}
    <div className="recipe-ingredient-list">{items.map((item, index) => <div className="equipment-requirement-row" key={item.equipment_id}>
      <select value={item.equipment_id} onChange={(event) => patch(index, { equipment_id: Number(event.target.value) })}>{equipment.filter((candidate) => candidate.id === item.equipment_id || !usedIds.has(candidate.id)).map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.name}</option>)}</select>
      <input aria-label="Equipment quantity" type="number" min="1" value={item.quantity} onChange={(event) => patch(index, { quantity: Number(event.target.value) })} />
      <input placeholder="Notes" value={item.notes ?? ''} onChange={(event) => patch(index, { notes: event.target.value || null })} />
      <button type="button" className="button-secondary" disabled={index === 0} onClick={() => { const copy = [...items]; [copy[index - 1], copy[index]] = [copy[index], copy[index - 1]]; onChange(normalize(copy)) }}>Move up</button>
      <button type="button" className="button-secondary" disabled={index === items.length - 1} onClick={() => { const copy = [...items]; [copy[index], copy[index + 1]] = [copy[index + 1], copy[index]]; onChange(normalize(copy)) }}>Move down</button>
      <button type="button" className="button-secondary" onClick={() => onChange(normalize(items.filter((_current, currentIndex) => currentIndex !== index)))}>Remove</button>
    </div>)}</div>
  </section>
}
