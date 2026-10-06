export const ADMIN_PATH = '/admin'

// Auth0 sends the admin back here after login and logout, so this exact URL
// must be in the application's Allowed Callback URLs and Allowed Logout URLs.
export const ADMIN_URL = `${window.location.origin}${ADMIN_PATH}`
