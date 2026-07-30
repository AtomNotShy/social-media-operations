export type AppError = {
  code: string;
  message: string;
  status: number;
  requestId?: string;
  retryable: boolean;
};

export async function toAppError(response: Response): Promise<AppError> {
  let problem: Record<string, unknown> = {};
  try {
    problem = (await response.json()) as Record<string, unknown>;
  } catch {
    // A network proxy may return a non-JSON error page.
  }
  return {
    code: String(problem.code ?? "REQUEST_FAILED"),
    message: String(problem.detail ?? "暂时无法获取数据，请稍后重试。"),
    status: response.status,
    requestId: problem.request_id ? String(problem.request_id) : undefined,
    retryable: Boolean(problem.retryable ?? response.status >= 500),
  };
}
