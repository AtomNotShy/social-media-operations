import { AlertTriangle, RotateCcw } from "lucide-react";

export function ErrorState({
  message,
  requestId,
  onRetry,
}: {
  message: string;
  requestId?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex min-h-64 flex-col items-center justify-center px-6 text-center">
      <span className="mb-4 rounded-xl bg-red-50 p-3 text-danger">
        <AlertTriangle aria-hidden="true" size={24} />
      </span>
      <h2 className="font-semibold">数据暂时无法加载</h2>
      <p className="mt-2 max-w-md text-sm leading-6 text-text-muted">{message}</p>
      {requestId ? (
        <details className="mt-3 text-xs text-text-muted">
          <summary className="cursor-pointer">查看诊断信息</summary>
          <code className="mt-2 block">Request ID: {requestId}</code>
        </details>
      ) : null}
      {onRetry ? (
        <button
          className="mt-5 inline-flex items-center gap-2 rounded-lg bg-text px-4 py-2 text-sm font-medium text-white"
          onClick={onRetry}
          type="button"
        >
          <RotateCcw aria-hidden="true" size={15} />
          重新加载
        </button>
      ) : null}
    </div>
  );
}
