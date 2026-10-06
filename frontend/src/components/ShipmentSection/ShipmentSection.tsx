import type { ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import {
  getListShipmentsQueryKey,
  useCreateShipment,
  useDeleteShipment,
  useListCustomers,
  useListShipments,
  useUpdateShipment,
} from '../../api/generated/chat'
import type { ShipmentInput, ShipmentStatus } from '../../api/generated/chat'
import type { RecordField } from '../RecordForm/RecordForm'
import { RecordSection } from '../RecordSection/RecordSection'
import { STATUS_LABELS } from '../ShipmentCard/statusLabels'

const FIELDS: RecordField<keyof ShipmentInput>[] = [
  { name: 'tracking_number', label: 'Tracking number' },
  {
    name: 'status',
    label: 'Status',
    options: Object.entries(STATUS_LABELS).map(([value, label]) => ({
      value,
      label,
    })),
  },
  { name: 'carrier', label: 'Carrier' },
  { name: 'origin', label: 'Origin' },
  { name: 'destination', label: 'Destination' },
  { name: 'estimated_delivery', label: 'Estimated delivery', type: 'date' },
]

const EMPTY_SHIPMENT: ShipmentInput = {
  tracking_number: '',
  status: 'label_created',
  carrier: '',
  origin: '',
  destination: '',
  estimated_delivery: '',
}

function isShipmentStatus(value: string): value is ShipmentStatus {
  return value in STATUS_LABELS
}

interface ShipmentSectionProps {
  // One customer's shipments; leave out to list every customer's shipments.
  customerId?: string
  selectedId: string | null
  onSelect: (id: string | null) => void
  // Shown under the selected shipment's row.
  children: ReactNode
}

export function ShipmentSection({
  customerId,
  selectedId,
  onSelect,
  children,
}: ShipmentSectionProps) {
  const queryClient = useQueryClient()
  const shipments = useListShipments(
    customerId ? { customer_id: customerId } : undefined,
  )
  // Only the all-customers list needs names, to say whose each shipment is.
  const customers = useListCustomers({ query: { enabled: !customerId } })
  const mutation = {
    // Every shipments list, so the per-customer and all-customers lists agree.
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: getListShipmentsQueryKey() }),
  }
  const createShipment = useCreateShipment({ mutation })
  const updateShipment = useUpdateShipment({ mutation })
  const deleteShipment = useDeleteShipment({ mutation })

  function saveShipment(values: Record<keyof ShipmentInput, string>, shipmentId: string | null) {
    if (!isShipmentStatus(values.status)) {
      return Promise.reject(new Error('Unknown shipment status'))
    }
    const data = { ...values, status: values.status }
    if (shipmentId) {
      return updateShipment.mutateAsync({ shipmentId, data })
    }
    if (!customerId) {
      return Promise.reject(new Error('A new shipment needs a customer'))
    }
    return createShipment.mutateAsync({ customerId, data })
  }

  function getCustomerName(shipmentId: string) {
    const shipment = shipments.data?.data.find(({ id }) => id === shipmentId)
    const customer = customers.data?.data.find(
      ({ id }) => id === shipment?.customer_id,
    )
    return customer ? `${customer.first_name} ${customer.last_name}` : ''
  }

  return (
    <RecordSection
      title={customerId ? 'Shipments' : undefined}
      canAdd={Boolean(customerId)}
      extraColumn={
        customerId ? undefined : { label: 'Customer', getValue: getCustomerName }
      }
      fields={FIELDS}
      emptyValues={EMPTY_SHIPMENT}
      filters={
        customerId
          ? undefined
          : [
              {
                placeholder: 'Filter by tracking number',
                getText: (shipment) => shipment.tracking_number,
              },
              {
                placeholder: 'Filter by customer name',
                getText: (shipment) => getCustomerName(shipment.id),
              },
            ]
      }
      records={shipments.data?.data}
      hasFailed={shipments.isError || customers.isError || deleteShipment.isError}
      deleteWarning="Delete this shipment with all its packages?"
      onSave={saveShipment}
      onDelete={(shipmentId) => deleteShipment.mutate({ shipmentId })}
      selectLabel="Packages"
      selectedId={selectedId}
      onSelect={onSelect}
    >
      {children}
    </RecordSection>
  )
}
