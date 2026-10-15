import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import { Layout } from './components/Layout'
import { Skeleton } from './components/ui'
import { useAuth } from './state/auth'
import type { User } from './api/types'
import { Dashboard } from './pages/Dashboard'
import { OfferPage } from './pages/OfferPage'
import { Login, Register } from './pages/Auth'
import { AgeVerify } from './pages/AgeVerify'
import { OrdersPage, OrderPage } from './pages/Orders'
import { PointsPage, ProfilePage } from './pages/Me'
import { ProducerPublish, ProducerOrders, ProducerOffers, ProducerPayouts } from './pages/Producer'
import { AdminMetrics, AdminGuardrails, AdminStalls, AdminDonations, AdminQuality } from './pages/Admin'
import { DemoPage } from './pages/Demo'
import { LockersPage } from './pages/Lockers'
import { ProducerHome } from './pages/ProducerHome'

function Guard({ roles, children }: { roles?: User['role'][]; children: ReactNode }) {
  const { user, ready } = useAuth()
  const loc = useLocation()
  if (!ready) return <div className="pt-4"><Skeleton count={3} /></div>
  if (!user) return <Navigate to="/entrar" state={{ from: loc.pathname }} replace />
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />
  return <>{children}</>
}

/** Ruta "/": cada rol aterriza en su zona (§6.1). Visitantes y vecinos ven el dashboard. */
function HomeRoute() {
  const { user, ready } = useAuth()
  if (!ready) return <div className="pt-4"><Skeleton count={3} /></div>
  if (user?.role === 'PRODUCER') return <Navigate to="/productor" replace />
  if (user?.role === 'MANAGER' || user?.role === 'ADMIN') return <Navigate to="/admin" replace />
  return <Dashboard />
}

export default function App() {
  const P = ['PRODUCER', 'ADMIN'] as User['role'][]
  const M = ['MANAGER', 'ADMIN'] as User['role'][]
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<HomeRoute />} />
        <Route path="oferta/:id" element={<OfferPage />} />
        <Route path="entrar" element={<Login />} />
        <Route path="registro" element={<Register />} />
        <Route path="verificar-edad" element={<Guard><AgeVerify /></Guard>} />
        <Route path="pedidos" element={<Guard><OrdersPage /></Guard>} />
        <Route path="pedidos/:id" element={<Guard><OrderPage /></Guard>} />
        <Route path="puntos" element={<Guard><PointsPage /></Guard>} />
        <Route path="perfil" element={<Guard><ProfilePage /></Guard>} />
        <Route path="productor" element={<Guard roles={P}><ProducerHome /></Guard>} />
        <Route path="productor/publicar" element={<Guard roles={P}><ProducerPublish /></Guard>} />
        <Route path="productor/pedidos" element={<Guard roles={P}><ProducerOrders /></Guard>} />
        <Route path="productor/ofertas" element={<Guard roles={P}><ProducerOffers /></Guard>} />
        <Route path="productor/liquidaciones" element={<Guard roles={P}><ProducerPayouts /></Guard>} />
        <Route path="admin" element={<Guard roles={M}><AdminMetrics /></Guard>} />
        <Route path="admin/barandillas" element={<Guard roles={M}><AdminGuardrails /></Guard>} />
        <Route path="admin/puestos" element={<Guard roles={M}><AdminStalls /></Guard>} />
        <Route path="admin/donaciones" element={<Guard roles={M}><AdminDonations /></Guard>} />
        <Route path="admin/calidad" element={<Guard roles={M}><AdminQuality /></Guard>} />
        <Route path="demo" element={<DemoPage />} />
        <Route path="sim/taquillas" element={<LockersPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
