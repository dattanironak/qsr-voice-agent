import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import AdminApp from './admin/AdminApp.tsx'
import { PaymentResultPage } from './components/PaymentResultPage.tsx'

const path = window.location.pathname
const isAdmin = path.startsWith('/admin')
// PayU's redirect (via the backend) lands here as /order/<id> — see PaymentResultPage.
const orderMatch = path.match(/^\/order\/([^/]+)/)

function Root() {
  if (orderMatch) return <PaymentResultPage orderId={orderMatch[1]} />
  if (isAdmin) return <AdminApp />
  return <App />
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
)
