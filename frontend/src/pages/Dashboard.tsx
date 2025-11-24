import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Film, Tv, RefreshCw, AlertCircle, CheckCircle2, StopCircle } from 'lucide-react';
import api from '@/lib/api';

interface Subscription {
    id: number;
    name: string;
    xtream_url: string;
    username: string;
    password: string;
    output_dir: string;
    is_active: boolean;
}

interface SyncStatus {
    id: number;
    subscription_id: number;
    type: string;
    last_sync: string | null;
    status: string;
    items_added: number;
    items_deleted: number;
    error_message?: string;
}

export default function Dashboard() {
    const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
    const [statuses, setStatuses] = useState<SyncStatus[]>([]);
    const [loading, setLoading] = useState(false);

    const fetchData = async () => {
        try {
            const [subsRes, statusRes] = await Promise.all([
                api.get<Subscription[]>('/subscriptions/'),
                api.get<SyncStatus[]>('/sync/status')
            ]);
            setSubscriptions(subsRes.data);
            setStatuses(statusRes.data);
        } catch (error) {
            console.error("Failed to fetch data", error);
        }
    };

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 5000);
        return () => clearInterval(interval);
    }, []);

    const triggerSync = async (subscriptionId: number, type: 'movies' | 'series') => {
        try {
            setLoading(true);
            await api.post(`/sync/${type}/${subscriptionId}`);
            await fetchData();
        } catch (error) {
            console.error(`Failed to trigger ${type} sync`, error);
        } finally {
            setLoading(false);
        }
    };

    const stopSync = async (subscriptionId: number, type: 'movies' | 'series') => {
        try {
            setLoading(true);
            await api.post(`/sync/stop/${subscriptionId}/${type}`);
            await fetchData();
        } catch (error) {
            console.error(`Failed to stop ${type} sync`, error);
        } finally {
            setLoading(false);
        }
    };



    const getStatusColor = (status: string) => {
        switch (status) {
            case 'success': return 'text-green-500';
            case 'failed': return 'text-red-500';
            case 'running': return 'text-blue-500 animate-pulse';
            default: return 'text-muted-foreground';
        }
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'success': return <CheckCircle2 className="w-5 h-5 text-green-500" />;
            case 'failed': return <AlertCircle className="w-5 h-5 text-red-500" />;
            case 'running': return <RefreshCw className="w-5 h-5 text-blue-500 animate-spin" />;
            default: return <div className="w-5 h-5 rounded-full bg-muted" />;
        }
    };

    const getStatus = (subscriptionId: number, type: string) => {
        return statuses.find(s => s.subscription_id === subscriptionId && s.type === type);
    };

    return (
        <div className="space-y-8">
            <div>
                <h2 className="text-3xl font-bold tracking-tight">Dashboard</h2>
                <p className="text-muted-foreground">Monitor sync status for all subscriptions</p>
            </div>

            {subscriptions.length === 0 ? (
                <Card>
                    <CardContent className="p-8 text-center text-muted-foreground">
                        No subscriptions configured. Go to Configuration to add subscriptions.
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-4">
                    {subscriptions.map(sub => {
                        const movieStatus = getStatus(sub.id, 'movies');
                        const seriesStatus = getStatus(sub.id, 'series');

                        return (
                            <Card key={sub.id}>
                                <CardHeader>
                                    <CardTitle className="flex items-center justify-between">
                                        <span>{sub.name}</span>
                                        {!sub.is_active && (
                                            <span className="text-sm font-normal text-muted-foreground">(Inactive)</span>
                                        )}
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        {/* Movies */}
                                        <div className="border rounded-lg p-4">
                                            <div className="flex items-center justify-between mb-3">
                                                <div className="flex items-center gap-2">
                                                    <Film className="w-5 h-5 text-muted-foreground" />
                                                    <span className="font-medium">Movies</span>
                                                </div>
                                                {getStatusIcon(movieStatus?.status || 'idle')}
                                            </div>
                                            <div className="space-y-2 text-sm">
                                                <div className="flex justify-between">
                                                    <span className="text-muted-foreground">Status:</span>
                                                    <span className={`font-medium capitalize ${getStatusColor(movieStatus?.status || 'idle')}`}>
                                                        {movieStatus?.status || 'Idle'}
                                                    </span>
                                                </div>
                                                {movieStatus?.last_sync && (
                                                    <div className="flex justify-between">
                                                        <span className="text-muted-foreground">Last Sync:</span>
                                                        <span>{new Date(movieStatus.last_sync).toLocaleString()}</span>
                                                    </div>
                                                )}
                                                {movieStatus && (
                                                    <>
                                                        <div className="flex justify-between">
                                                            <span className="text-muted-foreground">Added:</span>
                                                            <span className="text-green-600">{movieStatus.items_added}</span>
                                                        </div>
                                                        <div className="flex justify-between">
                                                            <span className="text-muted-foreground">Deleted:</span>
                                                            <span className="text-red-600">{movieStatus.items_deleted}</span>
                                                        </div>
                                                    </>
                                                )}
                                            </div>
                                            <div className="mt-4">
                                                {movieStatus?.status === 'running' ? (
                                                    <Button
                                                        onClick={() => stopSync(sub.id, 'movies')}
                                                        disabled={loading || !sub.is_active}
                                                        variant="destructive"
                                                        size="sm"
                                                        className="w-full"
                                                    >
                                                        <StopCircle className="w-4 h-4 mr-2" />
                                                        Stop Sync
                                                    </Button>
                                                ) : (
                                                    <Button
                                                        onClick={() => triggerSync(sub.id, 'movies')}
                                                        disabled={loading || !sub.is_active}
                                                        size="sm"
                                                        className="w-full"
                                                    >
                                                        <RefreshCw className="w-4 h-4 mr-2" />
                                                        Sync Now
                                                    </Button>
                                                )}
                                            </div>
                                        </div>

                                        {/* Series */}
                                        <div className="border rounded-lg p-4">
                                            <div className="flex items-center justify-between mb-3">
                                                <div className="flex items-center gap-2">
                                                    <Tv className="w-5 h-5 text-muted-foreground" />
                                                    <span className="font-medium">Series</span>
                                                </div>
                                                {getStatusIcon(seriesStatus?.status || 'idle')}
                                            </div>
                                            <div className="space-y-2 text-sm">
                                                <div className="flex justify-between">
                                                    <span className="text-muted-foreground">Status:</span>
                                                    <span className={`font-medium capitalize ${getStatusColor(seriesStatus?.status || 'idle')}`}>
                                                        {seriesStatus?.status || 'Idle'}
                                                    </span>
                                                </div>
                                                {seriesStatus?.last_sync && (
                                                    <div className="flex justify-between">
                                                        <span className="text-muted-foreground">Last Sync:</span>
                                                        <span>{new Date(seriesStatus.last_sync).toLocaleString()}</span>
                                                    </div>
                                                )}
                                                {seriesStatus && (
                                                    <>
                                                        <div className="flex justify-between">
                                                            <span className="text-muted-foreground">Added:</span>
                                                            <span className="text-green-600">{seriesStatus.items_added}</span>
                                                        </div>
                                                        <div className="flex justify-between">
                                                            <span className="text-muted-foreground">Deleted:</span>
                                                            <span className="text-red-600">{seriesStatus.items_deleted}</span>
                                                        </div>
                                                    </>
                                                )}
                                            </div>
                                            <div className="mt-4">
                                                {seriesStatus?.status === 'running' ? (
                                                    <Button
                                                        onClick={() => stopSync(sub.id, 'series')}
                                                        disabled={loading || !sub.is_active}
                                                        variant="destructive"
                                                        size="sm"
                                                        className="w-full"
                                                    >
                                                        <StopCircle className="w-4 h-4 mr-2" />
                                                        Stop Sync
                                                    </Button>
                                                ) : (
                                                    <Button
                                                        onClick={() => triggerSync(sub.id, 'series')}
                                                        disabled={loading || !sub.is_active}
                                                        size="sm"
                                                        className="w-full"
                                                    >
                                                        <RefreshCw className="w-4 h-4 mr-2" />
                                                        Sync Now
                                                    </Button>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
