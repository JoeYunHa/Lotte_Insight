import type { PlayerStatus } from "../types";

export const ACTIVE_STATUS: PlayerStatus = "active";

export const PLAYER_STATUS_META: Record<
  PlayerStatus,
  { label: string; color: string }
> = {
  active: { label: "Active", color: "var(--gold)" },
  "1군": { label: "Active", color: "var(--gold)" },
  "2군": { label: "Reserve", color: "var(--dim)" },
  말소: { label: "Inactive", color: "var(--dim)" },
};

export const PLAYER_STATUS_BADGE: Record<
  PlayerStatus,
  { bg: string; text: string; border: string }
> = {
  active: {
    bg: "var(--gold-soft)",
    text: "var(--gold)",
    border: "var(--gold-border)",
  },
  "1군": {
    bg: "var(--gold-soft)",
    text: "var(--gold)",
    border: "var(--gold-border)",
  },
  "2군": {
    bg: "var(--blue-soft)",
    text: "var(--neutral)",
    border: "var(--blue-border)",
  },
  말소: {
    bg: "var(--red-soft)",
    text: "var(--red)",
    border: "var(--red-border)",
  },
};

export function isActiveStatus(status: string): boolean {
  return status === ACTIVE_STATUS || status === "1군";
}

export function toKnownPlayerStatus(status: string): PlayerStatus {
  if (
    status === "active" ||
    status === "1군" ||
    status === "2군" ||
    status === "말소"
  ) {
    return status;
  }
  return "2군";
}
