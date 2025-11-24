import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Edit, Trash2, Save, X, Check } from 'lucide-react';
import api from '@/lib/api';

interface Subscription {
    id: number;
    name: string;
    xtream_url: string;
    username: string;
    password: string;
    movies_dir: string;
    series_dir: string;
    is_active: boolean;
}

interface SubscriptionForm {
    name: string;
    xtream_url: string;
    username: string;
    password: string;
    movies_dir: string;
    series_dir: string;
    is_active: boolean;
}

export default function Configuration() {
    const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
    const [loading, setLoading] = useState(false);
    const [editingId, setEditingId] = useState<number | null>(null);
    const [isAdding, setIsAdding] = useState(false);
    const [formData, setFormData] = useState<SubscriptionForm>({
        name: '',
        xtream_url: '',
        username: '',
        password: '',
        movies_dir: '/output/movies',
        series_dir: '/output/series',
        is_active: true
    });

    useEffect(() => {
        fetchSubscriptions();
    }, []);

    const fetchSubscriptions = async () => {
        try {
            const res = await api.get<Subscription[]>('/subscriptions/');
            setSubscriptions(res.data);
        } catch (error) {
            console.error("Failed to fetch subscriptions", error);
        }
    };

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value, type, checked } = e.target;
        setFormData(prev => ({
            ...prev,
            [name]: type === 'checkbox' ? checked : value
        }));
    };

    const startAdd = () => {
        setFormData({
            name: '',
            xtream_url: '',
            username: '',
            password: '',
            movies_dir: '',
            series_dir: '',
            is_active: true
        });
        setIsAdding(true);
        setEditingId(null);
    };

    const startEdit = (sub: Subscription) => {
        setFormData({
            name: sub.name,
            xtream_url: sub.xtream_url,
            username: sub.username,
            password: sub.password,
            movies_dir: sub.movies_dir,
            series_dir: sub.series_dir,
            is_active: sub.is_active
        });
        setEditingId(sub.id);
        setIsAdding(false);
    };

    const cancelEdit = () => {
        setEditingId(null);
        setIsAdding(false);
        setFormData({
            name: '',
            xtream_url: '',
            username: '',
            password: '',
            movies_dir: '',
            series_dir: '',
            is_active: true
        });
    };

    const handleSave = async () => {
        setLoading(true);
        try {
            if (isAdding) {
                await api.post('/subscriptions/', formData);
            } else if (editingId) {
                await api.put(`/subscriptions/${editingId}`, formData);
            }
            await fetchSubscriptions();
            cancelEdit();
        } catch (error) {
            console.error("Failed to save subscription", error);
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (id: number) => {
        if (!confirm('Are you sure you want to delete this subscription?')) return;

        setLoading(true);
        try {
            await api.delete(`/subscriptions/${id}`);
            await fetchSubscriptions();
        } catch (error) {
            console.error("Failed to delete subscription", error);
        } finally {
            setLoading(false);
        }
    };

    const toggleActive = async (sub: Subscription) => {
        setLoading(true);
        try {
            await api.put(`/subscriptions/${sub.id}`, {
                is_active: !sub.is_active
            });
            await fetchSubscriptions();
        } catch (error) {
            console.error("Failed to toggle subscription", error);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="space-y-8">
            <div>
                <h2 className="text-3xl font-bold tracking-tight">Configuration</h2>
                <p className="text-muted-foreground">Manage your Xtream Codes subscriptions.</p>
            </div>

            <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
                    <CardTitle>Subscriptions</CardTitle>
                    <Button onClick={startAdd} disabled={isAdding || editingId !== null || loading} size="sm">
                        <Plus className="w-4 h-4 mr-2" />
                        Add Subscription
                    </Button>
                </CardHeader>
                <CardContent>
                    <div className="border rounded-md">
                        <table className="w-full text-sm">
                            <thead className="bg-muted/50 text-muted-foreground">
                                <tr>
                                    <th className="p-3 text-left">Name</th>
                                    <th className="p-3 text-left">URL</th>
                                    <th className="p-3 text-left">Username</th>
                                    <th className="p-3 text-left">Password</th>
                                    <th className="p-3 text-left">Movies Dir</th>
                                    <th className="p-3 text-left">Series Dir</th>
                                    <th className="p-3 text-center">Active</th>
                                    <th className="p-3 text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y">
                                {isAdding && (
                                    <tr className="bg-accent/50">
                                        <td className="p-2">
                                            <Input
                                                name="name"
                                                value={formData.name}
                                                onChange={handleInputChange}
                                                placeholder="My Subscription"
                                                className="h-8"
                                            />
                                        </td>
                                        <td className="p-2">
                                            <Input
                                                name="xtream_url"
                                                value={formData.xtream_url}
                                                onChange={handleInputChange}
                                                placeholder="http://example.com:8080"
                                                className="h-8"
                                            />
                                        </td>
                                        <td className="p-2">
                                            <Input
                                                name="username"
                                                value={formData.username}
                                                onChange={handleInputChange}
                                                placeholder="username"
                                                className="h-8"
                                            />
                                        </td>
                                        <td className="p-2">
                                            <Input
                                                name="password"
                                                type="password"
                                                value={formData.password}
                                                onChange={handleInputChange}
                                                placeholder="password"
                                                className="h-8"
                                            />
                                        </td>
                                        <td className="p-2">
                                            <Input
                                                name="movies_dir"
                                                value={formData.movies_dir}
                                                onChange={handleInputChange}
                                                placeholder="/output/movies"
                                                className="h-8"
                                            />
                                        </td>
                                        <td className="p-2">
                                            <Input
                                                name="series_dir"
                                                value={formData.series_dir}
                                                onChange={handleInputChange}
                                                placeholder="/output/series"
                                                className="h-8"
                                            />
                                        </td>
                                        <td className="p-2 text-center">
                                            <input
                                                type="checkbox"
                                                name="is_active"
                                                checked={formData.is_active}
                                                onChange={handleInputChange}
                                                className="w-4 h-4"
                                            />
                                        </td>
                                        <td className="p-2">
                                            <div className="flex gap-2 justify-end">
                                                <Button onClick={handleSave} disabled={loading} size="sm" variant="default">
                                                    <Save className="w-4 h-4" />
                                                </Button>
                                                <Button onClick={cancelEdit} disabled={loading} size="sm" variant="outline">
                                                    <X className="w-4 h-4" />
                                                </Button>
                                            </div>
                                        </td>
                                    </tr>
                                )}
                                {subscriptions.map(sub => (
                                    editingId === sub.id ? (
                                        <tr key={sub.id} className="bg-accent/50">
                                            <td className="p-2">
                                                <Input
                                                    name="name"
                                                    value={formData.name}
                                                    onChange={handleInputChange}
                                                    className="h-8"
                                                />
                                            </td>
                                            <td className="p-2">
                                                <Input
                                                    name="xtream_url"
                                                    value={formData.xtream_url}
                                                    onChange={handleInputChange}
                                                    className="h-8"
                                                />
                                            </td>
                                            <td className="p-2">
                                                <Input
                                                    name="username"
                                                    value={formData.username}
                                                    onChange={handleInputChange}
                                                    className="h-8"
                                                />
                                            </td>
                                            <td className="p-2">
                                                <Input
                                                    name="password"
                                                    type="password"
                                                    value={formData.password}
                                                    onChange={handleInputChange}
                                                    className="h-8"
                                                />
                                            </td>
                                            <td className="p-2">
                                                <Input
                                                    name="movies_dir"
                                                    value={formData.movies_dir}
                                                    onChange={handleInputChange}
                                                    className="h-8"
                                                />
                                            </td>
                                            <td className="p-2">
                                                <Input
                                                    name="series_dir"
                                                    value={formData.series_dir}
                                                    onChange={handleInputChange}
                                                    className="h-8"
                                                />
                                            </td>
                                            <td className="p-2 text-center">
                                                <input
                                                    type="checkbox"
                                                    name="is_active"
                                                    checked={formData.is_active}
                                                    onChange={handleInputChange}
                                                    className="w-4 h-4"
                                                />
                                            </td>
                                            <td className="p-2">
                                                <div className="flex gap-2 justify-end">
                                                    <Button onClick={handleSave} disabled={loading} size="sm" variant="default">
                                                        <Save className="w-4 h-4" />
                                                    </Button>
                                                    <Button onClick={cancelEdit} disabled={loading} size="sm" variant="outline">
                                                        <X className="w-4 h-4" />
                                                    </Button>
                                                </div>
                                            </td>
                                        </tr>
                                    ) : (
                                        <tr key={sub.id} className="hover:bg-muted/50 transition-colors">
                                            <td className="p-3 font-medium">{sub.name}</td>
                                            <td className="p-3 text-muted-foreground">{sub.xtream_url}</td>
                                            <td className="p-3 text-muted-foreground">{sub.username}</td>
                                            <td className="p-3 text-muted-foreground">••••••••</td>
                                            <td className="p-3 text-muted-foreground">{sub.movies_dir}</td>
                                            <td className="p-3 text-muted-foreground">{sub.series_dir}</td>
                                            <td className="p-3 text-center">
                                                <button
                                                    onClick={() => toggleActive(sub)}
                                                    disabled={loading}
                                                    className={`w-5 h-5 rounded flex items-center justify-center ${sub.is_active ? 'bg-green-500 text-white' : 'bg-gray-300'
                                                        }`}
                                                >
                                                    {sub.is_active && <Check className="w-3 h-3" />}
                                                </button>
                                            </td>
                                            <td className="p-3">
                                                <div className="flex gap-2 justify-end">
                                                    <Button
                                                        onClick={() => startEdit(sub)}
                                                        disabled={loading || isAdding || editingId !== null}
                                                        size="sm"
                                                        variant="outline"
                                                    >
                                                        <Edit className="w-4 h-4" />
                                                    </Button>
                                                    <Button
                                                        onClick={() => handleDelete(sub.id)}
                                                        disabled={loading || isAdding || editingId !== null}
                                                        size="sm"
                                                        variant="destructive"
                                                    >
                                                        <Trash2 className="w-4 h-4" />
                                                    </Button>
                                                </div>
                                            </td>
                                        </tr>
                                    )
                                ))}
                                {subscriptions.length === 0 && !isAdding && (
                                    <tr>
                                        <td colSpan={7} className="p-8 text-center text-muted-foreground">
                                            No subscriptions configured. Click "Add Subscription" to get started.
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
