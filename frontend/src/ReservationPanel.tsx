import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchCycleReservations, regenerateCycleReservations } from './reservationsApi'

export default function ReservationPanel({ cycleId }: { cycleId: number }) {
  const queryClient = useQueryClient()
  const reservations = useQuery({ queryKey: ['reservations', cycleId], queryFn: () => fetchCycleReservations(cycleId) })
  const regenerate = useMutation({
    mutationFn: () => regenerateCycleReservations(cycleId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['reservations', cycleId] })
      await queryClient.invalidateQueries({ queryKey: ['inventory-availability'] })
    },
  })
  const error = reservations.error ?? regenerate.error
  return <section className="expiration-suggestions">
    <div className="section-heading">
      <div><h3>Ingredient reservations</h3><p className="planning-note">Reserve current planned ingredient requirements without changing physical Inventory.</p></div>
      <button type="button" className="button-secondary" disabled={regenerate.isPending} onClick={() => regenerate.mutate()}>{regenerate.isPending ? 'Refreshing…' : 'Refresh reservations'}</button>
    </div>
    {error instanceof Error && <div className="error-banner">{error.message}</div>}
    {reservations.data && <p className="planning-note"><strong>{reservations.data.active_count}</strong> active reservation{reservations.data.active_count === 1 ? '' : 's'}{reservations.data.released_count ? ` · ${reservations.data.released_count} released` : ''}.</p>}
  </section>
}
