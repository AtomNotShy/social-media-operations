export function buildInspirationsSearchHref({
  workspaceId,
  search,
  query,
}: {
  workspaceId: string;
  search: string;
  query: string;
}): string | null {
  const params = new URLSearchParams(search);
  const nextQuery = query.trim();
  const currentQuery = params.get("q")?.trim() ?? "";

  if (nextQuery === currentQuery) return null;

  if (nextQuery) params.set("q", nextQuery);
  else params.delete("q");
  params.delete("cursor");

  const suffix = params.toString();
  return `/w/${workspaceId}/inspirations${suffix ? `?${suffix}` : ""}`;
}
