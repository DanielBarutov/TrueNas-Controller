import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import {
  AlertCircle,
  CheckCircle2,
  CircleHelp,
  Info,
  MinusCircle,
} from "lucide-react";
import {
  statusDescription,
  statusLabel,
  type StationStatus,
} from "../../domain/station";

const statusIcons: Record<StationStatus, LucideIcon> = {
  online: CheckCircle2,
  stale: AlertCircle,
  offline: MinusCircle,
  disabled: MinusCircle,
};

export function StatusBadge({ status }: { status: StationStatus }) {
  const Icon = statusIcons[status];
  return (
    <span className={`status-badge status-${status}`} title={statusDescription[status]}>
      <Icon aria-hidden size={14} strokeWidth={2.2} />
      {statusLabel[status]}
    </span>
  );
}

export function MetricCard({
  label,
  value,
  hint,
  accent,
  icon: Icon,
}: {
  label: string;
  value: string;
  hint: string;
  accent: "blue" | "green" | "amber";
  icon: LucideIcon;
}) {
  return (
    <article className={`metric-card accent-${accent}`}>
      <div className="metric-heading"><span>{label}</span><Icon aria-hidden size={18} /></div>
      <strong>{value}</strong>
      <small>{hint}</small>
    </article>
  );
}

export function SectionHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="section-heading">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h2>{title}</h2>
        {description && <p className="muted">{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function HelpHint({ children }: { children: ReactNode }) {
  return <small className="help-hint"><CircleHelp aria-hidden size={13} />{children}</small>;
}

export function InfoNote({ children }: { children: ReactNode }) {
  return <div className="info-note"><Info aria-hidden size={16} />{children}</div>;
}
