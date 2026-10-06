import { useLayoutEffect } from 'react'
import { useAuth0 } from '@auth0/auth0-react'
import axios from 'axios'

const ADMIN_API_PREFIX = '/admin/'

// Adds the admin's Auth0 access token to admin API requests only. Chat
// requests pass through untouched, so the token never reaches the chat routes.
export function useAdminAccessToken() {
  const { getAccessTokenSilently } = useAuth0()

  // A layout effect, so the interceptor is in place before the admin
  // sections send their first request.
  useLayoutEffect(() => {
    const interceptor = axios.interceptors.request.use(async (config) => {
      if (config.url?.startsWith(ADMIN_API_PREFIX)) {
        const token = await getAccessTokenSilently()
        config.headers.Authorization = `Bearer ${token}`
      }
      return config
    })
    return () => axios.interceptors.request.eject(interceptor)
  }, [getAccessTokenSilently])
}
