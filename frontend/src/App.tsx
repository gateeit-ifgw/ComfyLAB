/*
 * Copyright (C) 2026 Paulo Felipe Jarschel
 * 
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import {
  ReactFlow,
  ReactFlowProvider,
  Controls,
  ControlButton,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  MarkerType,
  MiniMap,
  useViewport,
} from '@xyflow/react';
import type { Connection, Edge, Node } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import axios from 'axios';
import { ActionBlock } from './components/ActionBlock';
import { getPinColor } from './constants/blockLayouts';
import { TooltipEdge } from './components/common/TooltipEdge';
import { ScriptEditorPanel } from './components/ScriptEditorPanel';
import { LibrarySignatureEditorPanel } from './components/LibrarySignatureEditorPanel';
import { CreateClusterModal } from './components/CreateClusterModal';
import { BreadcrumbBar } from './components/BreadcrumbBar';
import { BlockInspectorPanel } from './components/BlockInspectorPanel';
import { TopBar } from './components/TopBar';
import { TabBar } from './components/TabBar';
import { Sidebar } from './components/Sidebar';
import { getBlockTitle, getBlockDescription, getBlockCategory } from './utils/blockI18n';
import './App.css';
import dagre from '@dagrejs/dagre';

import { RegistryContext } from './context/RegistryContext';
import { SettingsContext } from './context/SettingsContext';
import { useTranslation } from './i18n';
import { RemoteAccessAuthPanel } from './components/modals/RemoteAccessAuthPanel';
import { GlobalSettingsModal } from './components/modals/GlobalSettingsModal';
import { SaveWorkspaceModal } from './components/modals/SaveWorkspaceModal';
import { LoadWorkspaceModal } from './components/modals/LoadWorkspaceModal';
import { TrustWarningModal } from './components/modals/TrustWarningModal';
import { PackageImportModal } from './components/modals/PackageImportModal';
import { CanvasContextMenu } from './components/modals/CanvasContextMenu';
import { UploadFileModal } from './components/modals/UploadFileModal';
import { ConfirmModal } from './components/modals/ConfirmModal';
import { AlertModal } from './components/modals/AlertModal';
import { AboutModal } from './components/modals/AboutModal';
import { StoreModal } from './components/modals/StoreModal';
import { QuickStartModal } from './components/modals/QuickStartModal';
import { SplashScreenModal } from './components/modals/SplashScreenModal';
import { LoadExampleModal } from './components/modals/LoadExampleModal';
import { WhiteboardOverlay } from './components/widgets/WhiteboardOverlay';
import { WhiteboardSidebar } from './components/widgets/WhiteboardSidebar';
import { useWorkspaceHistory } from './hooks/useWorkspaceHistory';
import { useWhiteboardState } from './hooks/useWhiteboardState';
import { useFlowExecution } from './hooks/useFlowExecution';
import { useResizable } from './hooks/useResizable';
import { DashboardPanel } from './components/DashboardPanel';
import type { DashboardItem } from './components/widgets/DashboardCard';

interface Tab {
  id: string;
  name: string;
  blocks: Node[];
  edges: Edge[];
  annotations: any[];
  isDirty: boolean;
  past: { blocks: any[]; edges: any[]; annotations: any[] }[];
  future: { blocks: any[]; edges: any[]; annotations: any[] }[];
  canvasStack: { breadcrumbLabel: string; type: string; savedNodes?: any[]; savedEdges?: any[]; savedAnnotations?: any[] }[];
  currentLevelIndex: number;
  viewport?: { x: number; y: number; zoom: number };
  dashboard?: { items: DashboardItem[]; width?: number };
}


const blockTypes: any = {
  actionNode: ActionBlock,
};

const edgeTypes: any = {
  default: TooltipEdge,
};

let id = 0;
const getId = () => `block_${Date.now()}_${id++}`;

const lineSegmentsIntersect = (
  p1: { x: number; y: number },
  p2: { x: number; y: number },
  p3: { x: number; y: number },
  p4: { x: number; y: number }
): boolean => {
  const ccw = (a: { x: number; y: number }, b: { x: number; y: number }, c: { x: number; y: number }) => {
    return (c.y - a.y) * (b.x - a.x) > (b.y - a.y) * (c.x - a.x);
  };
  return ccw(p1, p3, p4) !== ccw(p2, p3, p4) && ccw(p1, p2, p3) !== ccw(p1, p2, p4);
};

export const getBackendUrls = () => {
  const hostname = window.location.hostname;
  let port = window.location.port;
  
  // In development mode (Vite dev server), read backend_port.json if present
  if (import.meta.env.DEV) {
    try {
      const xhr = new XMLHttpRequest();
      xhr.open('GET', '/backend_port.json', false); // synchronous request
      xhr.send(null);
      if (xhr.status === 200) {
        const data = JSON.parse(xhr.responseText);
        if (data.port) {
          port = data.port.toString();
        } else {
          port = '8000';
        }
      } else {
        port = '8000';
      }
    } catch (e) {
      port = '8000';
    }
  }
  
  const protocol = window.location.protocol;
  const wsProtocol = protocol === 'https:' ? 'wss:' : 'ws:';
  return {
    http: `${protocol}//${hostname}${port ? `:${port}` : ''}`,
    ws: `${wsProtocol}//${hostname}${port ? `:${port}` : ''}`
  };
};

const urls = getBackendUrls();
const BACKEND_URL = urls.http;
const WS_BACKEND_URL = urls.ws;



import type { SidebarCategoryNode } from './components/Sidebar';

const rewriteEdgeStyles = (eds: any[]) => {
  return eds.map((edge: any) => {
    if (edge.style && (edge.style.stroke === '#ffffff' || edge.style.stroke === '#e2e8f0' || edge.style.stroke === '#f8fafc')) {
      return {
        ...edge,
        style: {
          ...edge.style,
          stroke: '#64748b'
        },
        markerEnd: edge.markerEnd && (edge.markerEnd.color === '#ffffff' || edge.markerEnd.color === '#e2e8f0' || edge.markerEnd.color === '#f8fafc')
          ? { ...edge.markerEnd, color: '#64748b' }
          : edge.markerEnd
      };
    }
    return edge;
  });
};

const getResolvedEdgeColor = (
  sourceId: string,
  sourceHandle: string,
  blocks: any[],
  edges: any[],
  blockRegistry: any,
  visited = new Set<string>()
): string => {
  if (visited.has(sourceId)) {
    return '#64748b';
  }
  visited.add(sourceId);

  const sourceBlock = blocks.find(n => n.id === sourceId);
  if (!sourceBlock) return '#64748b';

  const action = sourceBlock.data?.action;
  if (!action) return '#64748b';

  const layout = blockRegistry?.[action];
  if (layout?.isPassthrough) {
    const incomingEdge = edges.find(e => e.target === sourceId && e.targetHandle === 'In');
    if (incomingEdge) {
      return getResolvedEdgeColor(incomingEdge.source, incomingEdge.sourceHandle || '', blocks, edges, blockRegistry, visited);
    }
    return '#64748b';
  }

  if (action === 'cluster/boundary/input') {
    const dataType = sourceBlock.data?.DataType || 'any';
    return getPinColor(dataType);
  }

  if (action && action.startsWith('script/')) {
    const pin = (sourceBlock.data?.customOutputs || []).find((p: any) => p.name === sourceHandle);
    if (pin) return getPinColor(pin.type);
  } else {
    const layout = blockRegistry?.[action];
    if (layout) {
      if (layout.execOuts?.includes(sourceHandle)) {
        return '#a78bfa';
      }
      const pin = layout.dataOuts?.find((p: any) => p.name === sourceHandle);
      if (pin) return getPinColor(pin.type);
    }
  }

  return '#64748b';
};

// Detect boundary pins for a selection of blocks
function detectBoundaryPins(
  selectedBlockIds: Set<string>,
  blocks: any[],
  edges: any[],
  blockRegistry: any
) {
  const exec_ins: any[] = [];
  const exec_outs: any[] = [];
  const data_ins: any[] = [];
  const data_outs: any[] = [];

  for (const edge of edges) {
    const sourceInside = selectedBlockIds.has(edge.source);
    const targetInside = selectedBlockIds.has(edge.target);
    
    if (sourceInside && !targetInside) {
      const sourceBlock = blocks.find((n: any) => n.id === edge.source);
      const layout = blockRegistry?.[sourceBlock?.data?.action || ''];
      const isExec = layout?.execOuts?.includes(edge.sourceHandle || '') || false;
      
      if (isExec) {
        exec_outs.push({
          name: edge.sourceHandle || 'Out',
          label: edge.sourceHandle || 'Out',
          type: 'exec',
          maps_from: { block_id: edge.source, pin: edge.sourceHandle || '' }
        });
      } else {
        const pinInfo = layout?.dataOuts?.find((p: any) => p.name === edge.sourceHandle);
        data_outs.push({
          name: edge.sourceHandle || 'Out',
          label: edge.sourceHandle || 'Out',
          type: pinInfo?.type || 'any',
          maps_from: { block_id: edge.source, pin: edge.sourceHandle || '' }
        });
      }
    }
    
    if (targetInside && !sourceInside) {
      const targetBlock = blocks.find((n: any) => n.id === edge.target);
      const layout = blockRegistry?.[targetBlock?.data?.action || ''];
      const isExec = layout?.execIns?.includes(edge.targetHandle || '') || false;
      
      if (isExec) {
        exec_ins.push({
          name: edge.targetHandle || 'In',
          label: edge.targetHandle || 'In',
          type: 'exec',
          maps_to: { block_id: edge.target, pin: edge.targetHandle || '' }
        });
      } else {
        const pinInfo = layout?.dataIns?.find((p: any) => p.name === edge.targetHandle);
        data_ins.push({
          name: edge.targetHandle || 'In',
          label: edge.targetHandle || 'In',
          type: pinInfo?.type || 'any',
          widget: pinInfo?.widget,
          default: pinInfo?.defaultVal,
          min: pinInfo?.min,
          max: pinInfo?.max,
          step: pinInfo?.step,
          options: pinInfo?.options,
          optional: pinInfo?.optional || false,
          maps_to: { block_id: edge.target, pin: edge.targetHandle || '' }
        });
      }
    }
  }

  return { exec_ins, exec_outs, data_ins, data_outs };
}

// Helper to extract clean alphanumeric tokens from strings
const extractSearchTokens = (text: string): string[] => {
  if (!text) return [];
  return text
    .toLowerCase()
    .split(/[^a-z0-9]+/g)
    .filter(t => t.length >= 2);
};

const isBlockMatchingConnectedDevices = (nodeSchema: any, discoveredDevices: any[]): boolean => {
  if (!discoveredDevices || discoveredDevices.length === 0) {
    return false;
  }

  const blockText = [
    nodeSchema.type || '',
    nodeSchema.name || '',
    nodeSchema.display_name || '',
    nodeSchema.category || '',
    nodeSchema.description || '',
    ...(nodeSchema.dataIns || []).map((p: any) => (p.defaultVal !== undefined ? String(p.defaultVal) : ''))
  ].join(' ').toLowerCase();

  const blockTokens = extractSearchTokens(blockText);
  if (blockTokens.length === 0) return false;

  for (const dev of discoveredDevices) {
    const devAddr = (dev.address || '').toLowerCase();
    if (devAddr && blockText.includes(devAddr)) {
      return true;
    }

    const modelTokens = extractSearchTokens(dev.model || dev.idn || '');
    const vendorTokens = extractSearchTokens(dev.vendor || '');

    const hasModelMatch = modelTokens.some(tok => {
      if (tok.length < 3) return false;
      return blockTokens.some(btok => btok.includes(tok) || tok.includes(btok));
    });

    const hasVendorMatch = vendorTokens.some(tok => {
      if (tok.length < 3) return false;
      return blockTokens.some(btok => btok.includes(tok) || tok.includes(btok));
    });

    if (hasModelMatch || (hasVendorMatch && modelTokens.length === 0)) {
      return true;
    }
  }

  return false;
};

const pruneEmptyCategories = (tree: Record<string, SidebarCategoryNode>) => {
  Object.keys(tree).forEach(key => {
    const node = tree[key];
    if (node.children) {
      pruneEmptyCategories(node.children);
    }
    const hasChildren = Object.keys(node.children || {}).length > 0;
    const hasDirect = (node.directNodes || []).length > 0;
    if (!hasChildren && !hasDirect) {
      delete tree[key];
    }
  });
};

function Flow() {
  const { t } = useTranslation();
  const [quickConnectMenu, setQuickConnectMenu] = useState<{
    show: boolean;
    clientX: number;
    clientY: number;
    offsetX: number;
    offsetY: number;
    sourceBlockId: string;
    sourceHandleId: string;
    sourceHandleType: string;
  } | null>(null);

  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const [blocks, setBlocks, reactFlowOnBlocksChange] = useNodesState<any>([]);
  const [edges, setEdges, reactFlowOnEdgesChange] = useEdgesState<any>([]);
  const [snapPreviewEdges, setSnapPreviewEdges] = useState<any[]>([]);
  const snapTargetRef = useRef<{ targetId: string; previews: any[] } | null>(null);
  const snapPreviewRef = useRef<any[]>([]);
  const snapRafRef = useRef<number | null>(null);
  const blocksRef = useRef<any[]>([]);
  const edgesRef = useRef<any[]>([]);
  blocksRef.current = blocks;
  edgesRef.current = edges;
  const [reactFlowInstance, setReactFlowInstance] = useState<any>(null);

  // Flow execution states
  const [isRunning, setIsRunning] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [runningTabId, setRunningTabId] = useState<string | null>(null);

  const [blockRegistry, setBlockRegistry] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [workspacePath, setWorkspacePath] = useState<string>('');
  const [editingWorkspace, setEditingWorkspace] = useState(false);
  const [workspaceInput, setWorkspaceInput] = useState('');

  const [activeScriptBlock, setActiveScriptBlock] = useState<{ id: string; code: string; actionType: string } | null>(null);
  const [activeLibraryBlockId, setActiveLibraryBlockId] = useState<string | null>(null);

  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [inspectedBlockId, setInspectedBlockId] = useState<string | null>(null);

  // Resizable sidebars & panels
  const sidebarResizer = useResizable({
    direction: 'left',
    defaultWidth: 320,
    minWidth: 250,
    maxWidth: 700,
    storageKey: 'comfylab_sidebar_width',
  });

  const inspectorResizer = useResizable({
    direction: 'right',
    defaultWidth: 320,
    minWidth: 260,
    maxWidth: 700,
    storageKey: 'comfylab_inspector_width',
  });

  const dashboardResizer = useResizable({
    direction: 'right',
    defaultWidth: 440,
    minWidth: 320,
    maxWidth: 850,
    storageKey: 'comfylab_dashboard_width',
  });

  // Dashboard state
  const [dashboardOpen, setDashboardOpen] = useState(false);
  const [dashboardMaximized, setDashboardMaximized] = useState(false);
  const [dashboardItems, setDashboardItems] = useState<DashboardItem[]>([]);
  const dashboardItemsRef = useRef<DashboardItem[]>([]);
  dashboardItemsRef.current = dashboardItems;

  const [searchQuery, setSearchQuery] = useState('');

  const [connectedDevices, setConnectedDevices] = useState<any[]>([]);
  const [isScanningVisa, setIsScanningVisa] = useState(false);
  const [connectedOnly, setConnectedOnly] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuContainerRef = useRef<HTMLDivElement>(null);
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    return (localStorage.getItem('comfylab-theme') as 'dark' | 'light') || 'dark';
  });
  const [liteMode, setLiteMode] = useState<boolean>(() => {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('lite') === '1' || urlParams.get('lite') === 'true') {
      return true;
    }
    return localStorage.getItem('comfylab-lite-mode') === 'true';
  });
  const [isLocked, setIsLocked] = useState(false);

  // Cluster state
  const [createClusterOpen, setCreateClusterOpen] = useState(false);
  const [detectedBoundary, setDetectedBoundary] = useState<any>(null);
  const [selectedForCluster, setSelectedForCluster] = useState<string[]>([]);
  const [selectedBlockIds, setSelectedBlockIds] = useState<Set<string>>(new Set());

  // Save/Load names
  const [currentBlueprintName, setCurrentBlueprintName] = useState<string>('');

  // Tab states and dirty tracking
  const [isDirty, setIsDirty] = useState(false);
  const [tabs, setTabs] = useState<Tab[]>([]);
  const [activeTabId, setActiveTabId] = useState<string>('');
  const [initialRunningInfo, setInitialRunningInfo] = useState<{ state: string; runId: string; rawCanvas: any } | null>(null);

  const activeTabIdRef = useRef(activeTabId);
  const runningTabIdRef = useRef(runningTabId);
  const tabsRef = useRef<Tab[]>(tabs);

  useEffect(() => {
    tabsRef.current = tabs;
  }, [tabs]);

  useEffect(() => {
    activeTabIdRef.current = activeTabId;
  }, [activeTabId]);

  useEffect(() => {
    runningTabIdRef.current = runningTabId;
  }, [runningTabId]);

  // Breadcrumb navigation state (Phase C)
  const [canvasStack, setCanvasStack] = useState<{ breadcrumbLabel: string; type: string; savedNodes?: any[]; savedEdges?: any[]; savedAnnotations?: any[] }[]>([]);
  const [currentLevelIndex, setCurrentLevelIndex] = useState(0);
  const canvasStackRef = useRef<any[]>([]);
  const currentLevelIndexRef = useRef<number>(0);
  canvasStackRef.current = canvasStack;
  currentLevelIndexRef.current = currentLevelIndex;
  const [shouldFitView, setShouldFitView] = useState(false);
  const [canvasMode, setCanvasMode] = useState<'select' | 'pan' | 'cut' | 'draw'>('select');
  const [snapToGrid, setSnapToGrid] = useState<boolean>(() => {
    return localStorage.getItem('comfylab-snap-to-grid') === 'true';
  });

  // Context Menu state
  const [contextMenu, setContextMenu] = useState<{
    show: boolean;
    x: number;
    y: number;
    clientX: number;
    clientY: number;
    type: 'pane' | 'block' | 'edge' | 'selection';
    targetId?: string | null;
  } | null>(null);
  const [contextMenuSearch, setContextMenuSearch] = useState('');

  // Slicer Tool state
  const [cutterPath, setCutterPath] = useState<{ x: number; y: number }[] | null>(null);
  const [isCutting, setIsCutting] = useState(false);



  // Annotations & Whiteboard state variables (synced to hooks)
  const [annotations, setAnnotations] = useState<any[]>([]);
  const [showAnnotations, setShowAnnotations] = useState(true);

  // Viewport scale & offsets
  const viewport = useViewport();

  // Create references for callbacks
  const annotationsRef = useRef<any[]>([]);
  useEffect(() => {
    annotationsRef.current = annotations;
  }, [annotations]);

  const pastRef = useRef<any[]>([]);
  const futureRef = useRef<any[]>([]);

  // Global Settings States
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settings, setSettings] = useState<{
    custom_block_dirs: string[];
    script_timeout: number;
    visa_backend: string;
    last_workspace: string;
    enable_lua_scripting: boolean;
    enable_julia_scripting: boolean;
    enable_js_scripting: boolean;
    enable_rust_scripting: boolean;
    enable_r_scripting: boolean;
    enable_octave_scripting: boolean;
    enable_wolfram_scripting: boolean;
    enable_sage_scripting: boolean;
    enable_maxima_scripting: boolean;
    enable_powershell_scripting: boolean;
    enable_csharp_scripting: boolean;
    external_python_path: string;
    creator_identity: string;
    trusted_origins: string[];
    plot_downsample_threshold: number;
    plot_downsample_target: number;
    custom_users: Record<string, string>;
  }>({
    custom_block_dirs: [],
    script_timeout: 30,
    visa_backend: '@py',
    last_workspace: '',
    enable_lua_scripting: false,
    enable_julia_scripting: false,
    enable_js_scripting: false,
    enable_rust_scripting: false,
    enable_r_scripting: false,
    enable_octave_scripting: false,
    enable_wolfram_scripting: false,
    enable_sage_scripting: false,
    enable_maxima_scripting: false,
    enable_powershell_scripting: false,
    enable_csharp_scripting: false,
    external_python_path: '',
    creator_identity: '',
    trusted_origins: [],
    plot_downsample_threshold: 10000,
    plot_downsample_target: 2000,
    custom_users: {}
  });
  const [newDirInput, setNewDirInput] = useState('');
  const [settingsTab, setSettingsTab] = useState<'general' | 'diagnostics'>('general');
  const [diagnosticsData, setDiagnosticsData] = useState<any>(null);
  const [loadingDiagnostics, setLoadingDiagnostics] = useState(false);
  const [isRestartingServer, setIsRestartingServer] = useState(false);

  // Splash Screen, Example, About & Quick Start Modal States
  const [aboutModalOpen, setAboutModalOpen] = useState(false);
  const [quickStartModalOpen, setQuickStartModalOpen] = useState(false);
  const [loadExampleOpen, setLoadExampleOpen] = useState(false);
  const [isExampleBlueprint, setIsExampleBlueprint] = useState(false);
  const [splashOpen, setSplashOpen] = useState<boolean>(() => {
    return localStorage.getItem('comfylab_hide_splash') !== 'true';
  });

  // Software Update Notification States
  const [updateInfo, setUpdateInfo] = useState<any>(null);

  const fetchUpdateInfo = useCallback(async (force = false) => {
    try {
      const res = await axios.get(`${BACKEND_URL}/updates/check${force ? '?force=true' : ''}`);
      if (res.data && res.data.status === 'success') {
        setUpdateInfo(res.data);
        return res.data;
      }
    } catch (err) {
      console.debug('Update check skipped or failed:', err);
    }
    return null;
  }, [BACKEND_URL]);

  useEffect(() => {
    fetchUpdateInfo(false);
  }, [fetchUpdateInfo]);

  // ComfyLAB Store Modal & Badge States
  const [storeModalOpen, setStoreModalOpen] = useState(false);
  const [storeBadgeCount, setStoreBadgeCount] = useState(0);

  const fetchStoreBadge = useCallback(async () => {
    try {
      const res = await axios.get(`${BACKEND_URL}/store/badge`);
      if (res.data && typeof res.data.total_badge_count === 'number') {
        setStoreBadgeCount(res.data.total_badge_count);
      }
    } catch (err) {
      console.debug('Failed to fetch store badge:', err);
    }
  }, [BACKEND_URL]);

  useEffect(() => {
    fetchStoreBadge();
    const interval = setInterval(fetchStoreBadge, 120000); // Poll badge every 2 minutes
    return () => clearInterval(interval);
  }, [fetchStoreBadge]);

  // Trust Warning Modal States
  const [trustWarningOpen, setTrustWarningOpen] = useState(false);
  const [trustWarningMessage, setTrustWarningMessage] = useState("");
  const [pendingBlueprint, setPendingBlueprint] = useState<any>(null);
  const [pendingFilename, setPendingFilename] = useState("");

  // Remote Access Authentication States
  const [_authToken, setAuthToken] = useState<string>(localStorage.getItem("comfylab-auth-token") || "");
  const [authRequired, setAuthRequired] = useState<boolean>(false);
  const [authInput, setAuthInput] = useState<string>("");
  const [authError, setAuthError] = useState<string>("");

  const handleAuthSubmit = async () => {
    const val = authInput.trim();
    if (!val) return;
    try {
      const headers = { 'X-ComfyLAB-Auth': val };
      await axios.get(`${BACKEND_URL}/status`, { headers });
      localStorage.setItem("comfylab-auth-token", val);
      setAuthToken(val);
      axios.defaults.headers.common['X-ComfyLAB-Auth'] = val;
      setAuthRequired(false);
      setAuthError("");
      await fetchRegistry();
      
      const wsRes = await axios.get(`${BACKEND_URL}/workspace`);
      if (wsRes.data.path) {
        setWorkspacePath(wsRes.data.path);
      }
    } catch (err: any) {
      if (err.response) {
        const detail = err.response.data?.detail;
        if (detail) {
          setAuthError(detail);
        } else if (err.response.status === 429) {
          setAuthError("Too many failed attempts. Try again later.");
        } else {
          setAuthError("Authentication failed: Invalid access token or username:password.");
        }
      } else {
        setAuthError("Connection failed: Unable to reach the server.");
      }
      setAuthRequired(true);
    }
  };

  // Remote access verification on load
  useEffect(() => {
    const isRemote = window.location.hostname !== 'localhost' && 
                     window.location.hostname !== '127.0.0.1' && 
                     window.location.hostname !== '[::1]';
    if (isRemote) {
      const savedToken = localStorage.getItem("comfylab-auth-token");
      if (!savedToken) {
        setAuthRequired(true);
      } else {
        axios.defaults.headers.common['X-ComfyLAB-Auth'] = savedToken;
      }
    }
  }, []);

  // Axios interceptor for auth error handling (401, 429)
  useEffect(() => {
    const interceptor = axios.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response) {
          if (error.response.status === 429) {
            setErrorMessage(error.response.data?.detail || "Too many failed attempts. Try again later.");
          } else if (error.response.status === 401) {
            localStorage.removeItem("comfylab-auth-token");
            setAuthToken("");
            setAuthRequired(true);
          }
        }
        return Promise.reject(error);
      }
    );
    return () => {
      axios.interceptors.response.eject(interceptor);
    };
  }, []);

  const fetchDiagnostics = useCallback(async () => {
    setLoadingDiagnostics(true);
    try {
      const res = await axios.get(`${BACKEND_URL}/diagnostics/check`);
      setDiagnosticsData(res.data);
    } catch (err) {
      console.error('Failed to run toolchain diagnostics:', err);
    } finally {
      setLoadingDiagnostics(false);
    }
  }, []);

  useEffect(() => {
    if (settingsOpen) {
      fetchDiagnostics();
    }
  }, [settingsOpen, fetchDiagnostics]);

  // Workspace Blueprints & Packages States
  const [saveWorkspaceOpen, setSaveWorkspaceOpen] = useState(false);
  const [loadWorkspaceOpen, setLoadWorkspaceOpen] = useState(false);
  const [workspaceBlueprints, setWorkspaceBlueprints] = useState<{ filename: string; path: string; isPackage?: boolean }[]>([]);
  const [saveFilenameInput, setSaveFilenameInput] = useState('');
  const [exportAsPackage, setExportAsPackage] = useState(false);

  // Package Import States
  const [packageImportOpen, setPackageImportOpen] = useState(false);
  const [packageFilename, setPackageFilename] = useState('');
  const [packagePreviewData, setPackagePreviewData] = useState<any>(null);
  const [uploadFileOpen, setUploadFileOpen] = useState(false);

  // Custom Confirm Modal State
  const [confirmDialog, setConfirmDialog] = useState<{
    message: string;
    onConfirm: () => void;
    onCancel: () => void;
  } | null>(null);

  const confirmAsync = useCallback((message: string): Promise<boolean> => {
    return new Promise((resolve) => {
      setConfirmDialog({
        message,
        onConfirm: () => {
          setConfirmDialog(null);
          resolve(true);
        },
        onCancel: () => {
          setConfirmDialog(null);
          resolve(false);
        }
      });
    });
  }, []);

  // Custom Alert Modal State
  const [alertDialog, setAlertDialog] = useState<{
    title?: string;
    message: string;
    onClose: () => void;
  } | null>(null);

  const alertAsync = useCallback((message: string, title?: string): Promise<void> => {
    return new Promise((resolve) => {
      setAlertDialog({
        title,
        message,
        onClose: () => {
          setAlertDialog(null);
          resolve();
        }
      });
    });
  }, []);
  const [importDestination, setImportDestination] = useState<'workspace' | 'user'>('workspace');
  const [trustAndSign, setTrustAndSign] = useState(true);
  const [deletePackageAfterImport, setDeletePackageAfterImport] = useState(true);
  const [importPermanent, setImportPermanent] = useState(false);
  const [unauthorizedBlocksCount, setUnauthorizedNodesCount] = useState(0);


  const onEditScript = useCallback((id: string, code: string, actionType: string) => {
    setActiveScriptBlock({ id, code, actionType });
  }, []);

  const onEditLibrarySignature = useCallback((id: string) => {
    setActiveLibraryBlockId(id);
  }, []);



  const fetchSettings = useCallback(async () => {
    try {
      const res = await axios.get(`${BACKEND_URL}/settings`);
      setSettings(res.data);
      return res.data;
    } catch (err) {
      console.error('Failed to load settings:', err);
    }
  }, []);

  const fetchRegistry = useCallback(async () => {
    try {
      const res = await axios.get(`${BACKEND_URL}/blocks`);
      setBlockRegistry(res.data);
    } catch (err) {
      console.error('Failed to load ComfyLAB block templates:', err);
      setErrorMessage('Failed to load block templates from backend.');
    }
  }, []);

  const scanConnectedDevices = useCallback(async () => {
    setIsScanningVisa(true);
    try {
      const res = await axios.get(`${BACKEND_URL}/blocks/visa/scan`);
      if (res.data && Array.isArray(res.data.devices)) {
        setConnectedDevices(res.data.devices);
      }
    } catch (err) {
      console.error('Failed to scan VISA devices:', err);
    } finally {
      setIsScanningVisa(false);
    }
  }, []);

  const handleReloadRegistry = useCallback(async () => {
    try {
      const res = await axios.post(`${BACKEND_URL}/blocks/reload`);
      setBlockRegistry(res.data);
      scanConnectedDevices();
    } catch (err) {
      console.error('Failed to reload block registry:', err);
    }
  }, [scanConnectedDevices]);

  const fetchUnauthorizedNodes = useCallback(async () => {
    try {
      const res = await axios.get(`${BACKEND_URL}/workspace/blocks/unauthorized`);
      setUnauthorizedNodesCount((res.data.unauthorized || []).length);
    } catch (err) {
      console.error("Failed to fetch unauthorized blocks:", err);
    }
  }, []);

  const handleAuthorizeAllNodes = async () => {
    try {
      await axios.post(`${BACKEND_URL}/workspace/blocks/authorize`, { all: true });
      await fetchUnauthorizedNodes();
      // Reload blocks to reload registry definitions!
      await axios.post(`${BACKEND_URL}/blocks/reload`);
      // Re-fetch templates/blocks schema to update sidebar list
      const templatesRes = await axios.get(`${BACKEND_URL}/blocks`);
      setBlockRegistry(templatesRes.data);
    } catch (err) {
      console.error("Failed to authorize blocks:", err);
      await alertAsync(t('app.alertFailedAuthorize', "Failed to authorize blocks."));
    }
  };

  const fetchWorkspaceBlueprints = useCallback(async () => {
    try {
      const bpRes = await axios.get(`${BACKEND_URL}/workspace/blueprints`);
      const pkgRes = await axios.get(`${BACKEND_URL}/workspace/packages`);
      
      const bps = (bpRes.data.blueprints || []).map((bp: any) => ({ ...bp, isPackage: false }));
      const pkgs = (pkgRes.data.packages || []).map((pkg: any) => ({ ...pkg, isPackage: true }));
      
      setWorkspaceBlueprints([...bps, ...pkgs]);
      await fetchUnauthorizedNodes();
    } catch (err) {
      console.error('Failed to load files from workspace:', err);
    }
  }, [fetchUnauthorizedNodes]);

  // Fetch settings, restore workspace path, and load dynamic block registry at startup
  useEffect(() => {
    const initialize = async () => {
      setLoading(true);
      try {
        // Don't make API calls if remote and no token yet — wait for auth
        const savedToken = localStorage.getItem("comfylab-auth-token");
        const isRemote = window.location.hostname !== 'localhost' &&
                         window.location.hostname !== '127.0.0.1' &&
                         window.location.hostname !== '[::1]';
        if (isRemote && !savedToken) {
          setLoading(false);
          return;
        }

        const configData = await fetchSettings();
        
        let activeWorkspace = '';
        if (configData && configData.last_workspace) {
          activeWorkspace = configData.last_workspace;
        }

        const wsRes = await axios.get(`${BACKEND_URL}/workspace`);
        if (wsRes.data.path) {
          activeWorkspace = wsRes.data.path;
        }

        if (activeWorkspace) {
          try {
            const res = await axios.post(`${BACKEND_URL}/workspace`, { path: activeWorkspace });
            setWorkspacePath(res.data.path);
          } catch (err) {
            console.error('Failed to initialize workspace:', err);
          }
        }

        await fetchRegistry();
        await fetchUnauthorizedNodes();
        await fetchWorkspaceBlueprints();

        // Check for active background execution
        try {
          const statusRes = await axios.get(`${BACKEND_URL}/status`);
          if ((statusRes.data.state === 'RUNNING' || statusRes.data.state === 'PAUSED') && statusRes.data.raw_canvas) {
            setInitialRunningInfo({
              state: statusRes.data.state,
              runId: statusRes.data.run_id,
              rawCanvas: statusRes.data.raw_canvas
            });
          }
        } catch (err) {
          console.error('Failed to fetch running status:', err);
        }
      } catch (err) {
        console.error('Error during startup initialization:', err);
      } finally {
        setLoading(false);
      }
    };
    initialize();
  }, [fetchSettings, fetchRegistry, fetchUnauthorizedNodes, fetchWorkspaceBlueprints]);


  // Initialize the canvas stack at startup
  useEffect(() => {
    if (canvasStack.length === 0 && !loading) {
      setCanvasStack([{
        breadcrumbLabel: 'Main',
        type: 'main',
      }]);
    }
  }, [loading, canvasStack.length]);

  // Initialize tabs system at startup (when loading is done)
  useEffect(() => {
    if (!loading && tabs.length === 0) {
      const initialTabId = `tab_${Date.now()}`;
      const defaultViewport = { x: 50, y: 50, zoom: 0.9 };
      if (initialRunningInfo && initialRunningInfo.rawCanvas) {
        const newTab: Tab = {
          id: initialTabId,
          name: initialRunningInfo.rawCanvas.blueprintName || 'Untitled',
          blocks: initialRunningInfo.rawCanvas.blocks || [],
          edges: initialRunningInfo.rawCanvas.edges || [],
          annotations: initialRunningInfo.rawCanvas.annotations || [],
          isDirty: false,
          past: [],
          future: [],
          canvasStack: [{ breadcrumbLabel: 'Main', type: 'main' }],
          currentLevelIndex: 0,
          viewport: initialRunningInfo.rawCanvas.viewport || defaultViewport
        };
        // Synchronously set refs to prevent WebSocket message race conditions
        activeTabIdRef.current = initialTabId;
        runningTabIdRef.current = initialTabId;
        setTabs([newTab]);
        setActiveTabId(initialTabId);
        setBlocks(initialRunningInfo.rawCanvas.blocks || []);
        setEdges(initialRunningInfo.rawCanvas.edges || []);
        setCurrentBlueprintName(initialRunningInfo.rawCanvas.blueprintName === 'Untitled' ? '' : (initialRunningInfo.rawCanvas.blueprintName || ''));
        setRunningTabId(initialTabId);
        setIsRunning(true);
        setIsPaused(initialRunningInfo.state === 'PAUSED');
        startTelemetryStream(initialRunningInfo.runId);
      } else {
        const newTab: Tab = {
          id: initialTabId,
          name: 'Untitled',
          blocks: [],
          edges: [],
          annotations: [],
          isDirty: false,
          past: [],
          future: [],
          canvasStack: [{ breadcrumbLabel: 'Main', type: 'main' }],
          currentLevelIndex: 0,
          viewport: defaultViewport
        };
        setTabs([newTab]);
        setActiveTabId(initialTabId);
      }
    }
  }, [loading, tabs.length, initialRunningInfo]);

  // Keep active tab name and dirty metadata synchronized in the tabs array
  useEffect(() => {
    if (!activeTabId) return;
    setTabs(prev => prev.map(t => {
      if (t.id === activeTabId) {
        return {
          ...t,
          name: currentBlueprintName || 'Untitled',
          isDirty: isDirty
        };
      }
      return t;
    }));
  }, [currentBlueprintName, isDirty, activeTabId]);

  const handleMoveEnd = useCallback((_: any, currentViewport: { x: number; y: number; zoom: number }) => {
    if (!activeTabId) return;
    setTabs(prev => prev.map(t => {
      if (t.id === activeTabId) {
        return {
          ...t,
          viewport: currentViewport
        };
      }
      return t;
    }));
  }, [activeTabId]);

  // Automatically close script editor if the editing block is deleted/removed
  useEffect(() => {
    if (activeScriptBlock) {
      const nodeExists = blocks.some((n: any) => n.id === activeScriptBlock.id);
      if (!nodeExists) {
        setActiveScriptBlock(null);
      }
    }
  }, [blocks, activeScriptBlock]);

  // Automatically close inspector if the inspected block is deleted/removed
  useEffect(() => {
    if (inspectedBlockId) {
      const nodeExists = blocks.some((n: any) => n.id === inspectedBlockId);
      if (!nodeExists) {
        setInspectedBlockId(null);
        setInspectorOpen(false);
      }
    }
  }, [blocks, inspectedBlockId]);

  // Automatically switch inspected block to the first selected block if inspector is open
  useEffect(() => {
    if (inspectorOpen) {
      const selectedNodes = blocks.filter((n: any) => n.selected);
      if (selectedNodes.length > 0) {
        const firstSelectedId = selectedNodes[0].id;
        if (firstSelectedId !== inspectedBlockId) {
          setInspectedBlockId(firstSelectedId);
        }
      }
    }
  }, [blocks, inspectorOpen, inspectedBlockId]);

  // Trigger fit view after navigating into a cluster
  useEffect(() => {
    if (shouldFitView && reactFlowInstance) {
      const timer = setTimeout(() => {
        reactFlowInstance.fitView({ padding: 0.2, duration: 300 });
        setShouldFitView(false);
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [shouldFitView, reactFlowInstance, blocks.length]);

  // Synchronize edge/wire colors dynamically for data passthrough blocks
  useEffect(() => {
    let changed = false;
    const newEdges = edges.map(edge => {
      const srcNode = blocks.find(n => n.id === edge.source);
      const isExecEdge = (blockRegistry?.[srcNode?.data?.action || '']?.execOuts?.includes(edge.sourceHandle || '') || false);
      const shouldAnimate = !liteMode && isExecEdge;
      
      if (isExecEdge) {
        if (edge.style?.stroke !== '#a78bfa' || edge.animated !== shouldAnimate) {
          changed = true;
          return {
            ...edge,
            animated: shouldAnimate,
            style: { ...edge.style, stroke: '#a78bfa', strokeWidth: 2, animated: shouldAnimate },
            markerEnd: { ...(edge.markerEnd || {}), color: '#a78bfa' }
          };
        }
        return edge;
      }
      
      const expectedColor = getResolvedEdgeColor(edge.source, edge.sourceHandle || '', blocks, edges, blockRegistry);
      if (edge.style?.stroke !== expectedColor || edge.animated) {
        changed = true;
        return {
          ...edge,
          animated: false,
          style: {
            ...edge.style,
            stroke: expectedColor,
            strokeWidth: 1.5,
            animated: false
          },
          markerEnd: {
            ...(edge.markerEnd || {}),
            color: expectedColor
          }
        };
      }
      return edge;
    });

    if (changed) {
      setEdges(newEdges);
    }
  }, [blocks, edges, blockRegistry, liteMode]);

  // Sync block changes back into blocks array
  const onBlockDataChange = useCallback((id: string, key: string, value: any) => {
    setIsDirty(true);
    setBlocks((nds) =>
      nds.map((block) => {
        if (block.id === id) {
          return {
            ...block,
            data: {
              ...block.data,
              [key]: value,
            },
          };
        }
        return block;
      })
    );

    // Automatic cleanup of disconnected/broken edges when custom inputs or outputs change
    if (key === 'customInputs') {
      const newInputNames = (value || []).map((inp: any) => inp.name);
      setEdges((eds) =>
        eds.filter((edge) => {
          if (edge.target === id) {
            if (edge.targetHandle !== 'In' && !newInputNames.includes(edge.targetHandle)) {
              return false;
            }
          }
          return true;
        })
      );
    } else if (key === 'customOutputs') {
      const newOutputNames = (value || []).map((out: any) => out.name);
      setEdges((eds) =>
        eds.filter((edge) => {
          if (edge.source === id) {
            if (edge.sourceHandle !== 'Out' && !newOutputNames.includes(edge.sourceHandle)) {
              return false;
            }
          }
          return true;
        })
      );
    } else if (key === 'library_args' || key === 'ffi_args') {
      const activeArgs = value || [];
      const validInputs = ['Library', 'FunctionName', 'ReturnType'];
      const validOutputs = ['ReturnValue', 'Status'];

      activeArgs.forEach((arg: any) => {
        const name = (arg.name || '').trim();
        if (!name) return;
        if (arg.direction === 'in' || arg.direction === 'inout_buffer' || arg.direction === 'inout') {
          validInputs.push(name);
        }
        if (arg.direction === 'out_buffer' || arg.direction === 'out_ptr' || arg.direction === 'inout_buffer' || arg.direction === 'out' || arg.direction === 'inout') {
          validOutputs.push(name);
        }
      });

      setEdges((eds) =>
        eds.filter((edge) => {
          if (edge.target === id) {
            if (edge.targetHandle !== 'Call' && !validInputs.includes(edge.targetHandle)) {
              return false;
            }
          }
          if (edge.source === id) {
            if (edge.sourceHandle !== 'Out' && !validOutputs.includes(edge.sourceHandle)) {
              return false;
            }
          }
          return true;
        })
      );
    }

    // If execution is active, propagate the property change to the backend in real-time
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      const msg = {
        type: 'update_property',
        block_id: id,
        name: key,
        value: value,
      };
      wsRef.current.send(JSON.stringify(msg));
    }
  }, [setBlocks, setEdges]);

  const onScriptCodeChange = useCallback((blockId: string, code: string) => {
    onBlockDataChange(blockId, 'code', code);
  }, [onBlockDataChange]);

  const navigateToCluster = useCallback(async (blockId: string, actionType: string) => {
    const currentNodes = blocksRef.current;
    const currentEdges = edgesRef.current;
    const clusterNode = currentNodes.find((n: any) => n.id === blockId);
    if (!clusterNode) {
      setErrorMessage(`Cluster block '${blockId}' not found. Try closing and reopening.`);
      return;
    }
    if (actionType.startsWith('cluster/boundary/') || actionType === 'cluster/input' || actionType === 'cluster/output') return;
    if (!actionType.startsWith('user/cluster/') && !actionType.startsWith('workspace/cluster/') && !actionType.startsWith('builtin/cluster/') && !actionType.startsWith('cluster/') && !actionType.startsWith('clusters/')) return;

    try {
      const url = `${BACKEND_URL}/cluster/${encodeURIComponent(actionType)}`;
      const defRes = await axios.get(url);
      const clusterDef = defRes.data;

      const levelIndex = currentLevelIndexRef.current;
      const stack = canvasStackRef.current;

      const updatedStack = [...stack];
      updatedStack[levelIndex] = {
        ...updatedStack[levelIndex],
        savedNodes: currentNodes.map((n: any) => ({ ...n, data: { ...n.data } })),
        savedEdges: currentEdges.map((e: any) => ({ ...e })),
      };

      // Build internal nodes for ReactFlow from the cluster's internal_blueprint
      const internalNodes = (clusterDef.internal_blueprint?.blocks || []).map((bn: any) => ({
        id: bn.id,
        type: 'actionNode',
        position: bn.position || { x: Math.random() * 200 + 50, y: Math.random() * 200 + 50 },
        data: {
          action: bn.type,
          status: 'idle',
          resultMessage: '',
          onChange: onBlockDataChange,
          onEditScript: onEditScript,
          onEditLibrarySignature: onEditLibrarySignature,
          onNavigateInto: (nid: string, atype: string) => navigateToCluster(nid, atype),
          onInspect: handleInspectNode,
          onResizeStart: () => pushStateToHistoryRef.current(),
          onResizeEnd: () => setIsDirty(true),
          ...(bn.properties || {}),
        },
        style: bn.style || (blockRegistry?.[bn.type]?.defaultWidth && blockRegistry?.[bn.type]?.defaultHeight
          ? { width: blockRegistry[bn.type].defaultWidth, height: blockRegistry[bn.type].defaultHeight }
          : { width: 210, minHeight: 100 }),
        width: bn.width,
        height: bn.height,
      }));

      const internalEdges = (clusterDef.internal_blueprint?.links || []).map((bl: any) => {
        const srcNode = (clusterDef.internal_blueprint?.blocks || []).find((n: any) => n.id === bl.source_block);
        const srcActionType = srcNode?.type;
        const sourceData = srcNode?.properties || {};

        let isExec = bl.type === 'exec';
        let pinColor = '#64748b'; // default gray

        if (isExec) {
          pinColor = '#a78bfa';
        } else if (srcActionType) {
          if (srcActionType === 'cluster/boundary/input') {
            const dataType = sourceData.DataType || 'any';
            pinColor = getPinColor(dataType);
          } else if (srcActionType && srcActionType.startsWith('script/')) {
            const pin = (sourceData.customOutputs || []).find((p: any) => p.name === bl.source_pin);
            if (pin) { pinColor = getPinColor(pin.type); }
          } else {
            const layout = blockRegistry?.[srcActionType];
            if (layout) {
              const pin = layout.dataOuts?.find((p: any) => p.name === bl.source_pin);
              if (pin) { pinColor = getPinColor(pin.type); }
            }
          }
        }

        return {
          id: bl.id,
          type: 'default',
          source: bl.source_block,
          sourceHandle: bl.source_pin,
          target: bl.target_block,
          targetHandle: bl.target_pin,
          style: isExec
            ? { stroke: pinColor, strokeWidth: 2, animated: !liteMode }
            : { stroke: pinColor, strokeWidth: 1.5, animated: false },
          markerEnd: { type: 'arrowclosed', color: pinColor },
        };
      });

      const layout = blockRegistry?.[actionType];
      const clusterName = layout?.name || actionType.split('/').pop() || 'Cluster';

      const newLevel = {
        breadcrumbLabel: clusterName,
        type: actionType,
      };
      updatedStack.push(newLevel);
      setCanvasStack(updatedStack);
      setCurrentLevelIndex(updatedStack.length - 1);
      setBlocks(internalNodes);
      setEdges(internalEdges);
      setErrorMessage(null);
      setShouldFitView(true);
    } catch (err: any) {
      console.error('Failed to navigate into cluster:', err);
      setErrorMessage(`Failed to open cluster: ${err.response?.data?.detail || err.message}`);
    }
  }, [blockRegistry, onBlockDataChange, onEditScript, onEditLibrarySignature, setBlocks, setEdges, setIsDirty]);

  const handleInspectNode = useCallback((blockId: string) => {
    setInspectedBlockId(blockId);
    setInspectorOpen(true);
  }, []);

  // Toggle whole block in/out of dashboard
  const toggleBlockDashboard = useCallback((blockId: string) => {
    setDashboardItems((prev) => {
      const exists = prev.some((i) => i.blockId === blockId && i.type === 'block');
      if (exists) {
        return prev.filter((i) => !(i.blockId === blockId && i.type === 'block'));
      } else {
        return [...prev, { id: `dash_${blockId}`, blockId, type: 'block', order: prev.length }];
      }
    });
    setBlocks((prev) =>
      prev.map((b) => {
        if (b.id === blockId) {
          return {
            ...b,
            data: {
              ...b.data,
              inDashboard: !b.data?.inDashboard,
            },
          };
        }
        return b;
      })
    );
    setDashboardOpen(true);
    setIsDirty(true);
  }, [setBlocks, setIsDirty]);

  // Toggle individual pin in/out of dashboard
  const togglePinDashboard = useCallback((blockId: string, pinName: string) => {
    setDashboardItems((prev) => {
      const exists = prev.some((i) => i.blockId === blockId && i.type === 'pin' && i.pinName === pinName);
      if (exists) {
        return prev.filter((i) => !(i.blockId === blockId && i.type === 'pin' && i.pinName === pinName));
      } else {
        return [...prev, { id: `dash_${blockId}_${pinName}`, blockId, type: 'pin', pinName, order: prev.length }];
      }
    });
    setBlocks((prev) =>
      prev.map((b) => {
        if (b.id === blockId) {
          const currentPins: string[] = Array.isArray(b.data?.dashboardPins) ? [...b.data.dashboardPins] : [];
          const exists = currentPins.includes(pinName);
          const nextPins = exists ? currentPins.filter((p) => p !== pinName) : [...currentPins, pinName];
          return {
            ...b,
            data: {
              ...b.data,
              dashboardPins: nextPins,
            },
          };
        }
        return b;
      })
    );
    setDashboardOpen(true);
    setIsDirty(true);
  }, [setBlocks, setIsDirty]);

  // Jump to block and center on canvas
  const handleJumpToBlock = useCallback((blockId: string) => {
    const node = blocksRef.current.find((b) => b.id === blockId);
    if (!node) return;
    if (reactFlowInstance) {
      const nodeX = node.position.x + (node.width || 240) / 2;
      const nodeY = node.position.y + (node.height || 140) / 2;
      reactFlowInstance.setCenter(nodeX, nodeY, { zoom: 1.1, duration: 400 });
    }
    setBlocks((prev) =>
      prev.map((b) => ({
        ...b,
        selected: b.id === blockId,
      }))
    );
  }, [reactFlowInstance, setBlocks]);

  const pushStateToHistoryRef = useRef<() => void>(() => {});

  // Base block data factory
  const getBaseBlockData = useCallback((extra: any = {}) => ({
    ...extra,
    status: extra.status || 'idle',
    resultMessage: extra.resultMessage || '',
    results: extra.results || {},
    onChange: onBlockDataChange,
    onEditScript: onEditScript,
    onEditLibrarySignature: onEditLibrarySignature,
    onNavigateInto: navigateToCluster,
    onInspect: handleInspectNode,
    onToggleDashboard: toggleBlockDashboard,
    onTogglePinDashboard: togglePinDashboard,
    onResizeStart: () => pushStateToHistoryRef.current(),
    onResizeEnd: () => setIsDirty(true),
  }), [onBlockDataChange, onEditScript, onEditLibrarySignature, navigateToCluster, handleInspectNode, toggleBlockDashboard, togglePinDashboard, setIsDirty]);


  const {
    pushStateToHistory,
    handleUndo,
    handleRedo,
    handleCopy,
    handlePaste,
    handleDuplicate,
    clipboardBlocksCount,
  } = useWorkspaceHistory({
    blocks,
    edges,
    annotations,
    setBlocks,
    setEdges,
    setAnnotations,
    setIsDirty,
    selectedBlockIds,
    setSelectedBlockIds,
    reactFlowInstance,
    snapToGrid,
    getBaseBlockData,
    pastRef,
    futureRef,
  });

  pushStateToHistoryRef.current = pushStateToHistory;

  // Context Menu handlers
  const closeContextMenu = useCallback(() => {
    setContextMenu({ show: false, x: 0, y: 0, clientX: 0, clientY: 0, type: 'pane' });
    setContextMenuSearch('');
    setQuickConnectMenu(null);
  }, []);

  const handleClearBlockData = useCallback(async (blockId: string) => {
    pushStateToHistory();
    setIsDirty(true);
    
    setBlocks((nds) =>
      nds.map((block) => {
        if (block.id === blockId) {
          const clearedData = { ...block.data };
          clearedData.status = 'idle';
          clearedData.resultMessage = '';
          clearedData.results = {};
          return {
            ...block,
            data: clearedData,
          };
        }
        return block;
      })
    );

    setTabs((prevTabs) =>
      prevTabs.map((t) => {
        if (t.id !== activeTabId) return t;
        const updatedNodes = (t.blocks || []).map((block: any) => {
          if (block.id === blockId) {
            const clearedData = { ...block.data };
            clearedData.status = 'idle';
            clearedData.resultMessage = '';
            clearedData.results = {};
            return { ...block, data: clearedData };
          }
          return block;
        });
        return { ...t, blocks: updatedNodes };
      })
    );

    try {
      await axios.post(`${BACKEND_URL}/blocks/${blockId}/clear`);
    } catch (err) {
      console.warn('Failed to notify backend to clear block data:', err);
    }
  }, [setBlocks, setTabs, BACKEND_URL, pushStateToHistory]);

  const handleClearAllBlocksData = useCallback(async () => {
    pushStateToHistory();
    setIsDirty(true);

    setBlocks((nds) =>
      nds.map((block) => {
        const clearedData = { ...block.data };
        clearedData.status = 'idle';
        clearedData.resultMessage = '';
        clearedData.results = {};
        return {
          ...block,
          data: clearedData,
        };
      })
    );

    setTabs((prevTabs) =>
      prevTabs.map((t) => {
        if (t.id !== activeTabId) return t;
        const updatedNodes = (t.blocks || []).map((block: any) => {
          const clearedData = { ...block.data };
          clearedData.status = 'idle';
          clearedData.resultMessage = '';
          clearedData.results = {};
          return { ...block, data: clearedData };
        });
        return { ...t, blocks: updatedNodes };
      })
    );

    const blockIds = blocks.map((n) => n.id);
    try {
      await Promise.all(
        blockIds.map((id) => axios.post(`${BACKEND_URL}/blocks/${id}/clear`))
      );
    } catch (err) {
      console.warn('Failed to notify backend to clear some blocks data:', err);
    }
  }, [blocks, activeTabId, setBlocks, setTabs, BACKEND_URL, pushStateToHistory]);


  // Converts the React Flow representation to ComfyLAB blueprint JSON specification
  const exportBlueprint = () => {
    const blueprintNodes = blocks.map((block) => {
      const props: Record<string, any> = {};
      const excludeKeys = ['action', 'status', 'resultMessage', 'onChange', 'results', 'onEditScript', 'onEditFFISignature', 'onEditLibrarySignature', 'onNavigateInto', 'onInspect'];

      
      // Dynamically copy all non-metadata fields from block.data to properties
      Object.keys(block.data || {}).forEach((key) => {
        if (!excludeKeys.includes(key) && (block.data as any)[key] !== undefined) {
          props[key] = (block.data as any)[key];
        }
      });
      return {
        id: block.id,
        type: block.data.action,
        properties: props,
      };
    });

    const blueprintLinks = edges.map((edge) => {
      const sourceBlock = blocks.find((n) => n.id === edge.source);
      const layout = blockRegistry?.[sourceBlock?.data?.action || ''];
      const isExec = layout?.execOuts.includes(edge.sourceHandle || '');

      return {
        id: edge.id,
        type: isExec ? 'exec' : 'data',
        source_block: edge.source,
        source_pin: edge.sourceHandle || '',
        target_block: edge.target,
        target_pin: edge.targetHandle || '',
      };
    });
return {
      blocks: blueprintNodes,
      links: blueprintLinks,
    };
  };

  const {
          drawTool,
          setDrawTool,
          drawColor,
          setDrawColor,
          drawWidth,
          setDrawWidth,
          drawStyle,
          setDrawStyle,
          lineStartCap,
          setLineStartCap,
          lineEndCap,
          setLineEndCap,
          drawFillEnable,
          setDrawFillEnable,
          drawFillColor,
          setDrawFillColor,
          drawFillOpacity,
          setDrawFillOpacity,
          eraserPath,
          markedForDeletion,
          hoverPoint,
          currentAnnotation,
          currentAnnotationRef,
          editingTextId,
          setEditingTextId,
          selectedAnnotationId,
          deleteSelectedAnnotation,
          commitActivePolyshape,
          handleResizeStart,
          handleSvgMouseDown,
          handleSvgMouseMove,
          handleSvgMouseUp,
          handleSvgDoubleClick,
          handleSvgWheel,
        } = useWhiteboardState({
          reactFlowInstance,
          snapToGrid,
          pushStateToHistory,
          closeContextMenu,
          blocks,
          edges,
          annotations,
          setAnnotations,
          isLocked,
          reactFlowWrapperRef: reactFlowWrapper,
        });

        const {
          handleRun,
          handlePause,
          handleResume,
          handleAbort,
          startTelemetryStream,
          wsRef,
        } = useFlowExecution({
          activeTabId,
          tabs,
          blocks,
          edges,
          currentBlueprintName,
          setBlocks,
          setTabs,
          exportBlueprint,
          BACKEND_URL,
          WS_BACKEND_URL,
          isRunning,
          setIsRunning,
          isPaused,
          setIsPaused,
          runningTabId,
          setRunningTabId,
          setErrorMessage,
          blockRegistry,
          liteMode,
        });

        const handleRunRef = useRef(handleRun);
        handleRunRef.current = handleRun;
        const handlePauseRef = useRef(handlePause);
        handlePauseRef.current = handlePause;
        const handleResumeRef = useRef(handleResume);
        handleResumeRef.current = handleResume;
        const handleAbortRef = useRef(handleAbort);
        handleAbortRef.current = handleAbort;
        const isRunningRef = useRef(isRunning);
        isRunningRef.current = isRunning;
        const isPausedRef = useRef(isPaused);
        isPausedRef.current = isPaused;
        const isDirtyRef = useRef(isDirty);
        isDirtyRef.current = isDirty;

        // Warn before leaving the page when there are unsaved changes or an active run
        useEffect(() => {
          const handleBeforeUnload = (e: BeforeUnloadEvent) => {
            const hasUnsavedChanges = isDirtyRef.current || tabsRef.current.some((tab) => tab.isDirty);
            if (!hasUnsavedChanges && !isRunningRef.current) return;
            e.preventDefault();
            e.returnValue = '';
          };
          window.addEventListener('beforeunload', handleBeforeUnload);
          return () => window.removeEventListener('beforeunload', handleBeforeUnload);
        }, []);

  // --- HISTORY & UNDO/REDO UTILITIES ---

  const onBlocksChange = useCallback((changes: any[]) => {
    // Filter out position changes for pinned blocks
    const filteredChanges = changes.filter(c => {
      if (c.type === 'position') {
        const block = blocksRef.current.find(n => n.id === c.id);
        if (block?.data?.pinned) {
          return false;
        }
      }
      return true;
    });

    const hasRemoval = filteredChanges.some(c => c.type === 'remove');
    if (hasRemoval) {
      pushStateToHistory();
    }
    const hasDirtyChange = filteredChanges.some(c => c.type === 'position' || c.type === 'remove' || c.type === 'add');
    if (hasDirtyChange) {
      setIsDirty(true);
    }
    reactFlowOnBlocksChange(filteredChanges);
  }, [reactFlowOnBlocksChange, pushStateToHistory]);

  const onEdgesChange = useCallback((changes: any[]) => {
    const hasRemoval = changes.some(c => c.type === 'remove');
    if (hasRemoval) {
      pushStateToHistory();
    }
    const hasDirtyChange = changes.some(c => c.type === 'remove' || c.type === 'add');
    if (hasDirtyChange) {
      setIsDirty(true);
    }
    reactFlowOnEdgesChange(changes);
  }, [reactFlowOnEdgesChange, pushStateToHistory]);

  const onBlockDragStart = useCallback(() => {
    pushStateToHistory();
  }, [pushStateToHistory]);

  const getOutputPinType = useCallback((block: any, pinName: string): string => {
    const action = block.data?.action;
    if (action?.startsWith('script/')) {
      const pin = (block.data?.customOutputs || []).find((p: any) => p.name === pinName);
      return pin?.type || 'any';
    }
    if (action === 'cluster/boundary/input') return block.data?.DataType || 'any';
    const layout = registryRef.current?.[action];
    if (layout) {
      if (layout.execOuts?.includes(pinName)) return 'exec';
      const pin = layout.dataOuts?.find((p: any) => p.name === pinName);
      return pin?.type || 'any';
    }
    return 'any';
  }, []);

  const getInputPinType = useCallback((block: any, pinName: string): string => {
    const action = block.data?.action;
    if (action?.startsWith('script/')) {
      const pin = (block.data?.customInputs || []).find((p: any) => p.name === pinName);
      return pin?.type || 'any';
    }
    const layout = registryRef.current?.[action];
    if (layout) {
      if (layout.execIns?.includes(pinName)) return 'exec';
      const pin = layout.dataIns?.find((p: any) => p.name === pinName);
      return pin?.type || 'any';
    }
    return 'any';
  }, []);

  const getNodePinDefs = useCallback((block: any) => {
    const action = block.data?.action;
    const layout = registryRef.current?.[action];
    if (action?.startsWith('script/')) {
      const customIns = (block.data?.customInputs || []).filter((p: any) => p.type !== 'exec');
      const customOuts = (block.data?.customOutputs || []).filter((p: any) => p.type !== 'exec');
      return {
        execIns: layout?.execIns || [],
        execOuts: layout?.execOuts || [],
        dataIns: customIns,
        dataOuts: customOuts,
      };
    }
    if (layout) {
      return {
        execIns: layout.execIns || [],
        execOuts: layout.execOuts || [],
        dataIns: layout.dataIns || [],
        dataOuts: layout.dataOuts || [],
      };
    }
    return { execIns: [], execOuts: [], dataIns: [], dataOuts: [] };
  }, []);

  const matchPins = useCallback((outputPinNames: string[], inputPinNames: string[], outputNode: any, inputNode: any) => {
    const pairs: { outputPin: string; inputPin: string }[] = [];
    const usedOutputs = new Set<string>();
    const usedInputs = new Set<string>();

    const getOutputType = (pin: string) => getOutputPinType(outputNode, pin);
    const getInputType = (pin: string) => getInputPinType(inputNode, pin);

    // Pass 1: match by exact type
    for (const outPin of outputPinNames) {
      const outType = getOutputType(outPin);
      if (outType === 'exec') continue;
      for (const inPin of inputPinNames) {
        if (usedInputs.has(inPin)) continue;
        const inType = getInputType(inPin);
        if (inType === 'exec') continue;
        if (outType === inType || outType === 'any' || inType === 'any') {
          pairs.push({ outputPin: outPin, inputPin: inPin });
          usedOutputs.add(outPin);
          usedInputs.add(inPin);
          break;
        }
      }
    }

    // Pass 2: fill remaining by position
    const remainingOuts = outputPinNames.filter(p => !usedOutputs.has(p) && getOutputType(p) !== 'exec');
    const remainingIns = inputPinNames.filter(p => !usedInputs.has(p) && getInputType(p) !== 'exec');
    const len = Math.min(remainingOuts.length, remainingIns.length);
    for (let i = 0; i < len; i++) {
      pairs.push({ outputPin: remainingOuts[i], inputPin: remainingIns[i] });
    }

    return pairs;
  }, [getOutputPinType, getInputPinType]);

  const onBlockDrag = useCallback((_event: any, draggedNode: any) => {
    if (!draggedNode) return;
    try {
    const currentNodes = blocksRef.current;
    const currentEdges = edgesRef.current;

    const dragW = draggedNode.measured?.width ?? draggedNode.width ?? 210;
    const dragH = draggedNode.measured?.height ?? draggedNode.height ?? 120;
    const dragX = draggedNode.position.x;
    const dragY = draggedNode.position.y;
    const SNAP_THRESHOLD = 50;

    let bestTarget: { block: any; side: 'left' | 'right'; gap: number } | null = null;

    for (const other of currentNodes) {
      if (other.id === draggedNode.id) continue;
      if (other.data?.pinned) continue;

      const otherW = other.measured?.width ?? other.width ?? 210;
      const otherH = other.measured?.height ?? other.height ?? 120;
      const otherX = other.position.x;
      const otherY = other.position.y;

      // Check vertical overlap (at least 30% of the smaller block)
      const overlapTop = Math.max(dragY, otherY);
      const overlapBottom = Math.min(dragY + dragH, otherY + otherH);
      const overlapHeight = Math.max(0, overlapBottom - overlapTop);
      const minH = Math.min(dragH, otherH);
      if (overlapHeight < minH * 0.3) continue;

      // Check horizontal proximity
      const gapRight = otherX - (dragX + dragW); // gap: dragged right edge → other left edge (positive = dragged is LEFT of other)
      const gapLeft = dragX - (otherX + otherW);  // gap: other right edge → dragged left edge (positive = dragged is RIGHT of other)

      if (gapRight >= -10 && gapRight < SNAP_THRESHOLD) {
        // Dragged is to the LEFT of other → dragged outputs → other inputs
        if (!bestTarget || gapRight < bestTarget.gap) {
          bestTarget = { block: other, side: 'left', gap: gapRight };
        }
      }
      if (gapLeft >= -10 && gapLeft < SNAP_THRESHOLD) {
        // Dragged is to the RIGHT of other → other outputs → dragged inputs
        if (!bestTarget || gapLeft < bestTarget.gap) {
          bestTarget = { block: other, side: 'right', gap: gapLeft };
        }
      }
    }

    if (!bestTarget) {
      if (snapTargetRef.current !== null) {
        snapPreviewRef.current = [];
        snapTargetRef.current = null;
        if (snapRafRef.current) cancelAnimationFrame(snapRafRef.current);
        snapRafRef.current = requestAnimationFrame(() => {
          setSnapPreviewEdges([]);
        });
      }
      return;
    }

    const target = bestTarget.block;
    const draggedPins = getNodePinDefs(draggedNode);
    const targetPins = getNodePinDefs(target);
    const previews: any[] = [];

    const getEdgeColor = (sourceBlock: any, handleName: string, isExec: boolean) => {
      if (isExec) return '#a78bfa';
      const type = getOutputPinType(sourceBlock, handleName);
      return getPinColor(type);
    };

    const isAlreadyConnected = (sourceId: string, sourceHandle: string, targetId: string, targetHandle: string) => {
      return currentEdges.some((e: any) =>
        (e.source === sourceId && e.sourceHandle === sourceHandle) ||
        (e.target === targetId && e.targetHandle === targetHandle)
      );
    };

    if (bestTarget.side === 'right') {
      // Dragged is to the right of target → target outputs → dragged inputs
      const execPairs = Math.min(targetPins.execOuts.length, draggedPins.execIns.length);
      for (let i = 0; i < execPairs; i++) {
        const sPin = targetPins.execOuts[i];
        const tPin = draggedPins.execIns[i];
        if (!isAlreadyConnected(target.id, sPin, draggedNode.id, tPin)) {
          previews.push({
            id: `snap-preview-${target.id}-${sPin}-${draggedNode.id}-${tPin}`,
            source: target.id,
            sourceHandle: sPin,
            target: draggedNode.id,
            targetHandle: tPin,
            style: { stroke: '#a78bfa', strokeWidth: 1.5, strokeDasharray: '6 4', opacity: 0.5 },
            type: 'default',
            deletable: false,
          });
        }
      }
      const dataPairs = matchPins(
        targetPins.dataOuts.map((p: any) => p.name),
        draggedPins.dataIns.map((p: any) => p.name),
        target, draggedNode
      );
      for (const pair of dataPairs) {
        if (!isAlreadyConnected(target.id, pair.outputPin, draggedNode.id, pair.inputPin)) {
          const color = getEdgeColor(target, pair.outputPin, false);
          previews.push({
            id: `snap-preview-${target.id}-${pair.outputPin}-${draggedNode.id}-${pair.inputPin}`,
            source: target.id,
            sourceHandle: pair.outputPin,
            target: draggedNode.id,
            targetHandle: pair.inputPin,
            style: { stroke: color, strokeWidth: 1.5, strokeDasharray: '6 4', opacity: 0.5 },
            type: 'default',
            deletable: false,
          });
        }
      }
    } else {
      // Dragged is to the left of target → dragged outputs → target inputs
      const execPairs = Math.min(draggedPins.execOuts.length, targetPins.execIns.length);
      for (let i = 0; i < execPairs; i++) {
        const sPin = draggedPins.execOuts[i];
        const tPin = targetPins.execIns[i];
        if (!isAlreadyConnected(draggedNode.id, sPin, target.id, tPin)) {
          previews.push({
            id: `snap-preview-${draggedNode.id}-${sPin}-${target.id}-${tPin}`,
            source: draggedNode.id,
            sourceHandle: sPin,
            target: target.id,
            targetHandle: tPin,
            style: { stroke: '#a78bfa', strokeWidth: 1.5, strokeDasharray: '6 4', opacity: 0.5 },
            type: 'default',
            deletable: false,
          });
        }
      }
      const dataPairs = matchPins(
        draggedPins.dataOuts.map((p: any) => p.name),
        targetPins.dataIns.map((p: any) => p.name),
        draggedNode, target
      );
      for (const pair of dataPairs) {
        if (!isAlreadyConnected(draggedNode.id, pair.outputPin, target.id, pair.inputPin)) {
          const color = getEdgeColor(draggedNode, pair.outputPin, false);
          previews.push({
            id: `snap-preview-${draggedNode.id}-${pair.outputPin}-${target.id}-${pair.inputPin}`,
            source: draggedNode.id,
            sourceHandle: pair.outputPin,
            target: target.id,
            targetHandle: pair.inputPin,
            style: { stroke: color, strokeWidth: 1.5, strokeDasharray: '6 4', opacity: 0.5 },
            type: 'default',
            deletable: false,
          });
        }
      }
    }

    const newKey = previews.map((p: any) => p.id).join(',');
    const oldKey = snapPreviewRef.current.map((p: any) => p.id).join(',');
    snapPreviewRef.current = previews;
    snapTargetRef.current = { targetId: target.id, previews };
    if (newKey !== oldKey) {
      if (snapRafRef.current) cancelAnimationFrame(snapRafRef.current);
      snapRafRef.current = requestAnimationFrame(() => {
        setSnapPreviewEdges(snapPreviewRef.current);
      });
    }
    } catch (e) {
      // Prevent snap-connect errors from breaking block dragging
    }
  }, [getNodePinDefs, matchPins, getOutputPinType]);

  const onBlockDragStop = useCallback((_event: any, _draggedNode: any) => {
    if (snapRafRef.current) {
      cancelAnimationFrame(snapRafRef.current);
      snapRafRef.current = null;
    }
    const snap = snapTargetRef.current;
    snapPreviewRef.current = [];
    setSnapPreviewEdges([]);
    snapTargetRef.current = null;

    if (!snap || snap.previews.length === 0) return;

    pushStateToHistory();
    setIsDirty(true);

    const newEdges = snap.previews.map((preview: any) => {
      const isExec = preview.style.stroke === '#a78bfa';
      const pinColor = isExec ? '#a78bfa' : preview.style.stroke;
      const edgeStyle = isExec
        ? { stroke: pinColor, strokeWidth: 2, animated: !liteMode }
        : { stroke: pinColor, strokeWidth: 1.5, animated: false };
      return {
        id: `edge_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        source: preview.source,
        sourceHandle: preview.sourceHandle,
        target: preview.target,
        targetHandle: preview.targetHandle,
        style: edgeStyle,
        markerEnd: { type: MarkerType.ArrowClosed, color: pinColor },
        type: 'default',
      };
    });

    setEdges((eds: any[]) => {
      const existingKeys = new Set(eds.map((e: any) => `${e.source}:${e.sourceHandle}->${e.target}:${e.targetHandle}`));
      const filtered = newEdges.filter((e: any) => !existingKeys.has(`${e.source}:${e.sourceHandle}->${e.target}:${e.targetHandle}`));
      return [...eds, ...filtered];
    });
  }, [setEdges, pushStateToHistory]);

  const onLayout = useCallback(() => {
    pushStateToHistory();

    const dagreGraph = new dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));
    dagreGraph.setGraph({
      rankdir: 'LR',
      nodesep: 40,
      ranksep: 80,
      align: 'UL',
    });

    blocks.forEach((block) => {
      const width = block.measured?.width ?? block.width ?? (block.style?.width ? parseFloat(String(block.style.width)) : 210);
      const height = block.measured?.height ?? block.height ?? (block.style?.height ? parseFloat(String(block.style.height)) : 120);

      dagreGraph.setNode(block.id, {
        width,
        height,
      });
    });

    edges.forEach((edge) => {
      dagreGraph.setEdge(edge.source, edge.target);
    });

    dagre.layout(dagreGraph);

    const layoutedNodes = blocks.map((block) => {
      if (block.data?.pinned) {
        return block;
      }

      const nodeWithPosition = dagreGraph.node(block.id);
      const width = block.measured?.width ?? block.width ?? (block.style?.width ? parseFloat(String(block.style.width)) : 210);
      const height = block.measured?.height ?? block.height ?? (block.style?.height ? parseFloat(String(block.style.height)) : 120);

      let newX = nodeWithPosition.x - width / 2;
      let newY = nodeWithPosition.y - height / 2;

      if (snapToGrid) {
        newX = Math.round(newX / 16) * 16;
        newY = Math.round(newY / 16) * 16;
      }

      return {
        ...block,
        position: { x: newX, y: newY },
      };
    });

    setBlocks(layoutedNodes);
    setIsDirty(true);

    if (reactFlowInstance) {
      setTimeout(() => {
        reactFlowInstance.fitView({ padding: 0.2, duration: 400 });
      }, 50);
    }
  }, [blocks, edges, snapToGrid, reactFlowInstance, pushStateToHistory, setBlocks]);





  // Stable selection handler to avoid infinite render loops
  const onSelectionChange = useCallback(({ nodes: selNodes }: any) => {
    const ids = new Set<string>(selNodes.map((n: any) => n.id));
    setSelectedBlockIds((prev: Set<string>) => {
      if (prev.size === ids.size && [...prev].every((id: string) => ids.has(id))) {
        return prev;
      }
      return ids;
    });
  }, []);


  // Save active cluster edits to the backend
  const saveCurrentClusterEdits = useCallback(async () => {
    const curLevelIndex = currentLevelIndexRef.current;
    if (curLevelIndex === 0) return;
    const currentLevel = canvasStackRef.current[curLevelIndex];
    if (currentLevel && (currentLevel.type.startsWith('user/cluster/') || currentLevel.type.startsWith('workspace/cluster/') || currentLevel.type.startsWith('cluster/'))) {
      if (currentLevel.type.startsWith('builtin/cluster/')) return;
      try {
        const exclude = ['action', 'status', 'resultMessage', 'onChange', 'results', 'onEditScript', 'onEditFFISignature', 'onEditLibrarySignature', 'onNavigateInto', 'onInspect'];

        const blueprintNodes = blocksRef.current.map((n: any) => {
          const props: any = {};
          Object.keys(n.data || {}).forEach((k: string) => { if (!exclude.includes(k)) props[k] = n.data[k]; });
          return { id: n.id, type: n.data.action, position: n.position, properties: props, style: n.style, width: n.width, height: n.height };
        });
        const isExec = (sourceAction: string, sourceHandle: string) => {
          const layout = blockRegistry?.[sourceAction];
          return layout?.execOuts?.includes(sourceHandle) || false;
        };
        const blueprintLinks = edgesRef.current.map((e: any) => ({
          id: e.id,
          type: isExec(blocksRef.current.find((n: any) => n.id === e.source)?.data?.action || '', e.sourceHandle || '') ? 'exec' : 'data',
          source_block: e.source,
          source_pin: e.sourceHandle || '',
          target_block: e.target,
          target_pin: e.targetHandle || '',
        }));

        const defRes = await axios.get(`${BACKEND_URL}/cluster/${encodeURIComponent(currentLevel.type)}`);
        const existingDef = defRes.data;

        await axios.post(`${BACKEND_URL}/blocks/publish_cluster`, {
          display_name: existingDef.display_name || existingDef.name || currentLevel.type,
          category: existingDef.category || 'Clusters',
          icon: existingDef.icon || '📦',
          description: existingDef.description || '',
          internal_blueprint: { blocks: blueprintNodes, links: blueprintLinks },
          boundary_pins: existingDef.boundary_pins,
          destination: existingDef._is_temp ? 'temp' : (existingDef.type_name?.startsWith('workspace/') ? 'workspace' : 'global'),
          type_name: currentLevel.type
        });
        await fetchRegistry();
      } catch (err) {
        console.error('Failed to save cluster edits:', err);
      }
    }
  }, [blockRegistry, fetchRegistry]);

  // Construct payload representing the root Level 0 blueprint
  const getSavePayload = useCallback(() => {
    const curLevelIndex = currentLevelIndexRef.current;
    const rootNodes = curLevelIndex === 0 ? blocks : (canvasStackRef.current[0]?.savedNodes || []);
    const rootEdges = curLevelIndex === 0 ? edges : (canvasStackRef.current[0]?.savedEdges || []);
    const rootAnnotations = curLevelIndex === 0 ? annotations : (canvasStackRef.current[0]?.savedAnnotations || []);

    return {
      blocks: rootNodes.map(({ id, type, position, data, style, width, height }: any) => {
        const persistData = { ...data };
        delete persistData.onChange;
        delete persistData.status;
        delete persistData.resultMessage;
        delete persistData.results;
        delete persistData.onToggleDashboard;
        delete persistData.onTogglePinDashboard;
        return { id, type, position, data: persistData, style, width, height };
      }),
      edges: rootEdges,
      annotations: rootAnnotations,
      viewport: reactFlowInstance ? reactFlowInstance.getViewport() : viewport,
      dashboard: {
        items: dashboardItemsRef.current,
        width: dashboardResizer.width,
      }
    };
  }, [blocks, edges, annotations, reactFlowInstance, viewport, dashboardResizer.width]);


  // Breadcrumb navigation: navigate to a specific level
  const handleBreadcrumbNavigate = useCallback(async (index: number) => {
    const curLevelIndex = currentLevelIndexRef.current;
    if (index > curLevelIndex) return;

    // Save current level state
    const updatedStack = [...canvasStackRef.current];
    updatedStack[curLevelIndex] = {
      ...updatedStack[curLevelIndex],
      savedNodes: blocksRef.current,
      savedEdges: edgesRef.current,
      savedAnnotations: annotationsRef.current,
    };

    // If navigating out of a cluster level, persist changes to the cluster definition
    await saveCurrentClusterEdits();

    const targetLevel = updatedStack[index];
    // Recreate block and data object references to force React Flow to rebuild the components
    // and visually pick up the updated cluster inputs/outputs registry schema immediately.
    const restoredNodes = (targetLevel.savedNodes || []).map((block: any) => ({
      ...block,
      data: getBaseBlockData(block.data)
    }));
    setBlocks(restoredNodes);
    setEdges(targetLevel.savedEdges || []);
    setAnnotations(targetLevel.savedAnnotations || []);
    setShouldFitView(true);

    updatedStack.length = index + 1;
    setCanvasStack(updatedStack);
    setCurrentLevelIndex(index);
  }, [saveCurrentClusterEdits, setBlocks, setEdges, setAnnotations, getBaseBlockData]);



  // Close hamburger menu when clicking outside
  useEffect(() => {
    if (!menuOpen) return;
    const handleClickOutside = (event: MouseEvent) => {
      if (menuContainerRef.current && !menuContainerRef.current.contains(event.target as any)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside, true);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside, true);
    };
  }, [menuOpen]);

  // Handle theme transitions and storage persistence
  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'light') {
      root.classList.add('light-theme');
    } else {
      root.classList.remove('light-theme');
    }
    localStorage.setItem('comfylab-theme', theme);
  }, [theme]);

  // Handle Lite Mode transitions and storage persistence
  useEffect(() => {
    const root = document.documentElement;
    if (liteMode) {
      root.classList.add('lite-mode');
    } else {
      root.classList.remove('lite-mode');
    }
    localStorage.setItem('comfylab-lite-mode', String(liteMode));
  }, [liteMode]);

  // Persist snap-to-grid preference
  useEffect(() => {
    localStorage.setItem('comfylab-snap-to-grid', String(snapToGrid));
  }, [snapToGrid]);

  const handleSaveSettings = async (updatedSettings = settings) => {
    try {
      const res = await axios.post(`${BACKEND_URL}/settings`, updatedSettings);
      setSettings(res.data);
      setErrorMessage(null);
      await fetchRegistry();
      return true;
    } catch (err: any) {
      setErrorMessage(err.response?.data?.detail || 'Failed to save settings.');
      return false;
    }
  };

  const handleRestartServer = async () => {
    const confirmed = await confirmAsync(
      t('settingsModal.confirmRestart', 'Are you sure you want to restart the server? Any ongoing executions will be terminated.')
    );
    if (!confirmed) return;

    setIsRestartingServer(true);
    try {
      await axios.post(`${BACKEND_URL}/settings/restart`);
    } catch {
      // Backend may close connection immediately when restarting
    }

    setSettingsOpen(false);

    // Poll until the server is back online
    const startTime = Date.now();
    const pollInterval = 1000;
    const maxWaitMs = 20000;

    const checkServerOnline = async () => {
      while (Date.now() - startTime < maxWaitMs) {
        await new Promise((resolve) => setTimeout(resolve, pollInterval));
        try {
          const res = await axios.get(`${BACKEND_URL}/settings`, { timeout: 2000 });
          if (res.status === 200) {
            await fetchSettings();
            await fetchRegistry();
            setIsRestartingServer(false);
            setErrorMessage(null);
            await alertAsync(
              t('settingsModal.serverRestarted', 'Server restarted successfully!'),
              t('settingsModal.serverSection', 'Server Operations')
            );
            return;
          }
        } catch {
          // Keep polling until online
        }
      }
      setIsRestartingServer(false);
      setErrorMessage(t('settingsModal.restartTimeout', 'Server restart timed out. Please check if the server is running.'));
    };

    checkServerOnline();
  };

  // Base block data factory
  const registryRef = useRef<any>(null);
  registryRef.current = blockRegistry;

  // Connect pins (execution wires get purple styling, data wires get dynamically colored styling)
  const onConnect = useCallback(
    (params: Connection | Edge) => {
      pushStateToHistory();
      setIsDirty(true);
      const currentNodes = blocksRef.current;
      const currentRegistry = registryRef.current;
      const sourceBlock = currentNodes.find((n: any) => n.id === params.source);
      const layout = currentRegistry?.[sourceBlock?.data?.action || ''];
      
      let isExec = false;
      let pinColor = '#10b981';

      if (layout) {
        if (layout.execOuts.includes(params.sourceHandle || '')) {
          isExec = true;
          pinColor = '#a78bfa';
        } else {
          if (sourceBlock?.data?.action === 'cluster/boundary/input') {
            const dataType = sourceBlock.data.DataType || 'any';
            pinColor = getPinColor(dataType);
          } else if (sourceBlock?.data?.action && sourceBlock.data.action.startsWith('script/')) {
            const pin = (sourceBlock.data.customOutputs || []).find((p: any) => p.name === params.sourceHandle);
            if (pin) { pinColor = getPinColor(pin.type); }
          } else {
            const pin = layout.dataOuts.find((p: any) => p.name === params.sourceHandle);
            if (pin) { pinColor = getPinColor(pin.type); }
          }
        }
      }

      const edgeStyle = isExec
        ? { stroke: pinColor, strokeWidth: 2, animated: !liteMode }
        : { stroke: pinColor, strokeWidth: 1.5, animated: false };

      const marker = { type: MarkerType.ArrowClosed, color: pinColor };

      setEdges((eds) =>
        addEdge(
          {
            ...params,
            style: edgeStyle,
            markerEnd: marker,
          },
          eds
        )
      );
    },
    [setEdges, pushStateToHistory]
  );

  const quickConnectStartRef = useRef<{ nodeId: string, handleId: string, handleType: string } | null>(null);

  const onConnectStart = useCallback((_event: any, params: any) => {
    quickConnectStartRef.current = params;
  }, []);

  const onConnectEnd = useCallback((event: any, connectionState: any) => {
    if (isLocked) return;
    const isValid = connectionState && connectionState.isValid;
    const targetIsPane = event.target && event.target.classList && event.target.classList.contains('react-flow__pane');
    if (!isValid && targetIsPane && quickConnectStartRef.current) {
       const { nodeId, handleId, handleType } = quickConnectStartRef.current;
       
       const sourceBlock = blocksRef.current.find((n: any) => n.id === nodeId);
       const layout = registryRef.current?.[sourceBlock?.data?.action];
       let isExec = false;
       if (layout) {
         if (handleType === 'source') {
           if (['Out', 'Then', 'Else'].includes(handleId)) isExec = true;
           const pin = layout.dataOuts?.find((p: any) => p.name === handleId);
           if (pin?.type === 'exec') isExec = true;
         } else {
           if (['In'].includes(handleId)) isExec = true;
           const pin = layout.dataIns?.find((p: any) => p.name === handleId);
           if (pin?.type === 'exec') isExec = true;
         }
       }
       
       if (isExec) {
          quickConnectStartRef.current = null;
          return;
       }

       const clientX = 'clientX' in event ? event.clientX : (event.changedTouches ? event.changedTouches[0].clientX : 0);
       const clientY = 'clientY' in event ? event.clientY : (event.changedTouches ? event.changedTouches[0].clientY : 0);
       
       let offsetX = clientX;
       let offsetY = clientY;
       if (reactFlowWrapper.current) {
          const rect = reactFlowWrapper.current.getBoundingClientRect();
          offsetX = clientX - rect.left;
          offsetY = clientY - rect.top;
       }

       setQuickConnectMenu({
         show: true,
         clientX,
         clientY,
         offsetX,
         offsetY,
         sourceBlockId: nodeId,
         sourceHandleId: handleId,
         sourceHandleType: handleType
       });
    }
    quickConnectStartRef.current = null;
  }, [isLocked]);


  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const addBlockAtClientPosition = useCallback((type: string, clientX: number, clientY: number) => {
    if (!reactFlowInstance) return null;

    pushStateToHistory();
    setIsDirty(true);

    let position = reactFlowInstance.screenToFlowPosition({
      x: clientX,
      y: clientY,
    });

    // Snap to grid if enabled
    if (snapToGrid) {
      const GRID = 16;
      position = {
        x: Math.round(position.x / GRID) * GRID,
        y: Math.round(position.y / GRID) * GRID,
      };
    }

    const layout = blockRegistry?.[type];
    if (!layout) return;

    // Populate default property values
    const initialProps: Record<string, any> = {};
    layout.dataIns.forEach((p: any) => {
      if (p.defaultVal !== undefined) {
        initialProps[p.name] = p.defaultVal;
      }
    });

    // Special cases
    if (type === 'constants/number') initialProps.value = 1.0;
    if (type === 'constants/string') initialProps.value = '';
    if (type === 'logic/compare') initialProps.operator = '==';
    if (type === 'control_flow/loops/for_loop') initialProps.Count = 5;
    if (type === 'constants/boolean') initialProps.value = false;
    if (type === 'control_flow/loops/while_loop') initialProps.Condition = false;
    if (type === 'outputs/basic/display' || type === 'control_flow/timing/measure_time') initialProps.results = { displayValue: '---' };
    if (type === 'Lists/manipulation/accumulate' || type === 'Numeric Arrays/manipulation/accumulate') initialProps.results = { displayValue: '[]' };
    if (type && type.startsWith('script/')) {
      const getLangCode = (t: string) => {
        switch (t) {
          case 'script/lua':
            return `-- @input name="value" type="number" default=1.0\n-- @output name="result" type="number"\n\nresult = value * 2\n`;
          case 'script/julia':
            return `# @input name="value" type="number" default=1.0\n# @output name="result" type="number"\n\nresult = value * 2\n`;
          case 'script/javascript':
            return `// @input name="value" type="number" default=1.0\n// @output name="result" type="number"\n\nresult = value * 2;\n`;
          case 'script/typescript':
            return `// @input name="value" type="number" default=1.0\n// @output name="result" type="number"\n\nconst val: number = value;\nresult = val * 2;\n`;
          case 'script/rust':
            return `// @input name="value" type="number" default=1.0\n// @output name="result" type="number"\n\nresult = value * 2.0;\n`;
          case 'script/r':
            return `# @input name="value" type="number" default=1.0\n# @output name="result" type="number"\n\nresult <- value * 2\n`;
          case 'script/octave':
            return `% @input name="value" type="number" default=1.0\n% @output name="result" type="number"\n\nresult = value * 2;\n`;
          case 'script/wolfram':
            return `(* @input name="value" type="number" default=1.0 *)\n(* @output name="result" type="number" *)\n\nresult = value * 2;\n`;
          case 'script/sage':
          case 'script/sagemath':
            return `# @input name="value" type="number" default=1.0\n# @output name="result" type="number"\n\nresult = value * 2\n`;
          case 'script/maxima':
            return `/* @input name="value" type="number" default=1.0 */\n/* @output name="result" type="number" */\n\nresult: value * 2;\n`;
          case 'script/powershell':
          case 'script/pwsh':
            return `# @input name="value" type="number" default=1.0\n# @output name="result" type="number"\n\n$result = $value * 2\n`;
          case 'script/csharp':
          case 'script/cs':
          case 'script/dotnet':
            return `// @input name="value" type="number" default=1.0\n// @output name="result" type="number"\n\nresult = value * 2;\n`;
          case 'script/python':
          default:
            return `# @input name="value" type="number" default=1.0\n# @output name="result" type="number"\n\nresult = value * 2\n`;
        }
      };
      initialProps.code = getLangCode(type);
      initialProps.customInputs = [{ name: 'value', type: 'number', default: 1.0 }];
      initialProps.customOutputs = [{ name: 'result', type: 'number' }];
    }


    const newBlockId = getId();
    const newBlock: Node = {
      id: newBlockId,
      type: 'actionNode',
      position,
      data: getBaseBlockData({
        action: type,
        ...initialProps
      }),
      style: (blockRegistry?.[type]?.defaultWidth && blockRegistry?.[type]?.defaultHeight)
        ? { width: blockRegistry[type].defaultWidth, height: blockRegistry[type].defaultHeight }
        : {
            width: 210,
            minHeight: (type && type.startsWith('script/')) ? 220 : 160
          },
    };

    setBlocks((nds) => nds.concat(newBlock));
    return newBlockId;
  }, [reactFlowInstance, blockRegistry, pushStateToHistory, getBaseBlockData, snapToGrid, setBlocks, isLocked]);

  const handleQuickConnect = useCallback((menu: any, createType: string) => {
    setQuickConnectMenu(null);
    const { clientX, clientY, sourceBlockId, sourceHandleId, sourceHandleType } = menu;

    const sourceBlock = blocksRef.current.find((n: any) => n.id === sourceBlockId);
    if (!sourceBlock) return;
    const layout = blockRegistry?.[sourceBlock.data.action];
    if (!layout) return;

    let dataType = 'any';
    if (sourceHandleType === 'source') {
      const pin = layout.dataOuts?.find((p: any) => p.name === sourceHandleId);
      if (pin) dataType = pin.type || 'any';
    } else {
      const pin = layout.dataIns?.find((p: any) => p.name === sourceHandleId);
      if (pin) dataType = pin.type || 'any';
    }

    const newBlockId = addBlockAtClientPosition(createType, clientX, clientY);
    if (newBlockId) {
      setTimeout(() => {
        const newLayout = registryRef.current?.[createType];
        if (!newLayout) return;

        const edgeColor = getPinColor(dataType);

        const newEdge = {
          id: `edge_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
          source: sourceHandleType === 'source' ? sourceBlockId : newBlockId,
          sourceHandle: sourceHandleType === 'source' ? sourceHandleId : newLayout.dataOuts?.[0]?.name,
          target: sourceHandleType === 'source' ? newBlockId : sourceBlockId,
          targetHandle: sourceHandleType === 'source' ? newLayout.dataIns?.[0]?.name : sourceHandleId,
          style: { stroke: edgeColor, strokeWidth: 1.5, animated: false },
          markerEnd: { type: MarkerType.ArrowClosed, color: edgeColor },
          type: 'default',
        };

        setEdges((eds: any) => [...eds, newEdge]);
      }, 100);
    }
  }, [blockRegistry, setEdges, addBlockAtClientPosition]);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      if (isLocked) return;
      event.preventDefault();
      const type = event.dataTransfer.getData('application/reactflow');
      if (!type) return;
      addBlockAtClientPosition(type, event.clientX, event.clientY);
    },
    [addBlockAtClientPosition, isLocked]
  );

  const handleReplaceBlock = useCallback((blockId: string, replacementAction: string) => {
    pushStateToHistory();
    setIsDirty(true);

    const schema = blockRegistry?.[replacementAction];
    if (!schema) return;

    const newBaseData = getBaseBlockData({
      action: replacementAction,
    });

    setBlocks((nds) =>
      nds.map((n) => {
        if (n.id === blockId) {
          const oldSchema = blockRegistry?.[n.data?.action];
          const isDefaultName = !n.data?.customName || n.data.customName === oldSchema?.name || n.data.customName === n.data?.action;
          const customName = isDefaultName ? schema.name : n.data?.customName;
          return {
            ...n,
            data: {
              ...n.data,
              ...newBaseData,
              action: replacementAction,
              customName: customName,
            },
          };
        }
        return n;
      })
    );

    const newExecIns = schema.execIns || [];
    const newExecOuts = schema.execOuts || [];
    const newDataIns = (schema.dataIns || []).map((p: any) => p.name);
    const newDataOuts = (schema.dataOuts || []).map((p: any) => p.name);

    setEdges((eds) =>
      eds.filter((edge) => {
        if (edge.target === blockId) {
          const pin = edge.targetHandle || '';
          return newExecIns.includes(pin) || newDataIns.includes(pin);
        }
        if (edge.source === blockId) {
          const pin = edge.sourceHandle || '';
          return newExecOuts.includes(pin) || newDataOuts.includes(pin);
        }
        return true;
      })
    );
  }, [blockRegistry, getBaseBlockData, setBlocks, setEdges, pushStateToHistory]);

  const handleDeleteBlockFromMenu = useCallback((id: string) => {
    pushStateToHistory();
    setIsDirty(true);
    const selectedIds = new Set(blocks.filter(n => n.selected).map(n => n.id));
    if (!selectedIds.has(id)) {
      selectedIds.add(id);
    }
    setBlocks(nds => nds.filter(n => !selectedIds.has(n.id)));
    setEdges(eds => eds.filter(edge => !selectedIds.has(edge.source) && !selectedIds.has(edge.target)));
    setSelectedBlockIds(new Set());
  }, [blocks, setBlocks, setEdges, pushStateToHistory]);

  const handleDeleteEdgeFromMenu = useCallback((id: string) => {
    pushStateToHistory();
    setIsDirty(true);
    setEdges(eds => eds.filter(e => e.id !== id));
  }, [setEdges, pushStateToHistory]);

  const onPaneContextMenu = useCallback(
    (event: any) => {
      event.preventDefault();
      if (!reactFlowWrapper.current) return;
      const rect = reactFlowWrapper.current.getBoundingClientRect();
      setContextMenu({
        show: true,
        x: event.clientX - rect.left,
        y: event.clientY - rect.top,
        clientX: event.clientX,
        clientY: event.clientY,
        type: 'pane',
      });
    },
    []
  );

  const onBlockContextMenu = useCallback(
    (event: any, block: any) => {
      event.preventDefault();
      if (!reactFlowWrapper.current) return;
      const rect = reactFlowWrapper.current.getBoundingClientRect();

      setBlocks((nds) =>
        nds.map((n) => {
          if (n.id === block.id) {
            return { ...n, selected: true };
          }
          return event.shiftKey ? n : { ...n, selected: n.selected };
        })
      );

      setContextMenu({
        show: true,
        x: event.clientX - rect.left,
        y: event.clientY - rect.top,
        clientX: event.clientX,
        clientY: event.clientY,
        type: 'block',
        targetId: block.id,
      });
    },
    [setBlocks]
  );

  const onSelectionContextMenu = useCallback(
    (event: any, _nodes: any) => {
      event.preventDefault();
      if (!reactFlowWrapper.current) return;
      const rect = reactFlowWrapper.current.getBoundingClientRect();

      setContextMenu({
        show: true,
        x: event.clientX - rect.left,
        y: event.clientY - rect.top,
        clientX: event.clientX,
        clientY: event.clientY,
        type: 'selection',
        targetId: null,
      });
    },
    []
  );

  const onEdgeContextMenu = useCallback(
    (event: any, edge: any) => {
      event.preventDefault();
      if (!reactFlowWrapper.current) return;
      const rect = reactFlowWrapper.current.getBoundingClientRect();

      setContextMenu({
        show: true,
        x: event.clientX - rect.left,
        y: event.clientY - rect.top,
        clientX: event.clientX,
        clientY: event.clientY,
        type: 'edge',
        targetId: edge.id,
      });
    },
    []
  );

  const handleWrapperMouseDown = useCallback((event: React.MouseEvent) => {
    if (canvasMode !== 'cut' || event.button !== 0) return;
    
    // Prevent cutting when the user clicks on a block, handle, or controls to drag/connect
    const target = event.target as HTMLElement;
    if (target.closest('.react-flow__node') || target.closest('.react-flow__handle') || target.closest('.react-flow__controls')) {
      return;
    }

    if (!reactFlowWrapper.current) return;
    const rect = reactFlowWrapper.current.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    setCutterPath([{ x, y }]);
    setIsCutting(true);
    closeContextMenu();
  }, [canvasMode, closeContextMenu]);

  // Global mouse handlers for the Left-Click Slicer (Cut Mode)
  useEffect(() => {
    if (!isCutting) return;

    const handleGlobalMouseMove = (event: MouseEvent) => {
      if (!reactFlowWrapper.current) return;
      const rect = reactFlowWrapper.current.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      setCutterPath((prev) => (prev ? [...prev, { x, y }] : null));
    };

    const handleGlobalMouseUp = () => {
      if (!cutterPath) return;
      setIsCutting(false);

      if (cutterPath.length > 1) {
        if (!reactFlowWrapper.current) return;
        const rect = reactFlowWrapper.current.getBoundingClientRect();
        const edgeElements = document.querySelectorAll('.react-flow__edge');
        const edgesToCut: string[] = [];

        edgeElements.forEach((edgeEl) => {
          const edgeId = edgeEl.getAttribute('data-id');
          if (!edgeId) return;

          const pathEl = edgeEl.querySelector('.react-flow__edge-path') as SVGPathElement;
          if (!pathEl) return;

          const svg = pathEl.ownerSVGElement;
          if (!svg) return;
          const matrix = pathEl.getScreenCTM();
          if (!matrix) return;

          const pathLength = pathEl.getTotalLength();
          const numSamples = 20;
          const edgePoints: { x: number; y: number }[] = [];

          for (let i = 0; i <= numSamples; i++) {
            const sampleLength = (i / numSamples) * pathLength;
            const pt = svg.createSVGPoint();
            const p = pathEl.getPointAtLength(sampleLength);
            pt.x = p.x;
            pt.y = p.y;
            const screenPt = pt.matrixTransform(matrix);
            edgePoints.push({
              x: screenPt.x - rect.left,
              y: screenPt.y - rect.top,
            });
          }

          let intersected = false;
          for (let j = 0; j < cutterPath.length - 1; j++) {
            for (let k = 0; k < edgePoints.length - 1; k++) {
              if (lineSegmentsIntersect(cutterPath[j], cutterPath[j + 1], edgePoints[k], edgePoints[k + 1])) {
                intersected = true;
                break;
              }
            }
            if (intersected) break;
          }

          if (intersected) {
            edgesToCut.push(edgeId);
          }
        });

        if (edgesToCut.length > 0) {
          pushStateToHistory();
          setIsDirty(true);
          setEdges((eds) => eds.filter((edge) => !edgesToCut.includes(edge.id)));
        }
      }
      setCutterPath(null);
    };

    window.addEventListener('mousemove', handleGlobalMouseMove);
    window.addEventListener('mouseup', handleGlobalMouseUp);

    return () => {
      window.removeEventListener('mousemove', handleGlobalMouseMove);
      window.removeEventListener('mouseup', handleGlobalMouseUp);
    };
  }, [isCutting, cutterPath, setEdges, pushStateToHistory]);



  // Group selected blocks into a cluster
  const handleGroupIntoCluster = useCallback(async () => {
    if (selectedBlockIds.size < 2) {
      await alertAsync(t('app.alertGroupClusterSelect', 'Select at least 2 blocks on the canvas to group into a cluster.\n\nClick blocks while holding Shift, or drag a selection box.'));
      return;
    }

    const boundary = detectBoundaryPins(selectedBlockIds, blocks, edges, blockRegistry);
    setDetectedBoundary(boundary);
    setSelectedForCluster(Array.from(selectedBlockIds));
    setCreateClusterOpen(true);
  }, [selectedBlockIds, blocks, edges, blockRegistry]);

  // Collapse selected blocks into a single cluster block on the canvas
  const collapseIntoClusterNode = useCallback((typeName: string, clusterNodeData: any) => {
    if (selectedBlockIds.size === 0) return;

    pushStateToHistory();
    setIsDirty(true);

    const boundary = detectBoundaryPins(selectedBlockIds, blocks, edges, blockRegistry);

    // Calculate bounding box center
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    const selNodes = blocks.filter((n: any) => selectedBlockIds.has(n.id));
    selNodes.forEach((n: any) => {
      minX = Math.min(minX, n.position.x);
      minY = Math.min(minY, n.position.y);
      let w = typeof n.width === 'number' ? n.width : parseFloat(n.style?.width);
      if (isNaN(w)) w = 210;
      let h = typeof n.height === 'number' ? n.height : parseFloat(n.style?.minHeight || n.style?.height);
      if (isNaN(h)) h = 160;
      maxX = Math.max(maxX, n.position.x + w);
      maxY = Math.max(maxY, n.position.y + h);
    });
    
    if (!isFinite(minX)) minX = 0;
    if (!isFinite(minY)) minY = 0;
    if (!isFinite(maxX)) maxX = 210;
    if (!isFinite(maxY)) maxY = 160;

    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;

    // Create cluster block
    const clusterNodeId = getId();
    const clusterNode: any = {
      id: clusterNodeId,
      type: 'actionNode',
      position: { x: centerX - 105, y: centerY - 80 },
      data: getBaseBlockData({
        action: typeName,
        ...clusterNodeData,
      }),
      style: {
        width: 230,
        minHeight: 180,
      },
    };

    // Build new edges: keep edges that are external to the selection, reconnect boundary edges
    const newEdges = edges.filter((edge: any) => {
      const srcInside = selectedBlockIds.has(edge.source);
      const tgtInside = selectedBlockIds.has(edge.target);
      // Keep edges where both ends are outside
      if (!srcInside && !tgtInside) return true;
      // Remove edges where both ends are inside
      if (srcInside && tgtInside) return false;
      // Boundary edges are recreated below
      return false;
    });

    // Recreate boundary edges
    boundary.data_ins.forEach((pin: any) => {
      const origEdge = edges.find((e: any) => e.target === pin.maps_to.block_id && e.targetHandle === pin.maps_to.pin);
      if (origEdge) {
        newEdges.push({
          id: `cluster_bdi_${origEdge.id}`,
          type: origEdge.type || 'default',
          source: origEdge.source,
          sourceHandle: origEdge.sourceHandle,
          target: clusterNodeId,
          targetHandle: pin.name,
          style: origEdge.style,
          markerEnd: origEdge.markerEnd,
        });
      }
    });

    boundary.exec_ins.forEach((pin: any) => {
      const origEdge = edges.find((e: any) => e.target === pin.maps_to.block_id && e.targetHandle === pin.maps_to.pin);
      if (origEdge) {
        newEdges.push({
          id: `cluster_ei_${origEdge.id}`,
          type: origEdge.type || 'default',
          source: origEdge.source,
          sourceHandle: origEdge.sourceHandle,
          target: clusterNodeId,
          targetHandle: pin.name,
          style: origEdge.style,
          markerEnd: origEdge.markerEnd,
        });
      }
    });

    boundary.data_outs.forEach((pin: any) => {
      const origEdge = edges.find((e: any) => e.source === pin.maps_from.block_id && e.sourceHandle === pin.maps_from.pin);
      if (origEdge) {
        newEdges.push({
          id: `cluster_bdo_${origEdge.id}`,
          type: origEdge.type || 'default',
          source: clusterNodeId,
          sourceHandle: pin.name,
          target: origEdge.target,
          targetHandle: origEdge.targetHandle,
          style: origEdge.style,
          markerEnd: origEdge.markerEnd,
        });
      }
    });

    boundary.exec_outs.forEach((pin: any) => {
      const origEdge = edges.find((e: any) => e.source === pin.maps_from.block_id && e.sourceHandle === pin.maps_from.pin);
      if (origEdge) {
        newEdges.push({
          id: `cluster_eo_${origEdge.id}`,
          type: origEdge.type || 'default',
          source: clusterNodeId,
          sourceHandle: pin.name,
          target: origEdge.target,
          targetHandle: origEdge.targetHandle,
          style: origEdge.style,
          markerEnd: origEdge.markerEnd,
        });
      }
    });

    // Remove selected blocks and add cluster block
    const remainingNodes = blocks.filter((n: any) => !selectedBlockIds.has(n.id));
    remainingNodes.push(clusterNode);

    setBlocks(remainingNodes);
    setEdges(newEdges);
    setCreateClusterOpen(false);
  }, [blocks, edges, blockRegistry, selectedBlockIds, getBaseBlockData, setBlocks, setEdges, pushStateToHistory]);


  const handleSaveBlueprint = useCallback(async () => {
    const curLevelIndex = currentLevelIndexRef.current;
    if (curLevelIndex > 0) {
      await saveCurrentClusterEdits();
    }
    const payload = getSavePayload();
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = (currentBlueprintName || 'comfylab_blueprint') + '.json';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    setIsDirty(false);
  }, [currentBlueprintName, getSavePayload, saveCurrentClusterEdits]);
  const loadBlueprintData = (payload: any, filename: string, isExample: boolean = false) => {
    const restoredNodes = payload.blocks.map((block: any) => ({
      ...block,
      data: getBaseBlockData({
        ...block.data,
      })
    }));
    setBlocks(restoredNodes);
    setEdges(rewriteEdgeStyles(payload.edges));
    setAnnotations(payload.annotations || []);
    setErrorMessage(null);
    setLoadWorkspaceOpen(false);
    const nameWithoutExt = filename.replace(/\.json$/, '');
    setCurrentBlueprintName(nameWithoutExt);
    setIsExampleBlueprint(isExample);
    setIsDirty(false);
    if (payload.viewport && payload.viewport.x !== undefined && payload.viewport.y !== undefined && payload.viewport.zoom !== undefined) {
      if (reactFlowInstance) {
        reactFlowInstance.setViewport(payload.viewport, { duration: 0 });
      }
      setShouldFitView(false);
    } else {
      setShouldFitView(true);
    }

    // Restore dashboard items
    if (payload.dashboard && Array.isArray(payload.dashboard.items)) {
      setDashboardItems(payload.dashboard.items);
      if (payload.dashboard.width) {
        dashboardResizer.setWidth(payload.dashboard.width);
      }
    } else {
      const reconstructed: DashboardItem[] = [];
      restoredNodes.forEach((node: any) => {
        if (node.data?.inDashboard) {
          reconstructed.push({ id: `dash_${node.id}`, blockId: node.id, type: 'block' });
        }
        if (Array.isArray(node.data?.dashboardPins)) {
          node.data.dashboardPins.forEach((p: string) => {
            reconstructed.push({ id: `dash_${node.id}_${p}`, blockId: node.id, type: 'pin', pinName: p });
          });
        }
      });
      setDashboardItems(reconstructed);
    }

    fetchRegistry();
  };


  const handleBlueprintUpload = (file: File) => {
    const reader = new FileReader();
    reader.onload = async (e) => {
      try {
        const content = e.target?.result as string;
        const payload = JSON.parse(content);
        if (payload.blocks && Array.isArray(payload.blocks) && payload.edges && Array.isArray(payload.edges)) {
          // Check origin
          const originUuid = payload.creator_identity || payload.origin_uuid;
          const isOriginTrusted = originUuid && 
                                  (originUuid === settings.creator_identity || 
                                  (settings.trusted_origins && settings.trusted_origins.includes(originUuid)));
          
          if (!isOriginTrusted) {
            const warningMsg = !originUuid 
              ? "This blueprint has no creator metadata (unknown source). It may contain custom scripts. Do you trust this blueprint and want to load it?"
              : `This blueprint was created by a developer/source with identity: ${originUuid}. It may contain custom scripts. Do you trust this developer and want to load it?`;
            setTrustWarningMessage(warningMsg);
            setPendingBlueprint({ ...payload, origin_uuid: originUuid });
            setPendingFilename(file.name.replace(/\.json$/, ''));
            setTrustWarningOpen(true);
            return;
          }
          
          loadBlueprintData(payload, file.name.replace(/\.json$/, ''));
        } else {
          await alertAsync(t('app.alertInvalidBlueprint', 'Invalid blueprint format.'));
        }
      } catch (err) {
        await alertAsync(t('app.alertFailedParseJSON', 'Failed to parse blueprint JSON.'));
      }
    };
    reader.readAsText(file);
  };

  const handleLoadBlueprint = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    handleBlueprintUpload(file);
    event.target.value = '';
  };


  const handleOpenPackage = async (filename: string) => {
    try {
      const res = await axios.post(`${BACKEND_URL}/workspace/packages/load`, { filename });
      setPackageFilename(filename);
      setPackagePreviewData(res.data);
      setImportPermanent(false);
      setLoadWorkspaceOpen(false); // Close load list modal
      setPackageImportOpen(true); // Open import preview modal
    } catch (err: any) {
      setErrorMessage(err.response?.data?.detail || 'Failed to load package preview.');
    }
  };

  const handleImportPackage = async () => {
    try {
      await axios.post(`${BACKEND_URL}/workspace/packages/import`, {
        package_filename: packageFilename,
        destination: importDestination,
        trust_and_sign: trustAndSign,
        delete_package: deletePackageAfterImport,
        import_permanent: importPermanent
      });
      setPackageImportOpen(false);
      
      // Load the blueprint that was imported
      const bpFilename = importPermanent
        ? packageFilename.replace(/\.cfy$/, '.json')
        : `.temp/${packageFilename.replace(/\.cfy$/, '.json')}`;
      await handleLoadBlueprintByName(bpFilename);
      
      // Refresh list & counts
      await fetchWorkspaceBlueprints();
      
      // Refresh sidebar block templates
      const templatesRes = await axios.get(`${BACKEND_URL}/blocks`);
      setBlockRegistry(templatesRes.data);
      
      console.log(`Successfully imported package: ${packageFilename}`);
    } catch (err: any) {
      setErrorMessage(err.response?.data?.detail || 'Failed to import package.');
    }
  };


  const triggerLoadFromWorkspace = async () => {
    await fetchWorkspaceBlueprints();
    setLoadWorkspaceOpen(true);
  };

  const handleLoadBlueprintByName = async (filename: string) => {
    try {
      const loadRes = await axios.get(`${BACKEND_URL}/workspace/blueprints/${encodeURIComponent(filename)}`);
      const payload = loadRes.data;
      if (payload.blocks && Array.isArray(payload.blocks) && payload.edges && Array.isArray(payload.edges)) {
        if (payload.origin_trusted === false) {
          setTrustWarningMessage(payload.origin_warning || "This blueprint is from another origin.");
          setPendingBlueprint(payload);
          setPendingFilename(filename);
          setTrustWarningOpen(true);
          return;
        }
        loadBlueprintData(payload, filename);
      } else {
        await alertAsync(t('app.alertInvalidWorkspaceBlueprint', 'Invalid blueprint format in workspace file.'));
      }
    } catch (err: any) {
      setErrorMessage(err.response?.data?.detail || 'Failed to load blueprint from workspace.');
    }
  };

  const handleLoadExampleByName = async (filename: string) => {
    try {
      const loadRes = await axios.get(`${BACKEND_URL}/workspace/examples/${encodeURIComponent(filename)}`);
      const payload = loadRes.data;
      const bpData = payload.blueprint || payload;
      if (bpData.blocks && Array.isArray(bpData.blocks) && bpData.edges && Array.isArray(bpData.edges)) {
        loadBlueprintData(bpData, `[Example] ${filename}`, true);
      } else {
        await alertAsync(t('app.alertInvalidExampleBlueprint', 'Invalid example blueprint format.'));
      }
    } catch (err: any) {
      setErrorMessage(err.response?.data?.detail || 'Failed to load example blueprint.');
    }
  };

  const handleDeleteBlueprint = async (filename: string, isPackage?: boolean) => {
    try {
      if (isPackage) {
        await axios.delete(`${BACKEND_URL}/workspace/packages/${encodeURIComponent(filename)}`);
      } else {
        await axios.delete(`${BACKEND_URL}/workspace/blueprints/${encodeURIComponent(filename)}`);
      }
      await fetchWorkspaceBlueprints();
    } catch (err: any) {
      setErrorMessage(err.response?.data?.detail || 'Failed to delete blueprint/package.');
    }
  };

  const handleOpenBlueprintsExplorer = async () => {
    try {
      await axios.post(`${BACKEND_URL}/workspace/blueprints/open-explorer`);
    } catch (err: any) {
      setErrorMessage(err.response?.data?.detail || 'Failed to open explorer.');
    }
  };

  const triggerSaveToWorkspace = () => {
    const curLevelIndex = currentLevelIndexRef.current;
    const rootNodes = curLevelIndex === 0 ? blocks : (canvasStackRef.current[0]?.savedNodes || []);
    if (rootNodes.length === 0) return;
    const initialName = isExampleBlueprint
      ? (currentBlueprintName || '').replace(/^\[Example\]\s*/, '')
      : (currentBlueprintName || '');
    setSaveFilenameInput(initialName);
    setSaveWorkspaceOpen(true);
  };

  const handleOverwriteToWorkspace = async () => {
    const curLevelIndex = currentLevelIndexRef.current;
    const rootNodes = curLevelIndex === 0 ? blocks : (canvasStackRef.current[0]?.savedNodes || []);
    if (!currentBlueprintName || rootNodes.length === 0) return;

    if (isExampleBlueprint) {
      triggerSaveToWorkspace();
      return;
    }

    if (curLevelIndex > 0) {
      await saveCurrentClusterEdits();
    }

    const payload = getSavePayload();

    try {
      await axios.post(`${BACKEND_URL}/workspace/blueprints`, {
        filename: currentBlueprintName,
        blueprint: payload
      });
      setErrorMessage(null);
      setIsDirty(false);
      console.log(`Successfully saved to workspace as "${currentBlueprintName}.json"`);
    } catch (err: any) {
      setErrorMessage(err.response?.data?.detail || 'Failed to overwrite blueprint in workspace.');
    }
  };

  const handleSaveToWorkspaceWithFilename = async () => {
    const curLevelIndex = currentLevelIndexRef.current;
    const rootNodes = curLevelIndex === 0 ? blocks : (canvasStackRef.current[0]?.savedNodes || []);
    if (rootNodes.length === 0) return;
    const trimmed = saveFilenameInput.trim();
    if (!trimmed) {
      await alertAsync(t('app.alertEnterFilename', 'Please enter a filename.'));
      return;
    }

    if (curLevelIndex > 0) {
      await saveCurrentClusterEdits();
    }

    const payload = getSavePayload();

    try {
      const nameWithoutExt = trimmed.replace(/\.json$/, '').replace(/\.cfy$/, '');
      if (exportAsPackage) {
        await axios.post(`${BACKEND_URL}/workspace/packages`, {
          filename: nameWithoutExt,
          blueprint: payload
        });
        console.log(`Successfully exported package as "${nameWithoutExt}.cfy"`);
        setErrorMessage(null);
        setSaveWorkspaceOpen(false);
      } else {
        await axios.post(`${BACKEND_URL}/workspace/blueprints`, {
          filename: nameWithoutExt,
          blueprint: payload
        });
        setErrorMessage(null);
        setSaveWorkspaceOpen(false);
        setCurrentBlueprintName(nameWithoutExt);
        setIsExampleBlueprint(false);
        setIsDirty(false);
      }
    } catch (err: any) {
      setErrorMessage(err.response?.data?.detail || 'Failed to save blueprint to workspace.');
    }
  };


  const handleSetWorkspace = async () => {
    if (!workspaceInput.trim()) return;
    try {
      const res = await axios.post(`${BACKEND_URL}/workspace`, { path: workspaceInput.trim() });
      setWorkspacePath(res.data.path);
      setEditingWorkspace(false);
      setErrorMessage(null);
      
      const updatedSettings = {
        ...settings,
        last_workspace: res.data.path
      };
      await handleSaveSettings(updatedSettings);
    } catch (err: any) {
      setErrorMessage(err.response?.data?.detail || 'Failed to set workspace.');
    }
  };



  // --- TAB MANAGEMENT OPERATIONS ---
  const switchTab = useCallback((targetTabId: string) => {
    if (targetTabId === activeTabId) return;

    // 1. Save current active tab state to tabs array
    const currentViewport = reactFlowInstance ? reactFlowInstance.getViewport() : viewport;
    const updatedTabs = tabsRef.current.map(t => {
      if (t.id === activeTabId) {
        return {
          ...t,
          name: currentBlueprintName || t.name,
          blocks: blocksRef.current,
          edges: edgesRef.current,
          annotations: annotationsRef.current,
          isDirty: isDirty,
          past: [...pastRef.current],
          future: [...futureRef.current],
          canvasStack: canvasStackRef.current,
          currentLevelIndex: currentLevelIndexRef.current,
          viewport: currentViewport,
          dashboard: {
            items: dashboardItemsRef.current,
            width: dashboardResizer.width,
          },
        };
      }
      return t;
    });

    tabsRef.current = updatedTabs;
    setTabs(updatedTabs);

    // 2. Retrieve target tab state from updatedTabs
    const targetTab = updatedTabs.find(t => t.id === targetTabId);
    if (targetTab) {
      // 3. Load target tab state into active states
      setBlocks(targetTab.blocks || []);
      setEdges(targetTab.edges || []);
      setAnnotations(targetTab.annotations || []);
      setCurrentBlueprintName(targetTab.name === 'Untitled' ? '' : targetTab.name);
      setIsDirty(targetTab.isDirty);
      
      pastRef.current = targetTab.past || [];
      futureRef.current = targetTab.future || [];
      
      setCanvasStack(targetTab.canvasStack || [{ breadcrumbLabel: 'Main', type: 'main' }]);
      setCurrentLevelIndex(targetTab.currentLevelIndex || 0);
      
      setActiveTabId(targetTabId);

      // Restore target tab dashboard
      setDashboardItems(targetTab.dashboard?.items || []);
      if (targetTab.dashboard?.width) {
        dashboardResizer.setWidth(targetTab.dashboard.width);
      }

      // 4. Restore target tab viewport
      if (reactFlowInstance) {
        const targetViewport = targetTab.viewport || { x: 50, y: 50, zoom: 0.9 };
        reactFlowInstance.setViewport(targetViewport, { duration: 0 });
      }
    }
  }, [activeTabId, currentBlueprintName, isDirty, annotations, setAnnotations, reactFlowInstance, viewport, dashboardResizer.width]);

  const addTab = useCallback(() => {
    // 1. Save current active tab state to tabs array first
    const currentViewport = reactFlowInstance ? reactFlowInstance.getViewport() : viewport;
    const updatedTabs = tabsRef.current.map(t => {
      if (t.id === activeTabId) {
        return {
          ...t,
          name: currentBlueprintName || t.name,
          blocks: blocksRef.current,
          edges: edgesRef.current,
          annotations: annotationsRef.current,
          isDirty: isDirty,
          past: [...pastRef.current],
          future: [...futureRef.current],
          canvasStack: canvasStackRef.current,
          currentLevelIndex: currentLevelIndexRef.current,
          viewport: currentViewport,
          dashboard: {
            items: dashboardItemsRef.current,
            width: dashboardResizer.width,
          },
        };
      }
      return t;
    });

    // 2. Create and switch to new tab
    const newTabId = `tab_${Date.now()}`;
    const defaultViewport = { x: 50, y: 50, zoom: 0.9 };
    const newTab: Tab = {
      id: newTabId,
      name: 'Untitled',
      blocks: [],
      edges: [],
      annotations: [],
      isDirty: false,
      past: [],
      future: [],
      canvasStack: [{ breadcrumbLabel: 'Main', type: 'main' }],
      currentLevelIndex: 0,
      viewport: defaultViewport,
      dashboard: { items: [], width: dashboardResizer.width },
    };

    const finalTabs = [...updatedTabs, newTab];
    tabsRef.current = finalTabs;
    setTabs(finalTabs);
    setActiveTabId(newTabId);

    // Reset active states for the new tab
    setBlocks([]);
    setEdges([]);
    setDashboardItems([]);

    setAnnotations([]);
    setCurrentBlueprintName('');
    setIsDirty(false);
    pastRef.current = [];
    futureRef.current = [];
    setCanvasStack([{ breadcrumbLabel: 'Main', type: 'main' }]);
    setCurrentLevelIndex(0);

    if (reactFlowInstance) {
      reactFlowInstance.setViewport(defaultViewport, { duration: 0 });
    }
  }, [activeTabId, currentBlueprintName, isDirty, annotations, setAnnotations, reactFlowInstance, viewport]);

  const closeTab = useCallback(async (tabIdToClose: string, event?: React.MouseEvent) => {
    if (event) {
      event.stopPropagation(); // Prevent tab switching when clicking close button
    }

    // Find tab to close
    const tabToClose = tabs.find(t => t.id === tabIdToClose);
    if (!tabToClose) return;

    // Check if it's dirty
    const isTabDirty = tabIdToClose === activeTabId ? isDirty : tabToClose.isDirty;
    if (isTabDirty) {
      const confirmClose = await confirmAsync(
        t('app.confirmCloseUnsaved', 'Are you sure you want to close this tab? Unsaved changes in "{{name}}" will be lost.', { name: tabToClose.name })
      );
      if (!confirmClose) return;
    }

    // If it's the running tab, warn or handle
    if (tabIdToClose === runningTabId) {
      const confirmRunning = await confirmAsync(
        t('app.confirmCloseRunning', 'This blueprint is currently executing. Closing the tab will stop the execution. Continue?')
      );
      if (!confirmRunning) return;
      handleAbort(); // Abort the execution
    }

    // Get remaining tabs
    const remainingTabs = tabs.filter(t => t.id !== tabIdToClose);

    if (remainingTabs.length === 0) {
      // If no tabs remain, create a new "Untitled" tab automatically
      const newTabId = `tab_${Date.now()}`;
      const defaultViewport = { x: 50, y: 50, zoom: 0.9 };
      const newTab: Tab = {
        id: newTabId,
        name: 'Untitled',
        blocks: [],
        edges: [],
        annotations: [],
        isDirty: false,
        past: [],
        future: [],
        canvasStack: [{ breadcrumbLabel: 'Main', type: 'main' }],
        currentLevelIndex: 0,
        viewport: defaultViewport
      };
      setTabs([newTab]);
      setActiveTabId(newTabId);
      setBlocks([]);
      setEdges([]);
      setAnnotations([]);
      setCurrentBlueprintName('');
      setIsDirty(false);
      pastRef.current = [];
      futureRef.current = [];
      setCanvasStack([{ breadcrumbLabel: 'Main', type: 'main' }]);
      setCurrentLevelIndex(0);
      if (reactFlowInstance) {
        reactFlowInstance.setViewport(defaultViewport, { duration: 0 });
      }
    } else {
      setTabs(remainingTabs);
      // If we closed the active tab, switch to another tab
      if (tabIdToClose === activeTabId) {
        // Find index of the closed tab
        const closedIndex = tabs.findIndex(t => t.id === tabIdToClose);
        // Switch to the tab to the left, or to the right if it was the first tab
        const nextActiveTab = remainingTabs[Math.max(0, closedIndex - 1)];
        
        // Switch states
        setBlocks(nextActiveTab.blocks);
        setEdges(nextActiveTab.edges);
        setAnnotations(nextActiveTab.annotations || []);
        setCurrentBlueprintName(nextActiveTab.name === 'Untitled' ? '' : nextActiveTab.name);
        setIsDirty(nextActiveTab.isDirty);
        pastRef.current = nextActiveTab.past || [];
        futureRef.current = nextActiveTab.future || [];
        setCanvasStack(nextActiveTab.canvasStack || [{ breadcrumbLabel: 'Main', type: 'main' }]);
        setCurrentLevelIndex(nextActiveTab.currentLevelIndex || 0);
        
        setActiveTabId(nextActiveTab.id);
        if (reactFlowInstance) {
          const nextViewport = nextActiveTab.viewport || { x: 50, y: 50, zoom: 0.9 };
          reactFlowInstance.setViewport(nextViewport, { duration: 0 });
        }
      }
    }
  }, [tabs, activeTabId, isDirty, runningTabId, setAnnotations, fetchRegistry, fetchWorkspaceBlueprints, reactFlowInstance]);

  // --- KEYBOARD LISTENER EFFECT ---
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        closeContextMenu();
        
        if (currentAnnotationRef.current && (currentAnnotationRef.current.type === 'polyline' || currentAnnotationRef.current.type === 'polygon')) {
          e.preventDefault();
          commitActivePolyshape();
          return;
        }

        if (canvasMode === 'draw') {
          if (editingTextId) {
            setEditingTextId(null);
          } else {
            setCanvasMode('select');
          }
        }
      }

      if (e.key === 'Enter') {
        if (currentAnnotationRef.current && (currentAnnotationRef.current.type === 'polyline' || currentAnnotationRef.current.type === 'polygon')) {
          e.preventDefault();
          commitActivePolyshape();
          return;
        }
      }

      const isCtrlOrMetaEarly = e.ctrlKey || e.metaKey;
      if (isCtrlOrMetaEarly) {
        const earlyKey = e.key.toLowerCase();
        if (earlyKey === 'r' && e.shiftKey) {
          e.preventDefault();
          if (isRunningRef.current) handleAbortRef.current();
          return;
        } else if (earlyKey === 'r') {
          e.preventDefault();
          if (!isRunningRef.current) {
            handleRunRef.current();
          } else if (isPausedRef.current) {
            handleResumeRef.current();
          } else {
            handlePauseRef.current();
          }
          return;
        }
      }

      const activeElement = document.activeElement;
      const isInputFocused = activeElement && (
        activeElement.tagName === 'INPUT' ||
        activeElement.tagName === 'TEXTAREA' ||
        activeElement.hasAttribute('contenteditable') ||
        activeElement.closest('.monaco-editor')
      );
      if (isInputFocused) return;

      // Tool mode shortcuts (1: Select, 2: Pan, 3: Cut, 4: Draw, d: Dashboard)
      if (!e.ctrlKey && !e.metaKey && !e.altKey && !e.shiftKey) {
        if (e.key === 'd' || e.key === 'D') {
          e.preventDefault();
          setDashboardOpen(prev => !prev);
          return;
        } else if (e.key === '1') {
          e.preventDefault();
          setCanvasMode('select');
        } else if (e.key === '2') {
          e.preventDefault();
          setCanvasMode('pan');
        } else if (e.key === '3') {
          e.preventDefault();
          setCanvasMode('cut');
        } else if (e.key === '4') {
          e.preventDefault();
          if (canvasMode !== 'draw') {
            setCanvasMode('draw');
            setShowAnnotations(true);
          } else {
            setCanvasMode('select');
          }
        }
      }

      if (e.key === 'Delete' || e.key === 'Backspace') {
        if (isLocked) return;
        if (canvasMode === 'draw' && drawTool === 'select' && selectedAnnotationId) {
          e.preventDefault();
          deleteSelectedAnnotation();
          return;
        }
        const selectedNodes = blocksRef.current.filter(n => n.selected);
        const selectedEdges = edgesRef.current.filter(e => e.selected);
        if (selectedNodes.length > 0 || selectedEdges.length > 0) {
          e.preventDefault();
          pushStateToHistory();
          setIsDirty(true);
          
          const selectedBlockIds = new Set(selectedNodes.map(n => n.id));
          setBlocks(nds => nds.filter(n => !selectedBlockIds.has(n.id)));
          setDashboardItems(prev => prev.filter(item => !selectedBlockIds.has(item.blockId)));
          setEdges(eds => eds.filter(edge => 
            !selectedEdges.some(se => se.id === edge.id) && 
            !selectedBlockIds.has(edge.source) && 
            !selectedBlockIds.has(edge.target)
          ));
          setSelectedBlockIds(new Set());
        }
      }


      const isCtrlOrMeta = e.ctrlKey || e.metaKey;
      if (isCtrlOrMeta) {
        const key = e.key.toLowerCase();
        if (key === 'z') {
          e.preventDefault();
          handleUndo();
        } else if (key === 'y') {
          e.preventDefault();
          handleRedo();
        } else if (key === 'c') {
          const selection = window.getSelection();
          if (selection && selection.toString().length > 0) return;
          e.preventDefault();
          handleCopy();
        } else if (key === 'v') {
          e.preventDefault();
          if (!isLocked) handlePaste();
        } else if (key === 'd') {
          e.preventDefault();
          if (!isLocked) handleDuplicate();
        } else if (key === 's') {
          e.preventDefault();
          if (e.shiftKey) {
            triggerSaveToWorkspace();
          } else {
            if (currentBlueprintName && !isExampleBlueprint) {
              handleOverwriteToWorkspace();
            } else {
              triggerSaveToWorkspace();
            }
          }
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [handleUndo, handleRedo, handleCopy, handlePaste, handleDuplicate, triggerSaveToWorkspace, handleOverwriteToWorkspace, currentBlueprintName, isExampleBlueprint, closeContextMenu, commitActivePolyshape, canvasMode, setCanvasMode, editingTextId, setEditingTextId, drawTool, selectedAnnotationId, deleteSelectedAnnotation, isLocked]);

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', width: '100vw', alignItems: 'center', justifyContent: 'center', background: '#090d16', color: '#60a5fa', fontFamily: 'sans-serif', gap: '16px' }}>
        <div style={{ border: '4px solid rgba(96, 165, 250, 0.1)', borderTop: '4px solid #60a5fa', borderRadius: '50%', width: '40px', height: '40px', animation: 'spin 1s linear infinite' }} />
        <style>{`
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
        `}</style>
        <div>Loading ComfyLAB Core Registry...</div>
      </div>
    );
  }

  // Group and filter categories into a recursive tree structure
  const filteredTree: Record<string, SidebarCategoryNode> = {};

  if (blockRegistry) {
    const query = searchQuery.toLowerCase().trim();
    Object.entries(blockRegistry).forEach(([type, nodeSchema]: [string, any]) => {
      const isDevice = Boolean(nodeSchema?.isDevice);
      const isConnected = isDevice && isBlockMatchingConnectedDevices({ type, ...nodeSchema }, connectedDevices);

      // If connected-only filter is active and this is an un-connected device block, skip it!
      if (connectedOnly && isDevice && !isConnected) {
        return;
      }

      const name = (getBlockTitle(nodeSchema) || nodeSchema.name || '').toLowerCase();
      const desc = (getBlockDescription(nodeSchema) || nodeSchema.description || '').toLowerCase();
      const catString = getBlockCategory(nodeSchema) || nodeSchema.category || 'Other';
      const parts: string[] = (catString || '').split(/(?<!\\)\//).map((p: string) => p.replace(/\\(\/)/g, '$1'));
      
      const isMatch = !query || 
                      name.includes(query) || 
                      desc.includes(query) || 
                      parts.some((p: string) => p.toLowerCase().includes(query));
      
      if (!isMatch) return;

      let currentLevel = filteredTree;
      parts.forEach((part: string, idx: number) => {
        if (!currentLevel[part]) {
          currentLevel[part] = { directNodes: [], children: {} };
        }
        if (idx === parts.length - 1) {
          currentLevel[part].directNodes.push({ type, ...nodeSchema, isDevice, isConnected });
        } else {
          currentLevel = currentLevel[part].children;
        }
      });
    });

    pruneEmptyCategories(filteredTree);
  }

  if (authRequired) {
    return (
      <RemoteAccessAuthPanel
        authInput={authInput}
        authError={authError}
        setAuthInput={setAuthInput}
        onSubmit={handleAuthSubmit}
      />
    );
  }

  return (
    <RegistryContext.Provider value={blockRegistry}>
      <SettingsContext.Provider value={settings}>
        <div className="app-container">
        {/* --- TOP BAR / TOOLBAR --- */}
        <TopBar
          menuOpen={menuOpen}
          setMenuOpen={setMenuOpen}
          currentBlueprintName={currentBlueprintName}
          isDirty={isDirty}
          workspacePath={workspacePath}
          workspaceInput={workspaceInput}
          setWorkspaceInput={setWorkspaceInput}
          editingWorkspace={editingWorkspace}
          setEditingWorkspace={setEditingWorkspace}
          handleSetWorkspace={handleSetWorkspace}
          isRunning={isRunning}
          isPaused={isPaused}
          runningTabName={tabs.find(t => t.id === runningTabId)?.name || 'Untitled'}
          blocksCount={blocks.length}
          selectedBlocksCount={blocks.filter(n => n.selected).length}
          theme={theme}
          setTheme={setTheme}
          liteMode={liteMode}
          onToggleLiteMode={() => setLiteMode(prev => !prev)}
          menuContainerRef={menuContainerRef}
          onNewBlueprint={async () => {
            setMenuOpen(false);
            if (await confirmAsync(t('app.confirmClearCanvas', 'Are you sure you want to clear the canvas and start a new blueprint?'))) {
              setBlocks([]);
              setEdges([]);
              setAnnotations([]);
              setCurrentBlueprintName('');
              setIsDirty(false);
              pastRef.current = [];
              futureRef.current = [];
              setCanvasStack([{ breadcrumbLabel: 'Main', type: 'main' }]);
              setCurrentLevelIndex(0);
              setErrorMessage(null);
              if (reactFlowInstance) {
                reactFlowInstance.setViewport({ x: 50, y: 50, zoom: 0.9 }, { duration: 0 });
              }
            }
          }}
          onSaveBlueprint={() => {
            setMenuOpen(false);
            triggerSaveToWorkspace();
          }}
          onOverwriteBlueprint={currentBlueprintName && !isExampleBlueprint ? () => {
            setMenuOpen(false);
            handleOverwriteToWorkspace();
          } : undefined}
          onLoadBlueprint={() => {
            setMenuOpen(false);
            triggerLoadFromWorkspace();
          }}
          onClearTemporaryFiles={async () => {
            setMenuOpen(false);
            if (await confirmAsync(t('app.confirmCleanTempFiles', 'Are you sure you want to delete all temporary package files, runtime temp files, and reload the registry? This will also close all open tabs running temporary package blueprints.'))) {
              try {
                await axios.post(`${BACKEND_URL}/workspace/packages/clear_temp`);
                await fetchRegistry();
                await fetchWorkspaceBlueprints();
                
                // Close all tabs running temporary package blueprints
                const isTempTab = (t: Tab) => t.name && (t.name.startsWith('.temp') || t.name.includes('.temp/'));
                const remainingTabs = tabs.filter(t => !isTempTab(t));
                
                const isRunningTemp = tabs.some(t => t.id === runningTabId && isTempTab(t));
                if (isRunningTemp) {
                  handleAbort();
                }
                
                const activeTab = tabs.find(t => t.id === activeTabId);
                const isActiveClosed = activeTab && isTempTab(activeTab);
                
                if (remainingTabs.length === 0) {
                  const newTabId = `tab_${Date.now()}`;
                  const defaultViewport = { x: 50, y: 50, zoom: 0.9 };
                  const newTab: Tab = {
                    id: newTabId,
                    name: 'Untitled',
                    blocks: [],
                    edges: [],
                    annotations: [],
                    isDirty: false,
                    past: [],
                    future: [],
                    canvasStack: [{ breadcrumbLabel: 'Main', type: 'main' }],
                    currentLevelIndex: 0,
                    viewport: defaultViewport
                  };
                  setTabs([newTab]);
                  setActiveTabId(newTabId);
                  setBlocks([]);
                  setEdges([]);
                  setAnnotations([]);
                  setCurrentBlueprintName('');
                  setIsDirty(false);
                  pastRef.current = [];
                  futureRef.current = [];
                  setCanvasStack([{ breadcrumbLabel: 'Main', type: 'main' }]);
                  setCurrentLevelIndex(0);
                  if (reactFlowInstance) {
                    reactFlowInstance.setViewport(defaultViewport, { duration: 0 });
                  }
                } else {
                  setTabs(remainingTabs);
                  if (isActiveClosed) {
                    const nextActiveTab = remainingTabs[0];
                    setBlocks(nextActiveTab.blocks);
                    setEdges(nextActiveTab.edges);
                    setAnnotations(nextActiveTab.annotations || []);
                    setCurrentBlueprintName(nextActiveTab.name === 'Untitled' ? '' : nextActiveTab.name);
                    setIsDirty(nextActiveTab.isDirty);
                    pastRef.current = nextActiveTab.past || [];
                    futureRef.current = nextActiveTab.future || [];
                    setCanvasStack(nextActiveTab.canvasStack || [{ breadcrumbLabel: 'Main', type: 'main' }]);
                    setCurrentLevelIndex(nextActiveTab.currentLevelIndex || 0);
                    setActiveTabId(nextActiveTab.id);
                    if (reactFlowInstance) {
                      const nextViewport = nextActiveTab.viewport || { x: 50, y: 50, zoom: 0.9 };
                      reactFlowInstance.setViewport(nextViewport, { duration: 0 });
                    }
                  }
                }
              } catch (err) {
                console.error('Failed to clear temporary files:', err);
                await alertAsync(t('app.alertFailedClearTemp', 'Failed to clear temporary files.'));
              }
            }
          }}
          onClearPersistentStates={async () => {
            setMenuOpen(false);
            if (await confirmAsync(t('app.confirmClearPersistent', 'Are you sure you want to clear all persistent block states and release their open handles/memory?'))) {
              try {
                await axios.post(`${BACKEND_URL}/blocks/clear_persistent`);
              } catch (err) {
                console.error('Failed to clear persistent blocks:', err);
                await alertAsync(t('app.alertFailedClearPersistent', 'Failed to clear persistent block states.'));
              }
            }
          }}
          onDownloadBlueprint={() => {
            setMenuOpen(false);
            handleSaveBlueprint();
          }}
          onUploadBlueprintClick={() => {
          const input = document.createElement('input');
          input.type = 'file';
          input.accept = '.json';
          input.onchange = (e: any) => {
            const file = e.target.files[0];
            if (file) handleBlueprintUpload(file);
          };
          input.click();
        }}
        onUploadFileClick={() => {
          setMenuOpen(false);
          setUploadFileOpen(true);
        }}
          onOpenSettings={() => setSettingsOpen(true)}
          onOpenSplash={() => setSplashOpen(true)}
          onOpenAbout={() => setAboutModalOpen(true)}
          onOpenQuickStart={() => setQuickStartModalOpen(true)}
          updateAvailable={Boolean(updateInfo?.update_available)}
          latestVersion={updateInfo?.latest_version}
          updateInfo={updateInfo}
          onCheckUpdate={fetchUpdateInfo}
          onLoadExample={() => setLoadExampleOpen(true)}
          onGroupCluster={handleGroupIntoCluster}
          onRun={handleRun}
          onPause={handlePause}
          onResume={handleResume}
          onAbort={handleAbort}
          onImportPackage={async () => {
            if (currentBlueprintName.startsWith('.temp/') || currentBlueprintName.includes('.temp/')) {
              const baseName = currentBlueprintName.split('/').pop() || '';
              const expectedPkgFilename = baseName + '.cfy';
              if (packageFilename !== expectedPkgFilename) {
                // Set to permanent import before opening the preview
                setImportPermanent(true);
                // Call raw loading endpoint but override state setter
                try {
                  const res = await axios.post(`${BACKEND_URL}/workspace/packages/load`, { filename: expectedPkgFilename });
                  setPackageFilename(expectedPkgFilename);
                  setPackagePreviewData(res.data);
                  setLoadWorkspaceOpen(false);
                  setPackageImportOpen(true);
                } catch (err: any) {
                  setErrorMessage(err.response?.data?.detail || 'Failed to load package preview.');
                }
              } else {
                setImportPermanent(true);
                setPackageImportOpen(true);
              }
            } else {
              setImportPermanent(true);
              setPackageImportOpen(true);
            }
          }}
          dashboardOpen={dashboardOpen}
          onToggleDashboard={() => setDashboardOpen(prev => !prev)}
          dashboardItemsCount={dashboardItems.length}
          onOpenStore={() => setStoreModalOpen(true)}
          storeBadgeCount={storeBadgeCount}
        />


        <input 
          id="blueprint-file-input" 
          type="file" 
          accept=".json" 
          onChange={handleLoadBlueprint} 
          style={{ display: 'none' }} 
        />

        {/* --- TAB BAR --- */}
        <TabBar
          tabs={tabs}
          activeTabId={activeTabId}
          runningTabId={runningTabId}
          isDirty={isDirty}
          switchTab={switchTab}
          closeTab={closeTab}
          addTab={addTab}
        />

        {/* --- BREADCRUMB BAR --- */}
        <BreadcrumbBar
          levels={canvasStack.map((lvl) => ({ breadcrumbLabel: lvl.breadcrumbLabel, type: lvl.type }))}
          currentIndex={currentLevelIndex}
          onNavigate={handleBreadcrumbNavigate}
        />

        {/* --- MAIN LAYOUT --- */}
        <div className="main-layout">
          {/* --- SIDEBAR --- */}
          <Sidebar
            sidebarOpen={sidebarOpen}
            setSidebarOpen={setSidebarOpen}
            searchQuery={searchQuery}
            setSearchQuery={setSearchQuery}
            filteredTree={filteredTree}
            onReloadRegistry={handleReloadRegistry}
            connectedOnly={connectedOnly}
            setConnectedOnly={(val) => {
              setConnectedOnly(prev => {
                const nextVal = typeof val === 'function' ? val(prev) : val;
                if (nextVal && connectedDevices.length === 0) {
                  scanConnectedDevices();
                }
                return nextVal;
              });
            }}
            isScanningVisa={isScanningVisa}
            connectedCount={connectedDevices.length}
            width={sidebarResizer.width}
            onResizeHandleMouseDown={sidebarResizer.handleProps.onMouseDown}
          />


          {/* --- CANVAS WRAPPER --- */}
          <div className="flow-wrapper" ref={reactFlowWrapper} style={{ position: 'relative' }} onMouseDown={handleWrapperMouseDown}>
            {errorMessage && (
              <div className="canvas-error-alert glass-panel">
                <span className="error-icon">⚠️</span>
                <span className="error-message">Error: {errorMessage}</span>
                <button className="error-close-btn" onClick={() => setErrorMessage(null)} title={t('canvasTools.clearError', 'Clear error')}>✕</button>
              </div>
            )}
            {isRestartingServer && (
              <div className="canvas-error-alert glass-panel" style={{ border: '1px solid #3b82f6', background: 'rgba(59, 130, 246, 0.1)', display: 'flex', alignItems: 'center', gap: '10px', zIndex: 10 }}>
                <span className="error-icon" style={{ animation: 'spin 1.2s linear infinite', display: 'inline-block' }}>🔄</span>
                <span className="error-message" style={{ color: 'var(--text-color)', flex: 1, margin: 0 }}>
                  {t('settingsModal.restartingServer', 'Restarting server, please wait...')}
                </span>
              </div>
            )}
            {unauthorizedBlocksCount > 0 && (
              <div className="canvas-error-alert glass-panel" style={{ border: '1px solid #f59e0b', background: 'rgba(245, 158, 11, 0.08)', display: 'flex', alignItems: 'center', gap: '10px', zIndex: 10 }}>
                <span className="error-icon" style={{ color: '#f59e0b' }}>⚠️</span>
                <span className="error-message" style={{ color: '#f59e0b', flex: 1, margin: 0 }}>
                  You have {unauthorizedBlocksCount} unauthorized custom block(s)/cluster(s) in your workspace.
                </span>
                <button 
                  className="button-primary" 
                  onClick={handleAuthorizeAllNodes}
                  style={{ padding: '6px 12px', fontSize: '0.8rem', background: '#f59e0b', color: '#1e293b', border: 'none', borderRadius: '4px', fontWeight: 'bold', cursor: 'pointer' }}
                >
                  Authorize & Sign
                </button>
              </div>
            )}

            <div className="canvas-floating-controls">
              {!sidebarOpen && (
                <button 
                  className="button-secondary library-toggle-btn"
                  onClick={() => setSidebarOpen(true)}
                  title={t('sidebar.showTitle', 'Show Block Library')}
                >
                  <span>📚</span>
                  <span>{t('sidebar.show', 'Show Library')}</span>
                </button>
              )}
              {currentLevelIndex > 0 && (
                <button
                  className="button-secondary back-btn"
                  onClick={() => handleBreadcrumbNavigate(currentLevelIndex - 1)}
                  title={t('canvasTools.backLevel', "Back to previous level")}
                >
                  <span>⬅</span>
                  <span>{t('canvasTools.backLabel', 'Back')}</span>
                </button>
              )}
              {selectedBlockIds.size >= 2 && (
                <button
                  className="button-primary cluster-group-btn"
                  onClick={handleGroupIntoCluster}
                  disabled={isRunning}
                  title={isRunning ? t('canvasTools.groupDisabled', "Cannot group blocks while an execution is running") : t('canvasTools.groupBlocks', "Group selected blocks into a cluster")}
                >
                  📦 {t('canvasTools.groupIntoCluster', 'Group into Cluster')} ({selectedBlockIds.size})
                </button>
              )}
            </div>
            <ReactFlow
              nodes={blocks.map((n: any) => ({ ...n, draggable: !isLocked && !n.data?.pinned }))}
              edges={snapPreviewEdges.length > 0 ? [...edges, ...snapPreviewEdges] : edges}
              onNodesChange={onBlocksChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onConnectStart={onConnectStart}
              onConnectEnd={onConnectEnd}
              onInit={setReactFlowInstance}
              onDrop={onDrop}
              onDragOver={onDragOver}
              onSelectionChange={onSelectionChange}
              onNodeDragStart={onBlockDragStart}
              onNodeDrag={onBlockDrag}
              onNodeDragStop={onBlockDragStop}
              isValidConnection={(connection) => {
                if (!connection.sourceHandle || !connection.targetHandle) return true;
                return true;
              }}
              nodeTypes={blockTypes}
              edgeTypes={edgeTypes}
              minZoom={0.2}
              maxZoom={2}
              defaultViewport={{ x: 50, y: 50, zoom: 0.9 }}
              className={`glass-panel canvas-mode-${canvasMode}`}
              proOptions={{ hideAttribution: true }}
              panOnDrag={(canvasMode === 'select' || canvasMode === 'cut' || canvasMode === 'draw') ? [1] : [0, 1]}
              selectionOnDrag={canvasMode === 'select'}
              snapToGrid={snapToGrid}
              snapGrid={[16, 16]}
              nodesDraggable={!isLocked}
              nodesConnectable={!isLocked}
              elementsSelectable={!isLocked}
              onPaneContextMenu={onPaneContextMenu}
              onNodeContextMenu={onBlockContextMenu}
              onSelectionContextMenu={onSelectionContextMenu}
              onEdgeContextMenu={onEdgeContextMenu}
              onPaneClick={closeContextMenu}
              onNodeClick={closeContextMenu}
              onEdgeClick={closeContextMenu}
              onMoveStart={closeContextMenu}
              onMoveEnd={handleMoveEnd}
            >
              <Background color="#3b82f6" gap={16} size={1} offset={[0.5, 0.5]} />
              <Controls showInteractive={false}>
                <ControlButton
                  onClick={onLayout}
                  title={t('canvasTools.autoOrganize', "Auto-Organize Blocks: Clean up and lay out blocks from left to right")}
                >
                  <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round" style={{ display: 'block', margin: 'auto' }}>
                    <rect x="2" y="9.5" width="6" height="5" rx="1" />
                    <rect x="16" y="3" width="6" height="5" rx="1" />
                    <rect x="16" y="16" width="6" height="5" rx="1" />
                    <path d="M8 12h4M12 5.5h4M12 18.5h4M12 5.5v13" />
                  </svg>
                </ControlButton>

                <ControlButton
                  onClick={() => setIsLocked(prev => !prev)}
                  className={`control-btn-lock ${isLocked ? 'control-btn-active' : ''}`}
                  title={isLocked ? t('canvasTools.unlock', 'Unlock Interactivity: Canvas is LOCKED') : t('canvasTools.lock', 'Lock Interactivity: Prevent moving or connecting blocks')}
                >
                  {isLocked ? (
                    <svg viewBox="0 0 25 32" width="15" height="15" style={{ display: 'block', margin: 'auto' }}>
                      <path d="M21.333 10.667H19.81V7.619C19.81 3.429 16.38 0 12.19 0 8 0 4.571 3.429 4.571 7.619v3.048H3.048A3.056 3.056 0 000 13.714v15.238A3.056 3.056 0 003.048 32h18.285a3.056 3.056 0 003.048-3.048V13.714a3.056 3.056 0 00-3.048-3.047zM12.19 24.533a3.056 3.056 0 01-3.047-3.047 3.056 3.056 0 013.047-3.048 3.056 3.056 0 013.048 3.048 3.056 3.056 0 01-3.048 3.047zm4.724-13.866H7.467V7.619c0-2.59 2.133-4.724 4.723-4.724 2.591 0 4.724 2.133 4.724 4.724v3.048z" />
                    </svg>
                  ) : (
                    <svg viewBox="0 0 25 32" width="15" height="15" style={{ display: 'block', margin: 'auto' }}>
                      <path d="M21.333 10.667H19.81V7.619C19.81 3.429 16.38 0 12.19 0c-4.114 1.828-1.37 2.133.305 2.438 1.676.305 4.42 2.59 4.42 5.181v3.048H3.047A3.056 3.056 0 000 13.714v15.238A3.056 3.056 0 003.048 32h18.285a3.056 3.056 0 003.048-3.048V13.714a3.056 3.056 0 00-3.048-3.047zM12.19 24.533a3.056 3.056 0 01-3.047-3.047 3.056 3.056 0 013.047-3.048 3.056 3.056 0 013.048 3.048 3.056 3.056 0 01-3.048 3.047z" />
                    </svg>
                  )}
                </ControlButton>
                <ControlButton
                  onClick={() => { setSnapToGrid(prev => !prev); }}
                  className={`control-btn-snap ${snapToGrid ? 'control-btn-active control-btn-snap-active' : ''}`}
                  title={snapToGrid ? t('canvasTools.snapOff', 'Snap to Grid: ON — Click to disable') : t('canvasTools.snapOn', 'Snap to Grid: OFF — Click to enable')}
                >
                  {/* Horseshoe magnet icon */}
                  <svg viewBox="0 0 24 24" width="15" height="15" style={{ display: 'block', margin: 'auto' }}>
                    <path d="M12,2A9,9 0 0,1 21,11V17H17V11A5,5 0 0,0 12,6A5,5 0 0,0 7,11V17H3V11A9,9 0 0,1 12,2M3,18H7V20H3V18M17,18H21V20H17V18" />
                  </svg>
                </ControlButton>
                <ControlButton
                  onClick={() => setShowAnnotations(prev => !prev)}
                  className={`control-btn-visibility ${showAnnotations ? 'control-btn-active' : ''}`}
                  title={showAnnotations ? t('canvasTools.hideAnnotations', "Hide Annotations") : t('canvasTools.showAnnotations', "Show Annotations")}
                >
                  {showAnnotations ? (
                    <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round" style={{ display: 'block', margin: 'auto' }}>
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                      <circle cx="12" cy="12" r="3"></circle>
                    </svg>
                  ) : (
                    <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round" style={{ display: 'block', margin: 'auto' }}>
                      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                      <line x1="1" y1="1" x2="23" y2="23"></line>
                    </svg>
                  )}
                </ControlButton>

                <ControlButton
                  onClick={() => setCanvasMode('select')}
                  className={`control-btn-select ${canvasMode === 'select' ? 'control-btn-active' : ''}`}
                  title={t('canvasTools.selectionMode', "Selection Mode: Left-click drag to select blocks, Middle/Right-click drag to pan")}
                >
                  <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round" style={{ display: 'block', margin: 'auto' }}>
                    <polygon points="3 3 10.07 19.97 12.58 12.58 19.97 10.07 3 3"></polygon>
                    <line x1="12" y1="12" x2="19" y2="19"></line>
                  </svg>
                </ControlButton>
                <ControlButton
                  onClick={() => setCanvasMode('pan')}
                  className={`control-btn-pan ${canvasMode === 'pan' ? 'control-btn-active' : ''}`}
                  title={t('canvasTools.panMode', "Pan Mode: Left-click drag to pan/move canvas")}
                >
                  <svg viewBox="0 0 24 24" width="16" height="16" style={{ display: 'block', margin: 'auto' }}>
                    {canvasMode === 'pan' ? (
                      <path d="M21 7C21 5.62 19.88 4.5 18.5 4.5C18.33 4.5 18.16 4.5 18 4.55V4C18 2.62 16.88 1.5 15.5 1.5C15.27 1.5 15.04 1.53 14.83 1.59C14.46 .66 13.56 0 12.5 0C11.27 0 10.25 .89 10.04 2.06C9.87 2 9.69 2 9.5 2C8.12 2 7 3.12 7 4.5V10.39C6.66 10.08 6.24 9.85 5.78 9.73L5 9.5C4.18 9.29 3.31 9.61 2.82 10.35C2.44 10.92 2.42 11.66 2.67 12.3L5.23 18.73C6.5 21.91 9.57 24 13 24C17.42 24 21 20.42 21 16V7M19 16C19 19.31 16.31 22 13 22C10.39 22 8.05 20.41 7.09 18L4.5 11.45L5 11.59C5.5 11.71 5.85 12.05 6 12.5L7 15H9V4.5C9 4.22 9.22 4 9.5 4S10 4.22 10 4.5V12H12V2.5C12 2.22 12.22 2 12.5 2S13 2.22 13 2.5V12H15V4C15 3.72 15.22 3.5 15.5 3.5S16 3.72 16 4V12H18V7C18 6.72 18.22 6.5 18.5 6.5S19 6.72 19 7V16Z" />
                    ) : (
                      <path d="M13 24C9.74 24 6.81 22 5.6 19L2.57 11.37C2.26 10.58 3 9.79 3.81 10.05L4.6 10.31C5.16 10.5 5.62 10.92 5.84 11.47L7.25 15H8V3.25C8 2.56 8.56 2 9.25 2S10.5 2.56 10.5 3.25V12H11.5V1.25C11.5 .56 12.06 0 12.75 0S14 .56 14 1.25V12H15V2.75C15 2.06 15.56 1.5 16.25 1.5C16.94 1.5 17.5 2.06 17.5 2.75V12H18.5V5.75C18.5 5.06 19.06 4.5 19.75 4.5S21 5.06 21 5.75V16C21 20.42 17.42 24 13 24Z" />
                    )}
                  </svg>
                </ControlButton>
                <ControlButton
                  onClick={() => setCanvasMode('cut')}
                  className={`control-btn-cut ${canvasMode === 'cut' ? 'control-btn-active' : ''}`}
                  title={t('canvasTools.cutMode', "Cut Mode: Left-click drag to cut/erase connections")}
                >
                  <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round" style={{ display: 'block', margin: 'auto' }}>
                    <circle cx="6" cy="6" r="3"></circle>
                    <circle cx="6" cy="18" r="3"></circle>
                    <line x1="20" y1="4" x2="8.12" y2="15.88"></line>
                    <line x1="14.47" y1="14.48" x2="20" y2="20"></line>
                    <line x1="8.12" y1="8.12" x2="12" y2="12"></line>
                  </svg>
                </ControlButton>
                <ControlButton
                  onClick={() => {
                    if (canvasMode !== 'draw') {
                      setCanvasMode('draw');
                      setShowAnnotations(true);
                    } else {
                      setCanvasMode('select');
                    }
                  }}
                  className={`control-btn-draw ${canvasMode === 'draw' ? 'control-btn-active' : ''}`}
                  title={t('canvasTools.drawMode', "Draw Mode: Annotate and draw on the canvas")}
                >
                  <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round" style={{ display: 'block', margin: 'auto' }}>
                    <path d="M12 20h9"></path>
                    <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
                  </svg>
                </ControlButton>
              </Controls>
              {!liteMode && (
                <MiniMap
                  pannable
                  zoomable
                  onClick={(_event, position) => {
                    if (reactFlowInstance) {
                      const viewport = reactFlowInstance.getViewport();
                      reactFlowInstance.setCenter(position.x, position.y, { zoom: viewport.zoom, duration: 400 });
                    }
                  }}
                />
              )}

              {/* Whiteboard / Annotations SVG Overlay */}
              <WhiteboardOverlay
                showAnnotations={showAnnotations}
                drawTool={drawTool}
                canvasMode={canvasMode}
                viewport={viewport}
                annotations={annotations}
                currentAnnotation={currentAnnotation}
                eraserPath={eraserPath}
                markedForDeletion={markedForDeletion}
                hoverPoint={hoverPoint}
                editingTextId={editingTextId}
                selectedAnnotationId={selectedAnnotationId}
                blocks={blocks}
                edges={edges}
                pushStateToHistory={pushStateToHistory}
                setAnnotations={setAnnotations}
                setEditingTextId={setEditingTextId}
                onMouseDown={handleSvgMouseDown}
                onMouseMove={handleSvgMouseMove}
                onMouseUp={handleSvgMouseUp}
                onDoubleClick={handleSvgDoubleClick}
                onWheel={handleSvgWheel}
                onStartResize={handleResizeStart}
              />
            </ReactFlow>

            {/* Slicing/Cutter path SVG overlay */}
            {canvasMode === 'cut' && cutterPath && cutterPath.length > 1 && (
              <svg
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  height: '100%',
                  pointerEvents: 'none',
                  zIndex: 9999,
                }}
              >
                <polyline
                  points={cutterPath.map(p => `${p.x},${p.y}`).join(' ')}
                  fill="none"
                  stroke="#ef4444"
                  strokeWidth="3"
                  strokeDasharray="4 2"
                  style={{ filter: 'drop-shadow(0 0 4px #ef4444)' }}
                />
              </svg>
            )}

            {/* Context Menu overlay */}
            <CanvasContextMenu
              contextMenu={contextMenu}
              contextMenuSearch={contextMenuSearch}
              setContextMenuSearch={setContextMenuSearch}
              blockRegistry={blockRegistry}
              isLocked={isLocked}
              snapToGrid={snapToGrid}
              showAnnotations={showAnnotations}
              selectedBlockIds={selectedBlockIds}
              clipboardBlocksCount={clipboardBlocksCount}
              blocks={blocks}
              edges={edges}
              onClose={closeContextMenu}
              onAddNodeAtClientPosition={addBlockAtClientPosition}
              onPaste={handlePaste}
              onResetZoom={() => reactFlowInstance?.zoomTo(1, { duration: 300 })}
              onFitView={() => reactFlowInstance?.fitView({ duration: 300 })}
              onLayout={onLayout}
              onToggleLocked={() => setIsLocked(prev => !prev)}
              onToggleSnap={() => setSnapToGrid(prev => !prev)}
              onToggleAnnotations={() => setShowAnnotations(prev => !prev)}
              onClearCanvas={async () => {
                if (await confirmAsync(t('app.confirmClearCanvasShort', 'Clear canvas?'))) {
                  pushStateToHistory(blocksRef.current, edgesRef.current, annotationsRef.current);
                  setBlocks([]);
                  setEdges([]);
                  setAnnotations([]);
                }
              }}
              onInspectBlock={(id) => {
                setInspectedBlockId(id);
                setInspectorOpen(true);
              }}
              onCopyBlock={handleCopy}
              onDuplicateBlock={handleDuplicate}
              onDeleteBlock={handleDeleteBlockFromMenu}
              onDeleteEdge={handleDeleteEdgeFromMenu}
              onEditScript={onEditScript}
              onGroupIntoCluster={handleGroupIntoCluster}
              onClearBlockData={handleClearBlockData}
              onClearAllBlocksData={handleClearAllBlocksData}
              onReplaceBlock={handleReplaceBlock}
              onBlockDataChange={onBlockDataChange}
              onToggleDashboard={toggleBlockDashboard}
            />


          {quickConnectMenu?.show && (
            <div
              className="quick-connect-menu glass-panel"
              onPointerDown={(e) => e.stopPropagation()}
              onMouseDown={(e) => e.stopPropagation()}
              onClick={(e) => e.stopPropagation()}
              style={{
                position: 'absolute',
                left: quickConnectMenu.offsetX,
                top: quickConnectMenu.offsetY,
                zIndex: 2000,
                padding: '12px',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
                boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
                borderRadius: '8px',
              }}
            >
              <div style={{ fontSize: '13px', fontWeight: '500', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                Quick Connect
              </div>
              <button 
                className="button-primary" 
                style={{ justifyContent: 'center', padding: '6px 16px' }}
                onClick={() => {
                  const menu = quickConnectMenu;
                  const sourceBlock = blocksRef.current.find((n: any) => n.id === menu.sourceBlockId);
                  const layout = registryRef.current?.[sourceBlock?.data?.action];
                  let dataType = 'any';
                  if (menu.sourceHandleType === 'source') {
                    const pin = layout?.dataOuts?.find((p: any) => p.name === menu.sourceHandleId);
                    if (pin) dataType = pin.type || 'any';
                  } else {
                    const pin = layout?.dataIns?.find((p: any) => p.name === menu.sourceHandleId);
                    if (pin) dataType = pin.type || 'any';
                  }
                  
                  let createType = 'constants/number';
                  if (menu.sourceHandleType === 'source') {
                    createType = 'outputs/basic/display';
                  } else {
                    switch (dataType) {
                      case 'number':
                      case 'int':
                      case 'float':
                        createType = 'constants/number'; break;
                      case 'string':
                      case 'text':
                        createType = 'constants/string'; break;
                      case 'boolean':
                      case 'bool':
                        createType = 'constants/boolean'; break;
                      case 'ndarray':
                      case 'array':
                        createType = 'Numeric Arrays/manipulation/create';
                        if (!registryRef.current?.[createType]) {
                            createType = 'Numeric Arrays/manipulation/accumulate';
                        }
                        break;
                      case 'list':
                        createType = 'Lists/manipulation/create';
                        if (!registryRef.current?.[createType]) {
                            createType = 'Lists/manipulation/accumulate';
                        }
                        break;
                      default:
                        createType = 'constants/number';
                    }
                  }
                  handleQuickConnect(menu, createType);
                }}
              >
                Create Default Block
              </button>
            </div>
          )}
            </div>

            {/* Drawing Sidebar Pane */}
            <WhiteboardSidebar
              isOpen={canvasMode === 'draw'}
              drawTool={drawTool}
              setDrawTool={setDrawTool}
              lineStartCap={lineStartCap}
              setLineStartCap={setLineStartCap}
              lineEndCap={lineEndCap}
              setLineEndCap={setLineEndCap}
              drawColor={drawColor}
              setDrawColor={setDrawColor}
              drawStyle={drawStyle}
              setDrawStyle={setDrawStyle}
              drawWidth={drawWidth}
              setDrawWidth={setDrawWidth}
              drawFillEnable={drawFillEnable}
              setDrawFillEnable={setDrawFillEnable}
              drawFillColor={drawFillColor}
              setDrawFillColor={setDrawFillColor}
              drawFillOpacity={drawFillOpacity}
              setDrawFillOpacity={setDrawFillOpacity}
              setEditingTextId={setEditingTextId}
              commitActivePolyshape={commitActivePolyshape}
              onClearAll={async () => {
                if (await confirmAsync(t('app.confirmClearAnnotations', 'Are you sure you want to clear all annotations from this level?'))) {
                  pushStateToHistory(blocksRef.current, edgesRef.current, annotationsRef.current);
                  setAnnotations([]);
                }
              }}
              onDone={() => setCanvasMode('select')}
            />

            {/* --- NODE INSPECTOR PANEL --- */}
            {inspectorOpen && inspectedBlockId && canvasMode !== 'draw' && !activeScriptBlock && (
              <BlockInspectorPanel
                isOpen={true}
                blockId={inspectedBlockId}
                blocks={blocks}
                edges={edges}
                onClose={() => {
                  setInspectorOpen(false);
                  setInspectedBlockId(null);
                }}
                onBlockDataChange={onBlockDataChange}
                onReloadRegistry={handleReloadRegistry}
                width={inspectorResizer.width}
                onResizeHandleMouseDown={inspectorResizer.handleProps.onMouseDown}
                onToggleDashboard={toggleBlockDashboard}
                onTogglePinDashboard={togglePinDashboard}
                isBlockInDashboard={dashboardItems.some((i) => i.blockId === inspectedBlockId && i.type === 'block')}
                dashboardPins={dashboardItems.filter((i) => i.blockId === inspectedBlockId && i.type === 'pin').map((i) => i.pinName!).filter(Boolean)}
              />
            )}

            {/* --- BLUEPRINT DASHBOARD PANEL --- */}
            {dashboardOpen && canvasMode !== 'draw' && !activeScriptBlock && (
              <DashboardPanel
                isOpen={true}
                onClose={() => setDashboardOpen(false)}
                isMaximized={dashboardMaximized}
                setIsMaximized={setDashboardMaximized}
                items={dashboardItems}
                blocks={blocks}
                blockRegistry={blockRegistry}
                onJumpToBlock={handleJumpToBlock}
                onRemoveItem={(itemId) => {
                  setDashboardItems((prev) => {
                    const target = prev.find((i) => i.id === itemId);
                    if (target) {
                      if (target.type === 'block') {
                        onBlockDataChange(target.blockId, 'inDashboard', false);
                      } else if (target.type === 'pin' && target.pinName) {
                        const block = blocksRef.current.find((b) => b.id === target.blockId);
                        const currentPins = Array.isArray(block?.data?.dashboardPins) ? block.data.dashboardPins : [];
                        onBlockDataChange(target.blockId, 'dashboardPins', currentPins.filter((p: string) => p !== target.pinName));
                      }
                    }
                    return prev.filter((i) => i.id !== itemId);
                  });
                  setIsDirty(true);
                }}
                onReorderItems={(newItems) => {
                  setDashboardItems(newItems);
                  setIsDirty(true);
                }}
                onClearAll={async () => {
                  if (await confirmAsync(t('dashboard.confirmClear', 'Are you sure you want to remove all items from the dashboard?'))) {
                    dashboardItems.forEach((item) => {
                      if (item.type === 'block') {
                        onBlockDataChange(item.blockId, 'inDashboard', false);
                      } else if (item.type === 'pin' && item.pinName) {
                        const block = blocksRef.current.find((b) => b.id === item.blockId);
                        const currentPins = Array.isArray(block?.data?.dashboardPins) ? block.data.dashboardPins : [];
                        onBlockDataChange(item.blockId, 'dashboardPins', currentPins.filter((p: string) => p !== item.pinName));
                      }
                    });
                    setDashboardItems([]);
                    setIsDirty(true);
                  }
                }}
                onBlockDataChange={onBlockDataChange}
                width={dashboardResizer.width}
                onResizeHandleMouseDown={dashboardResizer.handleProps.onMouseDown}
              />
            )}
          </div>

        {/* --- GLOBAL SCRIPT EDITOR PANEL --- */}
        {activeScriptBlock && (
          <ScriptEditorPanel
            isOpen={true}
            code={activeScriptBlock.code}
            blockId={activeScriptBlock.id}
            actionType={activeScriptBlock.actionType}
            onSave={(code, inputs, outputs) => {
              onBlockDataChange(activeScriptBlock.id, 'code', code);
              onBlockDataChange(activeScriptBlock.id, 'customInputs', inputs);
              onBlockDataChange(activeScriptBlock.id, 'customOutputs', outputs);
              setActiveScriptBlock(null);
            }}
            onClose={() => setActiveScriptBlock(null)}
            onCodeChange={onScriptCodeChange}
            hasActiveWorkspace={!!workspacePath}
            onPublishSuccess={fetchRegistry}
            registryLayout={blockRegistry?.[activeScriptBlock.actionType]}
            appTheme={theme}
          />
        )}

        {activeLibraryBlockId && (() => {
          const block = blocks.find((n: any) => n.id === activeLibraryBlockId);
          if (!block) return null;
          return (
            <LibrarySignatureEditorPanel
              isOpen={true}
              blockId={block.id}
              nodeName={block.data.customName || block.id}
              libraryArgs={block.data.library_args || block.data.ffi_args || []}
              onSave={(args) => {
                onBlockDataChange(block.id, 'library_args', args);
              }}
              onClose={() => setActiveLibraryBlockId(null)}
            />
          );
        })()}

        {/* --- CREATE CLUSTER MODAL --- */}
        {createClusterOpen && (
          <CreateClusterModal
            isOpen={true}
            detectedBoundary={detectedBoundary || { exec_ins: [], exec_outs: [], data_ins: [], data_outs: [] }}
            selectedBlockIds={selectedForCluster}
            internalBlueprint={{
              blocks: blocks
                .filter((n: any) => selectedForCluster.includes(n.id))
                .map((n: any) => ({ id: n.id, type: n.data.action, position: n.position, properties: (() => {
                  const props: any = {};
                  const exclude = ['action', 'status', 'resultMessage', 'onChange', 'results', 'onEditScript', 'onEditFFISignature', 'onEditLibrarySignature', 'onNavigateInto', 'onInspect'];
                  Object.keys(n.data || {}).forEach((k: string) => { if (!exclude.includes(k)) props[k] = n.data[k]; });
                  return props;
                })() })),
              links: edges
                .filter((e: any) => selectedForCluster.includes(e.source) && selectedForCluster.includes(e.target))
                .map((e: any) => {
                  const sourceBlock = blocks.find((n: any) => n.id === e.source);
                  const layout = blockRegistry?.[sourceBlock?.data?.action || ''];
                  const isExec = layout?.execOuts?.includes(e.sourceHandle || '') || false;
                  return { id: e.id, type: isExec ? 'exec' : 'data', source_block: e.source, source_pin: e.sourceHandle || '', target_block: e.target, target_pin: e.targetHandle || '' };
                })
            }}
            hasActiveWorkspace={!!workspacePath}
            onClose={() => setCreateClusterOpen(false)}
            onCreated={(typeName, clusterNodeData) => {
              collapseIntoClusterNode(typeName, clusterNodeData);
              fetchRegistry();
            }}
          />
        )}

        {/* --- SETTINGS MODAL OVERLAY --- */}
        <GlobalSettingsModal
          isOpen={settingsOpen}
          settings={settings}
          setSettings={setSettings}
          liteMode={liteMode}
          setLiteMode={setLiteMode}
          newDirInput={newDirInput}
          setNewDirInput={setNewDirInput}
          settingsTab={settingsTab}
          setSettingsTab={setSettingsTab}
          diagnosticsData={diagnosticsData}
          loadingDiagnostics={loadingDiagnostics}
          fetchDiagnostics={fetchDiagnostics}
          onRestartServer={handleRestartServer}
          isRestartingServer={isRestartingServer}
          onSave={async () => {
            const success = await handleSaveSettings();
            if (success) {
              await alertAsync(
                t('app.alertSettingsSaved', 'Settings saved and dynamic blocks reloaded successfully!'),
                t('settingsModal.title', 'Global Settings')
              );
              setSettingsOpen(false);
            }
          }}
          onClose={() => {
            fetchSettings();
            setSettingsOpen(false);
          }}
        />

        {/* --- SAVE TO WORKSPACE MODAL --- */}
        <SaveWorkspaceModal
          isOpen={saveWorkspaceOpen}
          saveFilenameInput={saveFilenameInput}
          exportAsPackage={exportAsPackage}
          setSaveFilenameInput={setSaveFilenameInput}
          setExportAsPackage={setExportAsPackage}
          onClose={() => setSaveWorkspaceOpen(false)}
          onSubmit={handleSaveToWorkspaceWithFilename}
        />

        {/* --- LOAD FROM WORKSPACE MODAL --- */}
        <LoadWorkspaceModal
          isOpen={loadWorkspaceOpen}
          workspaceBlueprints={workspaceBlueprints}
          onClose={() => setLoadWorkspaceOpen(false)}
          onOpenPackage={handleOpenPackage}
          onLoadBlueprintByName={handleLoadBlueprintByName}
          onDeleteBlueprint={handleDeleteBlueprint}
          onOpenExplorer={handleOpenBlueprintsExplorer}
          confirmAsync={confirmAsync}
        />

        {/* --- TRUST WARNING MODAL --- */}
        <TrustWarningModal
          isOpen={trustWarningOpen}
          trustWarningMessage={trustWarningMessage}
          pendingBlueprint={pendingBlueprint}
          onClose={() => setTrustWarningOpen(false)}
          onAlwaysTrust={async () => {
            if (pendingBlueprint) {
              loadBlueprintData(pendingBlueprint, pendingFilename);
              if (pendingBlueprint.origin_uuid) {
                try {
                  await axios.post(`${BACKEND_URL}/workspace/blueprints/trust-origin`, {
                    origin_uuid: pendingBlueprint.origin_uuid
                  });
                  const res = await axios.get(`${BACKEND_URL}/settings`);
                  setSettings(res.data);
                } catch (err) {
                  console.error("Failed to trust origin:", err);
                }
              }
              setTrustWarningOpen(false);
              setPendingBlueprint(null);
              setPendingFilename("");
            }
          }}
          onTrustOnce={() => {
            if (pendingBlueprint) {
              loadBlueprintData(pendingBlueprint, pendingFilename);
              setTrustWarningOpen(false);
              setPendingBlueprint(null);
              setPendingFilename("");
            }
          }}
        />

        {/* --- PACKAGE IMPORT MODAL --- */}
        <PackageImportModal
          isOpen={packageImportOpen}
          packageFilename={packageFilename}
          packagePreviewData={packagePreviewData}
          importDestination={importDestination}
          importPermanent={importPermanent}
          trustAndSign={trustAndSign}
          deletePackageAfterImport={deletePackageAfterImport}
          onClose={() => setPackageImportOpen(false)}
          setImportDestination={setImportDestination}
          setImportPermanent={setImportPermanent}
          setTrustAndSign={setTrustAndSign}
          setDeletePackageAfterImport={setDeletePackageAfterImport}
          onImport={handleImportPackage}
        />

        {/* --- UPLOAD FILE MODAL --- */}
        <UploadFileModal
          isOpen={uploadFileOpen}
          onClose={() => setUploadFileOpen(false)}
          BACKEND_URL={BACKEND_URL}
        />

        {/* --- CONFIRM MODAL --- */}
        {confirmDialog && (
          <ConfirmModal
            message={confirmDialog.message}
            onConfirm={confirmDialog.onConfirm}
            onCancel={confirmDialog.onCancel}
          />
        )}

        {/* --- ALERT MODAL --- */}
        {alertDialog && (
          <AlertModal
            title={alertDialog.title}
            message={alertDialog.message}
            onClose={alertDialog.onClose}
          />
        )}

        {/* --- ABOUT MODAL --- */}
        {aboutModalOpen && (
          <AboutModal 
            onClose={() => setAboutModalOpen(false)} 
            updateInfo={updateInfo}
            onCheckUpdate={fetchUpdateInfo}
          />
        )}

        {/* --- COMFYLAB STORE MODAL --- */}
        {storeModalOpen && (
          <StoreModal
            onClose={() => {
              setStoreModalOpen(false);
              fetchStoreBadge();
            }}
            onRefreshRegistry={handleReloadRegistry}
          />
        )}

        {/* --- QUICK START MODAL --- */}
        {quickStartModalOpen && (
          <QuickStartModal onClose={() => setQuickStartModalOpen(false)} />
        )}

        {/* --- SPLASH SCREEN MODAL --- */}
        <SplashScreenModal
          isOpen={splashOpen}
          onClose={() => setSplashOpen(false)}
          onNewBlueprint={() => {
            setBlocks([]);
            setEdges([]);
            setAnnotations([]);
            setCurrentBlueprintName('');
            setIsDirty(false);
          }}
          onLoadBlueprint={() => {
            fetchWorkspaceBlueprints();
            setLoadWorkspaceOpen(true);
          }}
          onLoadExample={() => {
            setLoadExampleOpen(true);
          }}
          onOpenSettings={() => {
            fetchSettings();
            setSettingsOpen(true);
          }}
          onOpenAbout={() => {
            setAboutModalOpen(true);
          }}
          onOpenQuickStart={() => {
            setQuickStartModalOpen(true);
          }}
        />

        {/* --- LOAD EXAMPLE MODAL --- */}
        <LoadExampleModal
          isOpen={loadExampleOpen}
          onClose={() => setLoadExampleOpen(false)}
          onLoadExampleByName={handleLoadExampleByName}
          BACKEND_URL={BACKEND_URL}
        />
        </div>
      </SettingsContext.Provider>
    </RegistryContext.Provider>
  );

}

export default () => (
  <ReactFlowProvider>
    <Flow />
  </ReactFlowProvider>
);
