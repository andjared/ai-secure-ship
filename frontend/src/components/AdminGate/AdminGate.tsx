import type { ReactNode } from 'react'
import { useAuth0 } from '@auth0/auth0-react'
import './AdminGate.css'

interface AdminGateProps {
  children: ReactNode
}

// Hides the admin area until Auth0 reports a signed-in admin. This is only
// the frontend half: admin API routes must validate the token themselves.
export function AdminGate({ children }: AdminGateProps) {
  const { isLoading, isAuthenticated, error, loginWithRedirect } = useAuth0()

  if (isLoading) {
    return <p className="admin-gate__status">Loading…</p>
  }

  if (isAuthenticated) {
    return <>{children}</>
  }

  return (
    <div className="admin-gate">
      <h1 className="admin-gate__title">SecureShip admin</h1>
      {error && (
        <p className="admin-gate__error" role="alert">
          Login failed — please try again.
        </p>
      )}
      <button
        className="admin-gate__login"
        type="button"
        onClick={() => loginWithRedirect()}
      >
        Log in
      </button>
    </div>
  )
}
