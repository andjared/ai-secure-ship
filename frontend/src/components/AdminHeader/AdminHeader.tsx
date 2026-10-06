import { useAuth0 } from '@auth0/auth0-react'
import { ADMIN_URL } from '../AdminApp/adminUrl'
import './AdminHeader.css'

export function AdminHeader() {
  const { user, logout } = useAuth0()

  return (
    <header className="admin-header">
      <span className="admin-header__title">SecureShip admin</span>
      <span className="admin-header__user">{user?.name ?? user?.email}</span>
      <button
        className="admin-header__logout"
        type="button"
        onClick={() => logout({ logoutParams: { returnTo: ADMIN_URL } })}
      >
        Log out
      </button>
    </header>
  )
}
