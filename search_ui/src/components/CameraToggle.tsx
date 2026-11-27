import { Camera, CameraOff } from 'lucide-react';
import { useEffect, useState } from 'react';
import { apiGet, apiPost } from '../api';

interface CameraStatus {
  available: boolean;
  active: boolean;
  loading: boolean;
  error: string | null;
}

/**
 * Optional webcam affect sensor. Off by default; while on, a red dot is always
 * visible. Video never leaves the computer -- only smoothed mood numbers are used.
 */
export function CameraToggle({ face }: { face: boolean | undefined }) {
  const [st, setSt] = useState<CameraStatus | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    apiGet<CameraStatus>('/api/camera').then(setSt).catch(() => setSt(null));
  }, []);

  if (!st?.available) return null;

  const toggle = async () => {
    setBusy(true);
    try {
      setSt(await apiPost<CameraStatus>('/api/camera', { enabled: !st.active }));
    } finally {
      setBusy(false);
    }
  };

  const label = busy ? (st.active ? 'Turning off…' : 'Starting camera…') : st.active ? 'Camera on' : 'Camera off';
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={toggle}
        disabled={busy}
        aria-pressed={st.active}
        title={st.active
          ? 'Your expression is read on this computer only; no video is stored or sent. Click to turn off.'
          : 'Optional: let Aura read your expression on this computer to adapt better. Off by default.'}
        className="aura-target flex items-center gap-2 rounded-full border text-sm disabled:opacity-60"
        style={{ borderColor: st.active ? 'var(--aura-elev)' : 'var(--aura-border-interactive)', background: 'var(--aura-surface)' }}
      >
        {st.active ? <Camera size={14} aria-hidden /> : <CameraOff size={14} aria-hidden />}
        {st.active && <span className="h-2 w-2 animate-pulse rounded-full" style={{ background: 'var(--aura-elev)' }} aria-hidden />}
        {label}
        {st.active && face === false && <span className="text-xs" style={{ color: 'var(--aura-muted)' }}>· no face</span>}
      </button>
      {st.error && !st.active && (
        <span role="status" className="max-w-56 truncate text-xs" style={{ color: 'var(--aura-elev)' }} title={st.error}>
          {st.error}
        </span>
      )}
    </div>
  );
}
