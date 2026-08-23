import type { Metric } from "@/lib/api";

export function compact(value: number | null | undefined): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: value > 999 ? 1 : 0 }).format(value);
}

export function score(value: number | null | undefined): string {
  return value == null ? "—" : Math.round(value).toString();
}

export function percent(value: number | null | undefined, signed = false): string {
  if (value == null) return "—";
  const normalized = Math.abs(value) < 10 ? value * 100 : value;
  return `${signed && normalized > 0 ? "+" : ""}${normalized.toFixed(Math.abs(normalized) >= 10 ? 0 : 1)}%`;
}

export function duration(hours: number | null | undefined): string {
  if (hours == null) return "No evidence";
  if (hours < 1) return `${Math.round(hours * 60)}m`;
  if (hours < 48) return `${hours.toFixed(hours < 10 ? 1 : 0)}h`;
  return `${(hours / 24).toFixed(1)}d`;
}

export function relativeDate(value: string | null | undefined): string {
  if (!value) return "Unknown";
  const days = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 86_400_000));
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 30) return `${days} days ago`;
  if (days < 365) return `${Math.floor(days / 30)} months ago`;
  return `${Math.floor(days / 365)} years ago`;
}

export function getNumber(metric: Metric | undefined, group: string, key: string): number | null {
  const value = metric?.components?.[group]?.[key];
  return typeof value === "number" ? value : null;
}

export function assessment(metric: Metric | undefined): { status: string; tone: string } {
  return metric?.components?.assessment ?? { status: "Insufficient data", tone: "neutral" };
}
