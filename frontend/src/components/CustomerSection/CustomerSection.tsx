import { useQueryClient } from '@tanstack/react-query'
import {
  getListCustomersQueryKey,
  useCreateCustomer,
  useDeleteCustomer,
  useListCustomers,
  useUpdateCustomer,
} from '../../api/generated/chat'
import type { CustomerInput } from '../../api/generated/chat'
import type { RecordField } from '../RecordForm/RecordForm'
import { RecordSection } from '../RecordSection/RecordSection'

const FIELDS: RecordField<keyof CustomerInput>[] = [
  { name: 'first_name', label: 'First name', minLength: 2 },
  { name: 'last_name', label: 'Last name', minLength: 2 },
  {
    name: 'phone_number',
    label: 'Phone number',
    minLength: 6,
    countsDigitsOnly: true,
  },
  { name: 'address', label: 'Address', minLength: 5 },
]

const EMPTY_CUSTOMER: CustomerInput = {
  first_name: '',
  last_name: '',
  phone_number: '',
  address: '',
}

export function CustomerSection() {
  const queryClient = useQueryClient()
  const customers = useListCustomers()
  const mutation = {
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: getListCustomersQueryKey() }),
  }
  const createCustomer = useCreateCustomer({ mutation })
  const updateCustomer = useUpdateCustomer({ mutation })
  const deleteCustomer = useDeleteCustomer({ mutation })

  return (
    <RecordSection
      fields={FIELDS}
      emptyValues={EMPTY_CUSTOMER}
      filters={[
        {
          placeholder: 'Filter by name',
          getText: (customer) => `${customer.first_name} ${customer.last_name}`,
        },
      ]}
      records={customers.data?.data}
      hasFailed={customers.isError || deleteCustomer.isError}
      deleteWarning="Delete this customer with all their shipments and packages?"
      onSave={(data, customerId) =>
        customerId
          ? updateCustomer.mutateAsync({ customerId, data })
          : createCustomer.mutateAsync({ data })
      }
      onDelete={(customerId) => deleteCustomer.mutate({ customerId })}
    />
  )
}
