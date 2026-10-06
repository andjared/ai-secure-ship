import { AdminApp } from './components/AdminApp/AdminApp'
import { ADMIN_PATH } from './components/AdminApp/adminUrl'
import { ChatWindow } from './components/ChatWindow/ChatWindow'
import './App.css'

const isAdminPath = window.location.pathname === ADMIN_PATH

function App() {
  return (
    <main className="app">{isAdminPath ? <AdminApp /> : <ChatWindow />}</main>
  )
}

export default App
