import { BrowserRouter as Router, Routes, Route, Link, useLocation, Navigate } from 'react-router-dom';
import { LayoutDashboard, Settings, FileText, Activity, List, Calendar } from 'lucide-react';
import Dashboard from './pages/Dashboard';
import Configuration from './pages/Configuration';
import BouquetSelection from './pages/BouquetSelection';
import Logs from './pages/Logs';
import Scheduler from './pages/Scheduler';

function Layout({ children }: { children: React.ReactNode }) {
    const location = useLocation();

    return (
        <div className="min-h-screen bg-background text-foreground flex">
            {/* Sidebar */}
            <aside className="w-64 border-r border-border bg-card p-4 flex flex-col">
                <div className="mb-8">
                    <h1 className="text-2xl font-bold text-primary">Xtream2STRM</h1>
                </div>

                <nav className="space-y-2 flex-1">
                    <Link to="/" className={`flex items-center gap-3 px-3 py-2 rounded-md transition-colors ${location.pathname === '/' ? 'bg-accent text-accent-foreground' : 'hover:bg-accent hover:text-accent-foreground'}`}>
                        <LayoutDashboard size={20} />
                        <span>Dashboard</span>
                    </Link>
                    <Link to="/bouquets" className={`flex items-center gap-3 px-3 py-2 rounded-md transition-colors ${location.pathname === '/bouquets' ? 'bg-accent text-accent-foreground' : 'hover:bg-accent hover:text-accent-foreground'}`}>
                        <List size={20} />
                        <span>Bouquet Selection</span>
                    </Link>
                    <Link to="/scheduler" className={`flex items-center gap-3 px-3 py-2 rounded-md transition-colors ${location.pathname === '/scheduler' ? 'bg-accent text-accent-foreground' : 'hover:bg-accent hover:text-accent-foreground'}`}>
                        <Calendar size={20} />
                        <span>Scheduler</span>
                    </Link>
                    <Link to="/config" className={`flex items-center gap-3 px-3 py-2 rounded-md transition-colors ${location.pathname === '/config' ? 'bg-accent text-accent-foreground' : 'hover:bg-accent hover:text-accent-foreground'}`}>
                        <Settings size={20} />
                        <span>Configuration</span>
                    </Link>
                    <Link to="/logs" className={`flex items-center gap-3 px-3 py-2 rounded-md transition-colors ${location.pathname === '/logs' ? 'bg-accent text-accent-foreground' : 'hover:bg-accent hover:text-accent-foreground'}`}>
                        <FileText size={20} />
                        <span>Logs</span>
                    </Link>
                </nav>

                <div className="mt-auto pt-4 border-t border-border">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground px-3">
                        <Activity size={16} />
                        <span>v1.0.0</span>
                    </div>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 p-8 overflow-auto">
                {children}
            </main>
        </div>
    );
}

function App() {
    return (
        <Router>
            <Routes>
                <Route path="/" element={<Layout><Dashboard /></Layout>} />
                <Route path="/config" element={<Layout><Configuration /></Layout>} />
                <Route path="/bouquets" element={<Layout><BouquetSelection /></Layout>} />
                <Route path="/logs" element={<Layout><Logs /></Layout>} />
                <Route path="/scheduler" element={<Layout><Scheduler /></Layout>} />
                <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
        </Router>
    );
}

export default App;
