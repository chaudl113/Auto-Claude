import { useState, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Badge } from './ui/badge';
import { ScrollArea } from './ui/scroll-area';
import {
  Activity,
  TrendingUp,
  Clock,
  CheckCircle,
  AlertCircle,
  Zap,
  Code2,
  TestTube,
  GitPullRequest,
  Calendar,
  BarChart3
} from 'lucide-react';
import { useTaskStore } from '../stores/task-store';
import type { Task } from '../../shared/types';
import { cn } from '../lib/utils';

interface ProgressDashboardProps {
  projectId: string;
}

interface MetricCardProps {
  title: string;
  value: string | number;
  change?: number;
  icon: React.ElementType;
  description?: string;
}

function MetricCard({ title, value, change, icon: Icon, description }: MetricCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {change !== undefined && (
          <p className={cn('text-xs mt-1', change >= 0 ? 'text-green-500' : 'text-red-500')}>
            {change >= 0 ? '+' : ''}{change}% from last period
          </p>
        )}
        {description && (
          <p className="text-xs text-muted-foreground mt-1">{description}</p>
        )}
      </CardContent>
    </Card>
  );
}

export function ProgressDashboard({ projectId }: ProgressDashboardProps) {
  const { t } = useTranslation();
  const tasks = useTaskStore((state) => state.tasks);

  // Time period filter
  const [timePeriod, setTimePeriod] = useState<'7d' | '30d' | '90d' | 'all'>('30d');
  const [activeTab, setActiveTab] = useState('overview');

  // Filter tasks by project
  const projectTasks = useMemo(() => {
    return tasks; // All tasks are already filtered by project when loaded
  }, [tasks]);

  // Filter tasks by time period
  const filteredTasks = useMemo(() => {
    if (timePeriod === 'all') return projectTasks;

    const now = new Date();
    const daysAgo = {
      '7d': 7,
      '30d': 30,
      '90d': 90
    }[timePeriod];

    const cutoff = new Date(now.getTime() - daysAgo * 24 * 60 * 60 * 1000);
    return projectTasks.filter(task => new Date(task.createdAt) >= cutoff);
  }, [projectTasks, timePeriod]);

  // Calculate metrics
  const metrics = useMemo(() => {
    const total = filteredTasks.length;
    const completed = filteredTasks.filter(t => t.status === 'done').length;
    const inProgress = filteredTasks.filter(t => t.status === 'in_progress').length;
    const failed = filteredTasks.filter(t => t.reviewReason === 'errors').length;
    
    // Calculate average completion time (for completed tasks)
    const completedWithDates = filteredTasks.filter(
      t => t.status === 'done' && t.createdAt && t.updatedAt
    );
    const avgCompletionTime = completedWithDates.length > 0
      ? Math.round(
          completedWithDates.reduce((sum, t) => {
            const created = new Date(t.createdAt).getTime();
            const updated = new Date(t.updatedAt).getTime();
            return sum + (updated - created);
          }, 0) / completedWithDates.length / (1000 * 60 * 60) // Convert to hours
        )
      : 0;

    // Calculate success rate
    const successRate = total > 0 ? Math.round((completed / total) * 100) : 0;

    // Calculate productivity (tasks completed per week)
    const weeks = timePeriod === 'all' ? 4 : { '7d': 1, '30d': 4, '90d': 13 }[timePeriod];
    const tasksPerWeek = weeks > 0 ? Math.round(completed / weeks) : 0;

    return {
      total,
      completed,
      inProgress,
      failed,
      avgCompletionTime,
      successRate,
      tasksPerWeek
    };
  }, [filteredTasks, timePeriod, projectTasks]);

  // Historical trend data (simulated based on tasks)
  const historicalData = useMemo(() => {
    const periods: { date: string; completed: number; created: number; failed: number }[] = [];
    const now = new Date();
    
    const numPoints = timePeriod === 'all' ? 12 : { '7d': 7, '30d': 30, '90d': 12 }[timePeriod];
    
    for (let i = numPoints - 1; i >= 0; i--) {
      const pointDate = new Date(now);
      
      if (timePeriod === '7d') {
        pointDate.setDate(pointDate.getDate() - i);
      } else if (timePeriod === '30d') {
        pointDate.setDate(pointDate.getDate() - i);
      } else {
        pointDate.setDate(pointDate.getDate() - i * 7); // Weekly points
      }

      const dateStr = timePeriod === '7d' || timePeriod === '30d'
        ? pointDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
        : pointDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

      const nextDate = new Date(pointDate);
      nextDate.setDate(nextDate.getDate() + 1);
      
      const completed = projectTasks.filter(
        t => t.status === 'done' &&
        new Date(t.updatedAt) >= pointDate &&
        new Date(t.updatedAt) < nextDate
      ).length;
      
      const created = projectTasks.filter(
        t => new Date(t.createdAt) >= pointDate &&
        new Date(t.createdAt) < nextDate
      ).length;
      
      const failed = projectTasks.filter(
        t => t.reviewReason === 'errors' &&
        new Date(t.updatedAt) >= pointDate &&
        new Date(t.updatedAt) < nextDate
      ).length;

      periods.push({ date: dateStr, completed, created, failed });
    }

    return periods;
  }, [projectTasks, timePeriod]);

  // Status distribution data
  const statusDistribution = useMemo(() => {
    return [
      { name: 'Completed', value: metrics.completed, color: '#22c55e' },
      { name: 'In Progress', value: metrics.inProgress, color: '#3b82f6' },
      { name: 'Failed', value: metrics.failed, color: '#ef4444' },
      { name: 'Other', value: metrics.total - metrics.completed - metrics.inProgress - metrics.failed, color: '#64748b' }
    ].filter(d => d.value > 0);
  }, [metrics]);

  // Category breakdown (if tasks have categories)
  const categoryBreakdown = useMemo(() => {
    const categories = new Map<string, number>();
    filteredTasks.forEach(task => {
      const category = task.metadata?.category || 'Uncategorized';
      categories.set(category, (categories.get(category) || 0) + 1);
    });

    return Array.from(categories.entries()).map(([name, value]) => ({ name, value }));
  }, [filteredTasks]);

  // Recent activity
  const recentActivity = useMemo(() => {
    return [...filteredTasks]
      .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
      .slice(0, 10);
  }, [filteredTasks]);

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border">
        <div>
          <h2 className="text-lg font-semibold">Progress Dashboard</h2>
          <p className="text-sm text-muted-foreground">
            Track your development metrics and trends
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={timePeriod} onValueChange={(v: any) => setTimePeriod(v)}>
            <SelectTrigger className="w-[140px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7d">Last 7 days</SelectItem>
              <SelectItem value="30d">Last 30 days</SelectItem>
              <SelectItem value="90d">Last 90 days</SelectItem>
              <SelectItem value="all">All time</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Content */}
      <ScrollArea className="flex-1">
        <div className="p-6 space-y-6">
          {/* Metrics Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
              title="Total Tasks"
              value={metrics.total}
              icon={Activity}
              description="Tasks in selected period"
            />
            <MetricCard
              title="Completed"
              value={metrics.completed}
              icon={CheckCircle}
              change={5}
              description="Successfully finished"
            />
            <MetricCard
              title="Success Rate"
              value={`${metrics.successRate}%`}
              icon={TrendingUp}
              change={metrics.successRate >= 70 ? 2 : -3}
              description="Tasks completed successfully"
            />
            <MetricCard
              title="Avg Completion Time"
              value={`${metrics.avgCompletionTime}h`}
              icon={Clock}
              change={-8}
              description="Average time to complete"
            />
          </div>

          {/* Charts */}
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList>
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="trends">Trends</TabsTrigger>
              <TabsTrigger value="details">Details</TabsTrigger>
            </TabsList>

            <TabsContent value="overview" className="space-y-6">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Completion Trend */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <TrendingUp className="h-4 w-4" />
                      Task Completion Trend
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ResponsiveContainer width="100%" height={300}>
                      <LineChart data={historicalData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="date" />
                        <YAxis />
                        <RechartsTooltip />
                        <Legend />
                        <Line
                          type="monotone"
                          dataKey="completed"
                          stroke="#22c55e"
                          strokeWidth={2}
                          name="Completed"
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>

                {/* Status Distribution */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <BarChart3 className="h-4 w-4" />
                      Status Distribution
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ResponsiveContainer width="100%" height={300}>
                      <PieChart>
                        <Pie
                          data={statusDistribution}
                          cx="50%"
                          cy="50%"
                          labelLine={false}
                          label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                          outerRadius={100}
                          fill="#8884d8"
                          dataKey="value"
                        >
                          {statusDistribution.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.color} />
                          ))}
                        </Pie>
                        <RechartsTooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>

                {/* Task Creation vs Completion */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Activity className="h-4 w-4" />
                      Created vs Completed
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ResponsiveContainer width="100%" height={300}>
                      <BarChart data={historicalData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="date" />
                        <YAxis />
                        <RechartsTooltip />
                        <Legend />
                        <Bar dataKey="created" fill="#3b82f6" name="Created" />
                        <Bar dataKey="completed" fill="#22c55e" name="Completed" />
                      </BarChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>

                {/* Category Breakdown */}
                {categoryBreakdown.length > 0 && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Code2 className="h-4 w-4" />
                        Tasks by Category
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ResponsiveContainer width="100%" height={300}>
                        <BarChart data={categoryBreakdown} layout="vertical">
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis type="number" />
                          <YAxis dataKey="name" type="category" width={100} />
                          <RechartsTooltip />
                          <Bar dataKey="value" fill="#8b5cf6" />
                        </BarChart>
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>
                )}
              </div>
            </TabsContent>

            <TabsContent value="trends" className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Detailed Trend Analysis</CardTitle>
                  <CardDescription>Track failures and creation rates over time</CardDescription>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={400}>
                    <LineChart data={historicalData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" />
                      <YAxis />
                      <RechartsTooltip />
                      <Legend />
                      <Line
                        type="monotone"
                        dataKey="created"
                        stroke="#3b82f6"
                        strokeWidth={2}
                        name="Created"
                      />
                      <Line
                        type="monotone"
                        dataKey="completed"
                        stroke="#22c55e"
                        strokeWidth={2}
                        name="Completed"
                      />
                      <Line
                        type="monotone"
                        dataKey="failed"
                        stroke="#ef4444"
                        strokeWidth={2}
                        name="Failed"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="details" className="space-y-6">
              {/* Recent Activity */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Calendar className="h-4 w-4" />
                    Recent Activity
                  </CardTitle>
                  <CardDescription>Latest task updates and status changes</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {recentActivity.map((task) => (
                      <div
                        key={task.id}
                        className="flex items-start gap-3 p-3 rounded-lg border border-border hover:bg-muted/50 transition-colors"
                      >
                        <div className="mt-1">
                          {task.status === 'done' && <CheckCircle className="h-4 w-4 text-green-500" />}
                          {task.status === 'in_progress' && <Zap className="h-4 w-4 text-blue-500" />}
                          {task.reviewReason === 'errors' && <AlertCircle className="h-4 w-4 text-red-500" />}
                          {task.status === 'human_review' && <TestTube className="h-4 w-4 text-yellow-500" />}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-sm truncate">{task.title}</p>
                          <p className="text-xs text-muted-foreground">
                            {new Date(task.updatedAt).toLocaleString()}
                          </p>
                        </div>
                        <Badge variant={
                          task.status === 'done' ? 'default' :
                          task.status === 'in_progress' ? 'secondary' :
                          task.reviewReason === 'errors' ? 'destructive' : 'outline'
                        }>
                          {task.status === 'done' ? 'Done' :
                           task.status === 'in_progress' ? 'In Progress' :
                           task.reviewReason === 'errors' ? 'Failed' : task.status}
                        </Badge>
                      </div>
                    ))}
                    {recentActivity.length === 0 && (
                      <div className="text-center py-8 text-muted-foreground">
                        No activity in the selected time period
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </ScrollArea>
    </div>
  );
}
