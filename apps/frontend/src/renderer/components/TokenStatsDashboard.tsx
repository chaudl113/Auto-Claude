/**
 * TokenStatsDashboard - Component for displaying token usage statistics
 *
 * Shows:
 * - Total token usage (input/output/cached)
 * - Cache hit rate and savings
 * - Cost breakdown by operation and model
 * - Usage trends over time (24h)
 */
import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  BarChart3,
  Coins,
  Zap,
  TrendingUp,
  RefreshCw,
  Database,
  Clock,
  ArrowUpRight,
  ArrowDownRight
} from 'lucide-react';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell
} from 'recharts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { cn } from '../lib/utils';

interface TokenStats {
  total_requests: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cached_tokens: number;
  total_cost: number;
  cache_hits: number;
  cache_misses: number;
  cache_hit_rate: number;
  tokens_saved_by_cache: number;
  cost_saved_by_cache: number;
  avg_response_time_ms: number;
  by_operation: Record<string, {
    requests: number;
    input_tokens: number;
    output_tokens: number;
    cached_tokens: number;
    cost: number;
  }>;
  by_model: Record<string, {
    requests: number;
    input_tokens: number;
    output_tokens: number;
    cost: number;
  }>;
  by_hour: Record<string, {
    requests: number;
    tokens: number;
    cost: number;
  }>;
  recent_requests: Array<{
    timestamp: string;
    operation: string;
    model: string;
    input_tokens: number;
    output_tokens: number;
    cached_tokens: number;
    cost: number;
  }>;
}

interface TokenStatsDashboardProps {
  projectId?: string;
  compact?: boolean;
}

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

function formatNumber(num: number): string {
  if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`;
  if (num >= 1_000) return `${(num / 1_000).toFixed(1)}K`;
  return num.toLocaleString();
}

function formatCost(cost: number): string {
  if (cost < 0.01) return `$${cost.toFixed(4)}`;
  return `$${cost.toFixed(2)}`;
}

export function TokenStatsDashboard({ projectId, compact = false }: TokenStatsDashboardProps) {
  const { t } = useTranslation();
  const [stats, setStats] = useState<TokenStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await window.electronAPI.tokenStats.get(projectId);
      if (result.success && result.data) {
        setStats(result.data);
      } else {
        setError(result.error || 'Failed to fetch stats');
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchStats();
    // Refresh every 30 seconds
    const interval = setInterval(fetchStats, 30000);
    return () => clearInterval(interval);
  }, [fetchStats]);

  if (isLoading && !stats) {
    return (
      <div className="flex items-center justify-center p-8">
        <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-center text-destructive">
        {error}
        <Button variant="outline" size="sm" onClick={fetchStats} className="ml-2">
          {t('buttons.retry', 'Retry')}
        </Button>
      </div>
    );
  }

  if (!stats) return null;

  // Prepare chart data
  const hourlyData = Object.entries(stats.by_hour)
    .sort(([a], [b]) => a.localeCompare(b))
    .slice(-12)
    .map(([hour, data]) => ({
      hour: hour.split(' ')[1],
      tokens: data.tokens,
      cost: data.cost,
      requests: data.requests
    }));

  const operationData = Object.entries(stats.by_operation)
    .map(([name, data]) => ({
      name: name.replace(/_/g, ' '),
      cost: data.cost,
      requests: data.requests,
      tokens: data.input_tokens + data.output_tokens
    }))
    .sort((a, b) => b.cost - a.cost)
    .slice(0, 6);

  const modelData = Object.entries(stats.by_model).map(([name, data]) => ({
    name: name.split('-').slice(0, 2).join('-'),
    cost: data.cost,
    requests: data.requests
  }));

  const cacheData = [
    { name: 'Hits', value: stats.cache_hits, color: '#10b981' },
    { name: 'Misses', value: stats.cache_misses, color: '#ef4444' }
  ];

  if (compact) {
    return (
      <div className="grid grid-cols-4 gap-2 p-2">
        <div className="text-center">
          <div className="text-lg font-bold">{formatNumber(stats.total_requests)}</div>
          <div className="text-xs text-muted-foreground">{t('tokenStats.requests', 'Requests')}</div>
        </div>
        <div className="text-center">
          <div className="text-lg font-bold">{formatNumber(stats.total_input_tokens + stats.total_output_tokens)}</div>
          <div className="text-xs text-muted-foreground">{t('tokenStats.tokens', 'Tokens')}</div>
        </div>
        <div className="text-center">
          <div className="text-lg font-bold">{stats.cache_hit_rate.toFixed(0)}%</div>
          <div className="text-xs text-muted-foreground">{t('tokenStats.cacheRate', 'Cache')}</div>
        </div>
        <div className="text-center">
          <div className="text-lg font-bold">{formatCost(stats.total_cost)}</div>
          <div className="text-xs text-muted-foreground">{t('tokenStats.cost', 'Cost')}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <BarChart3 className="h-5 w-5" />
          {t('tokenStats.title', 'Token Usage Statistics')}
        </h2>
        <Button variant="outline" size="sm" onClick={fetchStats} disabled={isLoading}>
          <RefreshCw className={cn('h-4 w-4 mr-2', isLoading && 'animate-spin')} />
          {t('buttons.refresh', 'Refresh')}
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-1">
              <Zap className="h-3 w-3" />
              {t('tokenStats.totalTokens', 'Total Tokens')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatNumber(stats.total_input_tokens + stats.total_output_tokens)}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              <span className="text-blue-500">{formatNumber(stats.total_input_tokens)} in</span>
              {' / '}
              <span className="text-green-500">{formatNumber(stats.total_output_tokens)} out</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-1">
              <Database className="h-3 w-3" />
              {t('tokenStats.cacheHitRate', 'Cache Hit Rate')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold flex items-center gap-2">
              {stats.cache_hit_rate.toFixed(1)}%
              {stats.cache_hit_rate > 50 ? (
                <ArrowUpRight className="h-4 w-4 text-green-500" />
              ) : (
                <ArrowDownRight className="h-4 w-4 text-red-500" />
              )}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              {formatNumber(stats.tokens_saved_by_cache)} {t('tokenStats.tokensSaved', 'tokens saved')}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-1">
              <Coins className="h-3 w-3" />
              {t('tokenStats.totalCost', 'Total Cost')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatCost(stats.total_cost)}</div>
            <div className="text-xs text-green-500 mt-1">
              {formatCost(stats.cost_saved_by_cache)} {t('tokenStats.savedByCache', 'saved by cache')}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {t('tokenStats.avgResponseTime', 'Avg Response Time')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.avg_response_time_ms.toFixed(0)}ms</div>
            <div className="text-xs text-muted-foreground mt-1">
              {stats.total_requests.toLocaleString()} {t('tokenStats.requests', 'requests')}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Hourly Usage Trend */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2">
              <TrendingUp className="h-4 w-4" />
              {t('tokenStats.usageTrend', 'Usage Trend (24h)')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={hourlyData}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="hour" className="text-xs" />
                  <YAxis className="text-xs" tickFormatter={formatNumber} />
                  <Tooltip
                    formatter={(value: number) => [formatNumber(value), 'Tokens']}
                    labelFormatter={(label) => `Hour: ${label}`}
                  />
                  <Line
                    type="monotone"
                    dataKey="tokens"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Cache Distribution */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2">
              <Database className="h-4 w-4" />
              {t('tokenStats.cacheDistribution', 'Cache Distribution')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-48 flex items-center justify-center">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={cacheData}
                    cx="50%"
                    cy="50%"
                    innerRadius={40}
                    outerRadius={70}
                    paddingAngle={2}
                    dataKey="value"
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  >
                    {cacheData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value: number) => [formatNumber(value), 'Requests']} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Cost by Operation */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm flex items-center gap-2">
            <Coins className="h-4 w-4" />
            {t('tokenStats.costByOperation', 'Cost by Operation')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={operationData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis type="number" tickFormatter={(v) => `$${v.toFixed(2)}`} className="text-xs" />
                <YAxis type="category" dataKey="name" width={100} className="text-xs" />
                <Tooltip formatter={(value: number) => [formatCost(value), 'Cost']} />
                <Bar dataKey="cost" fill="#3b82f6" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Models Used */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">{t('tokenStats.modelUsage', 'Model Usage')}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {modelData.map((model, index) => (
              <div key={model.name} className="flex items-center justify-between p-2 rounded bg-muted/50">
                <div className="flex items-center gap-2">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: COLORS[index % COLORS.length] }}
                  />
                  <span className="font-medium text-sm">{model.name}</span>
                  <Badge variant="outline" className="text-xs">
                    {model.requests} requests
                  </Badge>
                </div>
                <span className="font-mono text-sm">{formatCost(model.cost)}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Recent Requests */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">{t('tokenStats.recentRequests', 'Recent Requests')}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-1 max-h-48 overflow-y-auto">
            {stats.recent_requests.slice(-10).reverse().map((req, index) => (
              <div
                key={index}
                className="flex items-center justify-between text-xs p-2 rounded hover:bg-muted/50"
              >
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground">
                    {new Date(req.timestamp).toLocaleTimeString()}
                  </span>
                  <span className="font-medium">{req.operation}</span>
                  {req.cached_tokens > 0 && (
                    <Badge variant="secondary" className="text-xs">
                      cached
                    </Badge>
                  )}
                </div>
                <div className="flex items-center gap-4 text-muted-foreground">
                  <span>{formatNumber(req.input_tokens + req.output_tokens)} tokens</span>
                  <span className="font-mono">{formatCost(req.cost)}</span>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default TokenStatsDashboard;
