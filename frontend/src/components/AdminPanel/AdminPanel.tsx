import { useState } from 'react'
import { useAdminAccessToken } from '../AdminApp/useAdminAccessToken'
import { CustomerSection } from '../CustomerSection/CustomerSection'
import { PackageSection } from '../PackageSection/PackageSection'
import { ShipmentSection } from '../ShipmentSection/ShipmentSection'
import './AdminPanel.css'

const TABS = [
  { id: 'customers', label: 'Customers' },
  { id: 'shipments', label: 'Shipments' },
  { id: 'packages', label: 'Packages' },
] as const

type TabId = (typeof TABS)[number]['id']

// One tab per kind of record, each listing every record of that kind.
export function AdminPanel() {
  useAdminAccessToken()
  const [tab, setTab] = useState<TabId>('customers')

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
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === 'customers' && <CustomerSection />}
      {tab === 'shipments' && <ShipmentSection />}
      {tab === 'packages' && <PackageSection />}
    </div>
  )
}
