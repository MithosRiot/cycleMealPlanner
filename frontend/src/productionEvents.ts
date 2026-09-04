const productionInventoryEvents = new EventTarget()
const PRODUCTION_INVENTORY_CHANGED = 'production-inventory-changed'

export function emitProductionInventoryChanged(): void {
  productionInventoryEvents.dispatchEvent(new Event(PRODUCTION_INVENTORY_CHANGED))
}

export function onProductionInventoryChanged(listener: () => void): () => void {
  productionInventoryEvents.addEventListener(PRODUCTION_INVENTORY_CHANGED, listener)
  return () => productionInventoryEvents.removeEventListener(PRODUCTION_INVENTORY_CHANGED, listener)
}
