import { Loader2 } from 'lucide-react';

export function StatusPill({ label, busy }: { label: string; busy?: boolean }) {
  return (
    <div className="status-pill">
      {busy ? <Loader2 className="spin" size={14} /> : <span className="status-dot" />}
      <span>{label}</span>
    </div>
  );
}
