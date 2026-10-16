import { useQueryClient } from '@tanstack/react-query'
import {
  getListPackagesQueryKey,
  useCreatePackage,
  useDeletePackage,
  useListPackages,
  useListShipments,
  useUpdatePackage,
} from '../../api/generated/chat'
import type { PackageInput } from '../../api/generated/chat'
import type { RecordField } from '../RecordForm/RecordForm'
import { RecordSection } from '../RecordSection/RecordSection'

const FIELDS: RecordField<keyof PackageInput>[] = [
  { name: 'description', label: 'Description', minLength: 2 },
  // The maximums match the backend's Numeric(6, 2) and Numeric(10, 2) columns.
  { name: 'weight_kg', label: 'Weight (kg)', type: 'number', max: 9999.99 },
  {
    name: 'declared_value',
    label: 'Declared value',
    type: 'number',
    max: 99999999.99,
  },
]

// The shipment is picked only when adding a package; it never changes after.
type PackageFieldName = keyof PackageInput | 'shipment_id'

const EMPTY_PACKAGE: Record<PackageFieldName, string> = {
  shipment_id: '',
  description: '',
  weight_kg: '',
  declared_value: '',
}

// Every shipment's packages.
export function PackageSection() {
  const queryClient = useQueryClient()
  const packages = useListPackages()
  const shipments = useListShipments()
  const mutation = {
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: getListPackagesQueryKey() }),
  }
  const createPackage = useCreatePackage({ mutation })
  const updatePackage = useUpdatePackage({ mutation })
  const deletePackage = useDeletePackage({ mutation })

  const shipmentField: RecordField<PackageFieldName> = {
    name: 'shipment_id',
    label: 'Shipment',
    options: (shipments.data?.data ?? []).map((shipment) => ({
      value: shipment.id,
      label: shipment.tracking_number,
    })),
  }

  function savePackage(
    { shipment_id: shipmentId, ...data }: Record<PackageFieldName, string>,
    packageId: string | null,
  ) {
    return packageId
      ? updatePackage.mutateAsync({ packageId, data })
      : createPackage.mutateAsync({ shipmentId, data })
  }

  function getTrackingNumber(packageId: string) {
    const found = packages.data?.data.find(({ id }) => id === packageId)
    const shipment = shipments.data?.data.find(
      ({ id }) => id === found?.shipment_id,
    )
    return shipment?.tracking_number ?? ''
  }

  return (
    <RecordSection
      extraColumn={{ label: 'Shipment', getValue: getTrackingNumber }}
      fields={FIELDS}
      newRecordFields={[shipmentField]}
      emptyValues={EMPTY_PACKAGE}
      filters={[
        {
          placeholder: 'Filter by tracking number',
          getText: (record) => getTrackingNumber(record.id),
        },
        {
          placeholder: 'Filter by description',
          getText: (record) => record.description,
        },
      ]}
      records={packages.data?.data}
      hasFailed={packages.isError || shipments.isError || deletePackage.isError}
      deleteWarning="Delete this package?"
      onSave={savePackage}
      onDelete={(packageId) => deletePackage.mutate({ packageId })}
    />
  )
}
