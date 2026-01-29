import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Film, Tv, Activity, HardDrive, Loader2 } from 'lucide-react';
import api from '@/lib/api';

interface DashboardStats {
    total_content: {
        total: number;
        movies: number;
        series: number;
    };
    sources: {
        total: number;
        active: number;
        inactive: number;
    };
    sync_status: {
        in_progress: number;
        errors_24h: number;
        success_rate: number;
    };
}

interface SyncProgress {
    subscription_id: number;
    type: string;
    status: string;
    progress_current: number;
    progress_total: number;
    progress_phase: string | null;
}

export default function Dashboard() {
    const [stats, setStats] = useState<DashboardStats | null>(null);
    const [activeSync, setActiveSync] = useState<SyncProgress[]>([]);

    const fetchData = async () => {
        try {
            const statsRes = await api.get<DashboardStats>('/dashboard/stats');
            setStats(statsRes.data);

            // Fetch active sync progress
            const syncRes = await api.get<SyncProgress[]>('/sync/status');
            const running = syncRes.data.filter(s => s.status === 'running');
            setActiveSync(running);
        } catch (error) {
            console.error("Failed to fetch dashboard data", error);
        }
    };

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 2000); // Poll every 2s for progress updates
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="space-y-8">
            <div>
                <h2 className="text-3xl font-bold tracking-tight">Dashboard</h2>
                <p className="text-muted-foreground">Overview of your Xtream to STRM synchronization.</p>
            </div>

            {/* Statistics Cards */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Total Content</CardTitle>
                        <Film className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{stats?.total_content?.total?.toLocaleString() || 0}</div>
                        <p className="text-xs text-muted-foreground">
                            {stats?.sources?.total || 0} Sources Configured
                        </p>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Movies</CardTitle>
                        <Film className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{stats?.total_content?.movies?.toLocaleString() || 0}</div>
                        <p className="text-xs text-muted-foreground">
                            {stats?.total_content?.total ? ((stats.total_content.movies / stats.total_content.total) * 100).toFixed(1) : 0}% of total
                        </p>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Series</CardTitle>
                        <Tv className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{stats?.total_content?.series?.toLocaleString() || 0}</div>
                        <p className="text-xs text-muted-foreground">
                            {stats?.total_content?.total ? ((stats.total_content.series / stats.total_content.total) * 100).toFixed(1) : 0}% of total
                        </p>
                    </CardContent>
                </Card>
            </div>

            {/* Sync Status & Content Distribution */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
                <Card className="col-span-4">
                    <CardHeader>
                        <CardTitle>Sync Status</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-6">
                            {/* Active Sync Progress */}
                            {activeSync.length > 0 ? (
                                activeSync.map((sync) => {
                                    const percent = sync.progress_total > 0
                                        ? Math.round((sync.progress_current / sync.progress_total) * 100)
                                        : 0;
                                    return (
                                        <div key={`${sync.subscription_id}-${sync.type}`} className="space-y-2">
                                            <div className="flex items-center justify-between">
                                                <div className="flex items-center gap-2">
                                                    <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                                                    <span className="text-sm font-medium capitalize">{sync.type} Sync</span>
                                                </div>
                                                <span className="text-sm font-medium text-blue-500">{percent}%</span>
                                            </div>
                                            <div className="h-2 w-full bg-secondary rounded-full overflow-hidden">
                                                <div
                                                    className="h-full bg-blue-500 transition-all duration-300"
                                                    style={{ width: `${percent}%` }}
                                                />
                                            </div>
                                            <div className="flex justify-between text-xs text-muted-foreground">
                                                <span>{sync.progress_phase || 'Processing...'}</span>
                                                <span>{sync.progress_current.toLocaleString()} / {sync.progress_total.toLocaleString()}</span>
                                            </div>
                                        </div>
                                    );
                                })
                            ) : (
                                <div className="flex items-center">
                                    <Activity className="mr-2 h-4 w-4 opacity-70" />
                                    <div className="ml-4 space-y-1">
                                        <p className="text-sm font-medium leading-none">Status</p>
                                        <p className="text-sm text-muted-foreground">No active sync tasks</p>
                                    </div>
                                    <div className="ml-auto font-medium text-green-500">Idle</div>
                                </div>
                            )}

                            <div className="flex items-center pt-2 border-t">
                                <Activity className="mr-2 h-4 w-4 opacity-70" />
                                <div className="ml-4 space-y-1">
                                    <p className="text-sm font-medium leading-none">Success Rate</p>
                                    <p className="text-sm text-muted-foreground">Last 24 hours</p>
                                </div>
                                <div className="ml-auto font-medium text-green-500">
                                    {stats?.sync_status?.success_rate || 100}%
                                </div>
                            </div>
                            <div className="flex items-center">
                                <Activity className="mr-2 h-4 w-4 opacity-70" />
                                <div className="ml-4 space-y-1">
                                    <p className="text-sm font-medium leading-none">Errors</p>
                                    <p className="text-sm text-muted-foreground">Last 24 hours</p>
                                </div>
                                <div className="ml-auto font-medium text-red-500">
                                    {stats?.sync_status?.errors_24h || 0}
                                </div>
                            </div>
                        </div>
                    </CardContent>
                </Card>
                <Card className="col-span-3">
                    <CardHeader>
                        <CardTitle>Content Distribution</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-8">
                            <div className="flex items-center">
                                <HardDrive className="mr-2 h-4 w-4 opacity-70" />
                                <div className="ml-4 space-y-1">
                                    <p className="text-sm font-medium leading-none">Sources</p>
                                    <p className="text-sm text-muted-foreground">
                                        {stats?.sources?.active || 0} Active / {stats?.sources?.total || 0} Total
                                    </p>
                                </div>
                            </div>
                            <div className="space-y-2">
                                <div className="flex items-center justify-between text-sm">
                                    <span>Movies</span>
                                    <span>{stats?.total_content?.movies ? ((stats.total_content.movies / (stats.total_content.total || 1)) * 100).toFixed(0) : 0}%</span>
                                </div>
                                <div className="h-2 w-full bg-secondary rounded-full overflow-hidden">
                                    <div className="h-full bg-blue-500" style={{ width: `${stats?.total_content?.movies ? ((stats.total_content.movies / (stats.total_content.total || 1)) * 100) : 0}%` }} />
                                </div>
                            </div>
                            <div className="space-y-2">
                                <div className="flex items-center justify-between text-sm">
                                    <span>Series</span>
                                    <span>{stats?.total_content?.series ? ((stats.total_content.series / (stats.total_content.total || 1)) * 100).toFixed(0) : 0}%</span>
                                </div>
                                <div className="h-2 w-full bg-secondary rounded-full overflow-hidden">
                                    <div className="h-full bg-purple-500" style={{ width: `${stats?.total_content?.series ? ((stats.total_content.series / (stats.total_content.total || 1)) * 100) : 0}%` }} />
                                </div>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Quick Info */}
            <div>
                <h3 className="text-xl font-semibold mb-4">Quick Info</h3>
                <Card>
                    <CardContent className="p-6">
                        <p className="text-muted-foreground">
                            For detailed subscription management and sync controls, visit the <strong>XtreamTV &gt; Subscriptions</strong> page.
                        </p>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
