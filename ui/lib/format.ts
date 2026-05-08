export function formatDate(value: string | null | undefined): string {
  if (!value) return "--";
  return value.slice(0, 10);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "--";
  return value.replace("T", " ").replace(/\.\d+Z$/, "Z").slice(0, 19);
}
