import { Auth0Provider } from '@auth0/auth0-react'
import { AdminGate } from '../AdminGate/AdminGate'
import { AdminHeader } from '../AdminHeader/AdminHeader'
import { ADMIN_URL } from './adminUrl'
import './AdminApp.css'

// Auth0 wraps only the admin area. The chat is rendered outside this
// provider, so the admin login and the chat's identity gate never meet.
export function AdminApp() {
  return (
    <Auth0Provider
      domain={import.meta.env.VITE_AUTH0_DOMAIN}
      clientId={import.meta.env.VITE_AUTH0_CLIENT_ID}
      authorizationParams={{
        redirect_uri: ADMIN_URL,
        audience: import.meta.env.VITE_AUTH0_AUDIENCE,
      }}
    >
      <section className="admin-app">
        <AdminGate>
          <AdminHeader />
          <p className="admin-app__placeholder">The admin panel is coming next.</p>
        </AdminGate>
      </section>
    </Auth0Provider>
  )
}
