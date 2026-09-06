export function canSubmitDiscard(quantity: string, reason: string, lotQuantity: string): boolean {
  const requested = Number(quantity)
  const available = Number(lotQuantity)
  return Number.isFinite(requested)
    && Number.isFinite(available)
    && requested > 0
    && requested <= available
    && reason.trim().length > 0
}
