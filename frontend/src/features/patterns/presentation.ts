export function patternStatusLabel(status: string) {
  return (
    { draft: "草稿", validated: "已验证", retired: "已退役" }[status] ?? status
  );
}

export function evidenceValues(evidence: Record<string, unknown>) {
  return {
    success: typeof evidence.success_count === "number" ? evidence.success_count : 0,
    failure: typeof evidence.failure_count === "number" ? evidence.failure_count : 0,
    limitations:
      typeof evidence.limitations === "string"
        ? evidence.limitations
        : "尚未记录不适用条件",
  };
}
