import { Circle } from "lucide-react";

const styles: Record<string, string> = {
  idle: "bg-surface-subtle text-text-muted",
  paused: "bg-surface-subtle text-text-muted",
  pending: "bg-primary-50 text-primary-700",
  running: "bg-primary-50 text-primary-700",
  retry_wait: "bg-amber-50 text-amber-700",
  succeeded: "bg-emerald-50 text-emerald-700",
  failed: "bg-red-50 text-red-700",
  dead: "bg-red-50 text-red-700",
  cancelled: "bg-surface-subtle text-text-muted",
  inbox: "bg-amber-50 text-amber-700",
  analyzed: "bg-blue-50 text-blue-700",
  candidate: "bg-violet-50 text-violet-700",
  archived: "bg-surface-subtle text-text-muted",
  ready: "bg-emerald-50 text-emerald-700",
  summary: "bg-blue-50 text-blue-700",
  draft: "bg-amber-50 text-amber-700",
  validated: "bg-emerald-50 text-emerald-700",
  retired: "bg-surface-subtle text-text-muted",
};

export function StatusBadge({
  status,
  label,
}: {
  status: string;
  label: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${styles[status] ?? styles.idle}`}
    >
      <Circle
        aria-hidden="true"
        className={status === "running" ? "animate-pulse fill-current" : "fill-current"}
        size={6}
      />
      {label}
    </span>
  );
}
