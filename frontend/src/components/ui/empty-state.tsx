import { Radar } from "lucide-react";

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex min-h-72 flex-col items-center justify-center px-6 text-center">
      <span className="mb-4 rounded-xl bg-primary-50 p-3 text-primary-600">
        <Radar aria-hidden="true" size={24} />
      </span>
      <h2 className="font-semibold">{title}</h2>
      <p className="mt-2 max-w-sm text-sm leading-6 text-text-muted">{description}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}
