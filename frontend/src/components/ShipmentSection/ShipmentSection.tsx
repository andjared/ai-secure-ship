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
  { name: 'tracking_number', label: 'Tracking number', minLength: 5 },
  {
    name: 'status',
    label: 'Status',
    options: Object.entries(STATUS_LABELS).map(([value, label]) => ({
      value,
      label,
    })),
  },
  { name: 'carrier', label: 'Carrier', minLength: 2 },
  { name: 'origin', label: 'Origin', minLength: 2 },
  { name: 'destination', label: 'Destination', minLength: 2 },
  { name: 'estimated_delivery', label: 'Estimated delivery', type: 'date' },
]

// The customer is picked only when adding a shipment; it never changes after.
type ShipmentFieldName = keyof ShipmentInput | 'customer_id'

const EMPTY_SHIPMENT: Record<ShipmentFieldName, string> = {
  customer_id: '',
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

// Every customer's shipments.
export function ShipmentSection() {
  const queryClient = useQueryClient()
  const shipments = useListShipments()
  const customers = useListCustomers()
  const mutation = {
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: getListShipmentsQueryKey() }),
  }
  const createShipment = useCreateShipment({ mutation })
  const updateShipment = useUpdateShipment({ mutation })
  const deleteShipment = useDeleteShipment({ mutation })

  const customerField: RecordField<ShipmentFieldName> = {
    name: 'customer_id',
    label: 'Customer',
    options: (customers.data?.data ?? []).map((customer) => ({
      value: customer.id,
      label: `${customer.first_name} ${customer.last_name}`,
    })),
  }

  function saveShipment(
    { customer_id: customerId, ...values }: Record<ShipmentFieldName, string>,
    shipmentId: string | null,
  ) {
    if (!isShipmentStatus(values.status)) {
      return Promise.reject(new Error('Unknown shipment status'))
    }
    const data = { ...values, status: values.status }
    if (shipmentId) {
      return updateShipment.mutateAsync({ shipmentId, data })
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
      extraColumn={{ label: 'Customer', getValue: getCustomerName }}
      fields={FIELDS}
      newRecordFields={[customerField]}
      emptyValues={EMPTY_SHIPMENT}
      filters={[
        {
          placeholder: 'Filter by tracking number',
          getText: (shipment) => shipment.tracking_number,
        },
        {
          placeholder: 'Filter by customer name',
          getText: (shipment) => getCustomerName(shipment.id),
        },
      ]}
      records={shipments.data?.data}
      hasFailed={shipments.isError || customers.isError || deleteShipment.isError}
      deleteWarning="Delete this shipment with all its packages?"
      onSave={saveShipment}
      onDelete={(shipmentId) => deleteShipment.mutate({ shipmentId })}
    />
  )
}
