import { useQueryClient } from '@tanstack/react-query'
import {
  getListPackagesQueryKey,
  useCreatePackage,
  useDeletePackage,
  useListPackages,
  useUpdatePackage,
} from '../../api/generated/chat'
import type { PackageInput } from '../../api/generated/chat'
import type { RecordField } from '../RecordForm/RecordForm'
import { RecordSection } from '../RecordSection/RecordSection'

const FIELDS: RecordField<keyof PackageInput>[] = [
  { name: 'description', label: 'Description' },
  { name: 'weight_kg', label: 'Weight (kg)', type: 'number' },
  { name: 'declared_value', label: 'Declared value', type: 'number' },
]

const EMPTY_PACKAGE: Record<keyof PackageInput, string> = {
  description: '',
  weight_kg: '',
  declared_value: '',
}

interface PackageSectionProps {
  shipmentId: string
}

export function PackageSection({ shipmentId }: PackageSectionProps) {
  const queryClient = useQueryClient()
  const packages = useListPackages(shipmentId)
  const mutation = {
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: getListPackagesQueryKey(shipmentId),
      }),
  }
  const createPackage = useCreatePackage({ mutation })
  const updatePackage = useUpdatePackage({ mutation })
  const deletePackage = useDeletePackage({ mutation })

  return (
    <RecordSection
      title="Packages"
      fields={FIELDS}
      emptyValues={EMPTY_PACKAGE}
      records={packages.data?.data}
      hasFailed={packages.isError || deletePackage.isError}
      deleteWarning="Delete this package?"
      onSave={(data, packageId) =>
        packageId
          ? updatePackage.mutateAsync({ packageId, data })
          : createPackage.mutateAsync({ shipmentId, data })
      }
      onDelete={(packageId) => deletePackage.mutate({ packageId })}
    />
  )
}
