import { useState, useMemo, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ReactFlow,
  Node,
  Edge,
  Controls,
  Background,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  NodeTypes,
  MarkerType,
  Panel,
  Handle,
  Position,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import {
  Filter,
  GitBranch,
  CircleDot,
  CheckCircle,
  Clock,
  AlertCircle,
  ArrowRight
} from 'lucide-react';
import { useTaskStore } from '../stores/task-store';
import type { Task } from '../../shared/types';
import { cn } from '../lib/utils';

interface TaskDependencyGraphProps {
  projectId: string;
}

interface TaskNodeData {
  task: Task;
  status: string;
  isBlocking?: boolean;
  isBlockedBy?: string[];
}

// Custom task node
const TaskNode = ({ data }: { data: TaskNodeData }) => {
  const { t } = useTranslation('common');
  const { task, status, isBlocking, isBlockedBy } = data;

  const statusIcons = {
    done: CheckCircle,
    in_progress: Clock,
    human_review: AlertCircle,
    backlog: CircleDot
  };

  const StatusIcon = statusIcons[status as keyof typeof statusIcons] || CircleDot;
  const statusColors = {
    done: 'text-green-500 bg-green-50 border-green-200',
    in_progress: 'text-blue-500 bg-blue-50 border-blue-200',
    human_review: 'text-yellow-500 bg-yellow-50 border-yellow-200',
    backlog: 'text-gray-500 bg-gray-50 border-gray-200'
  };

  const statusColorClass = statusColors[status as keyof typeof statusColors];

  return (
    <div className={cn(
      'p-4 rounded-lg border-2 bg-white shadow-lg min-w-[250px] max-w-[300px] relative',
      statusColorClass
    )}>
      <Handle type="target" position={Position.Left} className="!bg-gray-400" />
      <Handle type="source" position={Position.Right} className="!bg-gray-400" />
      <div className="flex items-start gap-3">
        <StatusIcon className="h-5 w-5 mt-0.5 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-sm truncate" title={task.title}>
            {task.title}
          </p>
          <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
            {task.description}
          </p>
          <div className="flex items-center gap-2 mt-2 flex-wrap">
            <Badge variant="outline" className="text-xs">
              {task.metadata?.category || t('dependencyGraph.taskNode.uncategorized')}
            </Badge>
            <Badge variant="outline" className="text-xs">
              {task.metadata?.priority || t('dependencyGraph.taskNode.normal')}
            </Badge>
          </div>
          {isBlockedBy && isBlockedBy.length > 0 && (
            <div className="mt-2 text-xs text-amber-600">
              {t('dependencyGraph.taskNode.blockedBy', { count: isBlockedBy.length })}
            </div>
          )}
          {isBlocking && (
            <div className="mt-2 text-xs text-blue-600">
              {t('dependencyGraph.taskNode.blockingOthers')}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const nodeTypes: NodeTypes = {
  task: TaskNode,
};

export function TaskDependencyGraph({ projectId }: TaskDependencyGraphProps) {
  const { t } = useTranslation('common');
  const tasks = useTaskStore((state) => state.tasks);
  
  const [nodes, setNodes, onNodesChange] = useNodesState<TaskNodeData>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [filterStatus, setFilterStatus] = useState<'all' | 'in_progress' | 'pending' | 'blocked'>('all');
  const [viewMode, setViewMode] = useState<'dependencies' | 'timeline' | 'category'>('dependencies');

  // Build dependency graph from task metadata
  const graphData = useMemo(() => {
    const taskMap = new Map(tasks.map(t => [t.id, t]));
    
    // Build nodes
    const graphNodes: Node<TaskNodeData>[] = tasks.map((task, index) => {
      // Determine if task is blocked or blocking based on subtask dependencies
      const isBlocked = task.subtasks?.some(st => st.status === 'pending');
      const isBlocking = task.status === 'in_progress' && 
        task.subtasks?.some(st => st.status === 'completed');

      return {
        id: task.id,
        type: 'task',
        position: {
          x: (index % 4) * 350,
          y: Math.floor(index / 4) * 300
        },
        data: {
          task,
          status: task.status,
          isBlocking,
          isBlockedBy: [] // Will be populated from edges
        }
      };
    });

    // Build edges based on task dependencies
    // For now, create edges based on creation order as a placeholder
    // Real dependencies would come from task.metadata.dependsOn or similar
    const graphEdges: Edge[] = [];
    
    for (let i = 1; i < tasks.length; i++) {
      const currentTask = tasks[i];
      const prevTask = tasks[i - 1];
      
      // Add edge from previous task to current
      graphEdges.push({
        id: `edge-${prevTask.id}-${currentTask.id}`,
        source: prevTask.id,
        target: currentTask.id,
        type: 'smoothstep',
        animated: prevTask.status === 'in_progress',
        style: {
          stroke: prevTask.status === 'done' ? '#22c55e' : 
                  prevTask.status === 'in_progress' ? '#3b82f6' : '#94a3b8',
          strokeWidth: 2
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 20,
          height: 20,
          color: prevTask.status === 'done' ? '#22c55e' : 
                 prevTask.status === 'in_progress' ? '#3b82f6' : '#94a3b8'
        }
      });
    }

    // Add blocking edges
    const inProgressTasks = tasks.filter(t => t.status === 'in_progress');
    inProgressTasks.forEach(inProgressTask => {
      const blockedTasks = tasks.filter(t => 
        t.status === 'backlog' && 
        new Date(t.createdAt) > new Date(inProgressTask.createdAt)
      );
      
      blockedTasks.forEach(blocked => {
        graphEdges.push({
          id: `blocking-${inProgressTask.id}-${blocked.id}`,
          source: inProgressTask.id,
          target: blocked.id,
          type: 'default',
          animated: true,
          style: {
            stroke: '#f59e0b',
            strokeWidth: 2,
            strokeDasharray: '5,5'
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: '#f59e0b'
          },
          label: 'blocking',
          labelStyle: {
            fontSize: 10,
            fontWeight: 'bold'
          }
        });
      });
    });

    return { nodes: graphNodes, edges: graphEdges };
  }, [tasks]);

  // Apply filters to nodes and edges
  const { filteredNodes, filteredEdges } = useMemo(() => {
    let visibleNodes = [...graphData.nodes];
    
    // Filter by status
    if (filterStatus !== 'all') {
      visibleNodes = visibleNodes.filter(node => {
        if (filterStatus === 'in_progress') return node.data.status === 'in_progress';
        if (filterStatus === 'pending') return node.data.status === 'backlog';
        if (filterStatus === 'blocked') return node.data.isBlockedBy && node.data.isBlockedBy.length > 0;
        return true;
      });
    }

    // Only keep edges between visible nodes
    const visibleNodeIds = new Set(visibleNodes.map(n => n.id));
    const visibleEdges = graphData.edges.filter(
      edge => visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target)
    );

    return { filteredNodes: visibleNodes, filteredEdges: visibleEdges };
  }, [graphData, filterStatus]);

  // Update nodes and edges when filtered data changes
  useEffect(() => {
    setNodes(filteredNodes);
    setEdges(filteredEdges);
  }, [filteredNodes, filteredEdges, setNodes, setEdges]);

  // Handle edge connections
  const onConnect = useCallback((connection: Connection) => {
    setEdges((eds) => addEdge({
      ...connection,
      type: 'smoothstep',
      animated: true
    }, eds));
  }, [setEdges]);

  // Calculate statistics
  const stats = useMemo(() => {
    const completed = tasks.filter(t => t.status === 'done').length;
    const inProgress = tasks.filter(t => t.status === 'in_progress').length;
    const pending = tasks.filter(t => t.status === 'backlog').length;
    const blocked = tasks.filter(t => 
      t.status === 'backlog' && 
      inProgress > 0
    ).length;

    return { completed, inProgress, pending, blocked };
  }, [tasks]);

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border">
        <div>
          <h2 className="text-lg font-semibold">{t('dependencyGraph.title')}</h2>
          <p className="text-sm text-muted-foreground">
            {t('dependencyGraph.description')}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={filterStatus} onValueChange={(v: typeof filterStatus) => setFilterStatus(v)}>
            <SelectTrigger className="w-[150px]">
              <Filter className="h-4 w-4 mr-2" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('dependencyGraph.filters.all')}</SelectItem>
              <SelectItem value="in_progress">{t('dependencyGraph.filters.inProgress')}</SelectItem>
              <SelectItem value="pending">{t('dependencyGraph.filters.pending')}</SelectItem>
              <SelectItem value="blocked">{t('dependencyGraph.filters.blocked')}</SelectItem>
            </SelectContent>
          </Select>
          <Select value={viewMode} onValueChange={(v: typeof viewMode) => setViewMode(v)}>
            <SelectTrigger className="w-[150px]">
              <GitBranch className="h-4 w-4 mr-2" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="dependencies">{t('dependencyGraph.viewModes.dependencies')}</SelectItem>
              <SelectItem value="timeline">{t('dependencyGraph.viewModes.timeline')}</SelectItem>
              <SelectItem value="category">{t('dependencyGraph.viewModes.category')}</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 relative">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          nodeTypes={nodeTypes}
          fitView
          attributionPosition="bottom-left"
        >
          <Controls />
          <MiniMap 
            nodeColor={(node) => {
              if (node.data.status === 'done') return '#22c55e';
              if (node.data.status === 'in_progress') return '#3b82f6';
              if (node.data.status === 'human_review') return '#f59e0b';
              return '#94a3b8';
            }}
          />
          <Background color="#94a3b8" gap={16} />

          {/* Statistics Panel */}
          <Panel position="top-left" className="w-64">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">{t('dependencyGraph.stats.title')}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">{t('dependencyGraph.stats.completed')}</span>
                  <Badge className="bg-green-100 text-green-700">
                    <CheckCircle className="h-3 w-3 mr-1" />
                    {stats.completed}
                  </Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">{t('dependencyGraph.stats.inProgress')}</span>
                  <Badge className="bg-blue-100 text-blue-700">
                    <Clock className="h-3 w-3 mr-1" />
                    {stats.inProgress}
                  </Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">{t('dependencyGraph.stats.pending')}</span>
                  <Badge className="bg-gray-100 text-gray-700">
                    <CircleDot className="h-3 w-3 mr-1" />
                    {stats.pending}
                  </Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">{t('dependencyGraph.stats.blocked')}</span>
                  <Badge className="bg-amber-100 text-amber-700">
                    <AlertCircle className="h-3 w-3 mr-1" />
                    {stats.blocked}
                  </Badge>
                </div>
              </CardContent>
            </Card>
          </Panel>

          {/* Legend Panel */}
          <Panel position="top-right" className="w-64">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">{t('dependencyGraph.legend.title')}</CardTitle>
                <CardDescription className="text-xs">{t('dependencyGraph.legend.description')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-green-500" />
                  <span className="text-xs">{t('dependencyGraph.legend.completed')}</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-blue-500" />
                  <span className="text-xs">{t('dependencyGraph.legend.inProgress')}</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-amber-500" />
                  <span className="text-xs">{t('dependencyGraph.legend.review')}</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-gray-400" />
                  <span className="text-xs">{t('dependencyGraph.legend.pending')}</span>
                </div>
                <div className="h-px bg-border my-2" />
                <div className="flex items-center gap-2">
                  <ArrowRight className="h-3 w-3 text-green-500" />
                  <span className="text-xs">{t('dependencyGraph.legend.completedDependency')}</span>
                </div>
                <div className="flex items-center gap-2">
                  <ArrowRight className="h-3 w-3 text-blue-500" />
                  <span className="text-xs">{t('dependencyGraph.legend.activeDependency')}</span>
                </div>
                <div className="flex items-center gap-2">
                  <ArrowRight className="h-3 w-3 text-amber-500" />
                  <span className="text-xs">{t('dependencyGraph.legend.blockingRelationship')}</span>
                </div>
              </CardContent>
            </Card>
          </Panel>
        </ReactFlow>
      </div>
    </div>
  );
}
