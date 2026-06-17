import { Sidebar } from '@/components/shell/Sidebar'
import { Topbar } from '@/components/shell/Topbar'
import { ShellProvider } from '../context/shell'

export default function ShellLayout({ children }: { children: React.ReactNode }) {
  return (
    <ShellProvider>
      <div className="flex h-screen overflow-hidden bg-bgApp">
        <Sidebar />
        <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
          <Topbar />
          <main className="flex-1 overflow-y-auto p-7">
            <div className="max-w-content mx-auto">
              {children}
            </div>
          </main>
        </div>
      </div>
    </ShellProvider>
  )
}
