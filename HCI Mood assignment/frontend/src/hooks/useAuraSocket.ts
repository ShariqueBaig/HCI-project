import { useCallback, useEffect, useRef, useState } from 'react';
import type {
  AgencyMode,
  HciState,
  ModelStatus,
  TelemetryData,
  UISchema,
  WorkspaceData,
} from '../types/aura';

interface WsPayload {
  telemetry: TelemetryData;
  schema: UISchema;
  annotated_frame_b64: string | null;
  vision_latency_ms: number;
}

export function useAuraSocket() {
  const [workspace, setWorkspace] = useState<WorkspaceData | null>(null);
  const [telemetry, setTelemetry] = useState<TelemetryData | null>(null);
  const [schema, setSchema] = useState<UISchema | null>(null);
  const [models, setModels] = useState<ModelStatus | null>(null);
  const [frameB64, setFrameB64] = useState<string | null>(null);
  const [visionLatencyMs, setVisionLatencyMs] = useState<number>(0);
  const [connected, setConnected] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);

  const fetchInitial = useCallback(async () => {
    try {
      const res = await fetch('/api/workspace');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setWorkspace(data.workspace);
      setTelemetry(data.telemetry);
      setSchema(data.schema);
      setModels(data.models);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load workspace');
    }
  }, []);

  useEffect(() => {
    fetchInitial();

    let cancelled = false;
    let retryTimer: number | undefined;

    const connectWs = () => {
      if (cancelled) return;
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${proto}//${window.location.host}/ws/affective`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!cancelled) {
          setConnected(true);
          setError(null);
        }
      };

      ws.onmessage = (evt) => {
        try {
          const payload: WsPayload = JSON.parse(evt.data);
          setTelemetry(payload.telemetry);
          setSchema(payload.schema);
          setFrameB64(payload.annotated_frame_b64);
          setVisionLatencyMs(payload.vision_latency_ms ?? 0);
        } catch {
          // ignore malformed frame
        }
      };

      ws.onclose = () => {
        if (!cancelled) {
          setConnected(false);
          retryTimer = window.setTimeout(connectWs, 1500);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connectWs();
    return () => {
      cancelled = true;
      if (retryTimer) window.clearTimeout(retryTimer);
      wsRef.current?.close();
    };
  }, [fetchInitial]);

  const applyServerSnapshot = (data: { workspace?: WorkspaceData; telemetry?: TelemetryData; schema?: UISchema }) => {
    if (data.workspace) setWorkspace(data.workspace);
    if (data.telemetry) setTelemetry(data.telemetry);
    if (data.schema) setSchema(data.schema);
  };

  const toggleCamera = async (enabled: boolean) => {
    const res = await fetch('/api/camera/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    });
    return res.json();
  };

  const setAgency = async (mode: AgencyMode, dwellSeconds?: number) => {
    const res = await fetch('/api/agency', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode, dwell_seconds: dwellSeconds }),
    });
    const data = await res.json();
    applyServerSnapshot(data);
    return data;
  };

  const simulateState = async (state: HciState | null) => {
    const res = await fetch('/api/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ state }),
    });
    const data = await res.json();
    applyServerSnapshot(data);
    return data;
  };

  const respondProposal = async (action: 'accept' | 'dismiss' | 'undo') => {
    const res = await fetch('/api/proposal/respond', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action }),
    });
    const data = await res.json();
    applyServerSnapshot(data);
    return data;
  };

  const addTask = async (title: string, priority: 'high' | 'medium' | 'low', estimatedMinutes: number, category: string) => {
    const res = await fetch('/api/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, priority, estimatedMinutes, category }),
    });
    const data = await res.json();
    applyServerSnapshot(data);
  };

  const updateTask = async (id: string, patch: Record<string, unknown>) => {
    const res = await fetch(`/api/tasks/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    });
    const data = await res.json();
    applyServerSnapshot(data);
  };

  const toggleMicroStep = async (taskId: string, stepId: string) => {
    const res = await fetch(`/api/tasks/${taskId}/microstep/${stepId}`, { method: 'POST' });
    const data = await res.json();
    applyServerSnapshot(data);
  };

  const deleteTask = async (id: string) => {
    const res = await fetch(`/api/tasks/${id}`, { method: 'DELETE' });
    const data = await res.json();
    applyServerSnapshot(data);
  };

  const addNote = async (title: string, content = '') => {
    const res = await fetch('/api/notes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, content }),
    });
    const data = await res.json();
    applyServerSnapshot(data);
    return data.note;
  };

  const updateNote = async (id: string, title?: string, content?: string) => {
    const res = await fetch(`/api/notes/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, content }),
    });
    const data = await res.json();
    applyServerSnapshot(data);
  };

  const deleteNote = async (id: string) => {
    const res = await fetch(`/api/notes/${id}`, { method: 'DELETE' });
    const data = await res.json();
    applyServerSnapshot(data);
  };

  const addIdea = async (text: string, tag: string) => {
    const res = await fetch('/api/ideas', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, tag }),
    });
    const data = await res.json();
    applyServerSnapshot(data);
  };

  const deleteIdea = async (id: string) => {
    const res = await fetch(`/api/ideas/${id}`, { method: 'DELETE' });
    const data = await res.json();
    applyServerSnapshot(data);
  };

  const promoteIdea = async (id: string) => {
    const res = await fetch(`/api/ideas/${id}/promote`, { method: 'POST' });
    const data = await res.json();
    applyServerSnapshot(data);
  };

  return {
    workspace,
    telemetry,
    schema,
    models,
    frameB64,
    visionLatencyMs,
    connected,
    error,
    actions: {
      toggleCamera,
      setAgency,
      simulateState,
      respondProposal,
      addTask,
      updateTask,
      toggleMicroStep,
      deleteTask,
      addNote,
      updateNote,
      deleteNote,
      addIdea,
      deleteIdea,
      promoteIdea,
    },
  };
}
