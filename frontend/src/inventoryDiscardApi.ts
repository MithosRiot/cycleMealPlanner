import type { InventoryLot } from './api'

type DiscardKind = 'WASTE' | 'SPOILAGE'

async function discardRequest(id: number, kind: DiscardKind, quantity: string, reason: string, note: string): Promise<InventoryLot> {
  const endpoint = kind === 'WASTE' ? 'waste' : 'spoilage'
  const response = await fetch(`/api/inventory/${id}/${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ quantity, reason: reason.trim(), note: note.trim() || null }),
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(body?.detail ?? `Request failed: ${response.status}`)
  }
  return response.json() as Promise<InventoryLot>
}

export const recordWaste = (id: number, quantity: string, reason: string, note: string): Promise<InventoryLot> =>
  discardRequest(id, 'WASTE', quantity, reason, note)

export const recordSpoilage = (id: number, quantity: string, reason: string, note: string): Promise<InventoryLot> =>
  discardRequest(id, 'SPOILAGE', quantity, reason, note)
