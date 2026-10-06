import { useState } from 'react'
import { useAdminAccessToken } from '../AdminApp/useAdminAccessToken'
import { CustomerSection } from '../CustomerSection/CustomerSection'
import { PackageSection } from '../PackageSection/PackageSection'
import { ShipmentSection } from '../ShipmentSection/ShipmentSection'
import './AdminPanel.css'

const TABS = [
  { id: 'customers', label: 'Customers' },
  { id: 'shipments', label: 'Shipments' },
] as const

type TabId = (typeof TABS)[number]['id']

// Two views of the same records. Customers is a drill-down: open a customer
// to see their shipments under that row, then a shipment to see its packages.
// Shipments lists every customer's shipments.
export function AdminPanel() {
  useAdminAccessToken()
  const [tab, setTab] = useState<TabId>('customers')
  const [customerId, setCustomerId] = useState<string | null>(null)
  const [shipmentId, setShipmentId] = useState<string | null>(null)

  function selectCustomer(id: string | null) {
    setCustomerId(id)
    setShipmentId(null)
  }

  function selectTab(id: TabId) {
    setTab(id)
    selectCustomer(null)
  }

  const packages = shipmentId && (
    <PackageSection key={shipmentId} shipmentId={shipmentId} />
  )

  return (
    <div className="admin-panel">
      <div className="admin-panel__tabs" role="tablist">
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            className="admin-panel__tab"
            type="button"
            role="tab"
            aria-selected={tab === id}
            onClick={() => selectTab(id)}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === 'customers' ? (
        <CustomerSection selectedId={customerId} onSelect={selectCustomer}>
          {customerId && (
            <ShipmentSection
              key={customerId}
              customerId={customerId}
              selectedId={shipmentId}
              onSelect={setShipmentId}
            >
              {packages}
            </ShipmentSection>
          )}
        </CustomerSection>
      ) : (
        <ShipmentSection selectedId={shipmentId} onSelect={setShipmentId}>
          {packages}
        </ShipmentSection>
      )}
    </div>
  )
}
