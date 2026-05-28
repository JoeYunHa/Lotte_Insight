import type { Player } from "../types";

export const POSITION_GROUPS: {
  key: string;
  label: string;
  match: (p: string) => boolean;
}[] = [
  {
    key: "pitcher",
    label: "Pitchers",
    match: (p) => p.includes("투수") || p.toLowerCase().includes("pitcher"),
  },
  {
    key: "catcher",
    label: "Catchers",
    match: (p) => p.includes("포수") || p.toLowerCase().includes("catcher"),
  },
  {
    key: "infield",
    label: "Infielders",
    match: (p) =>
      p.includes("내야") ||
      ["1루", "2루", "3루", "유격"].some((k) => p.includes(k)) ||
      p.toLowerCase().includes("infield"),
  },
  {
    key: "outfield",
    label: "Outfielders",
    match: (p) =>
      p.includes("외야") ||
      ["좌익", "중견", "우익"].some((k) => p.includes(k)) ||
      p.toLowerCase().includes("outfield"),
  },
];

export function classifyPosition(position: string): string {
  for (const group of POSITION_GROUPS) {
    if (group.match(position)) return group.key;
  }
  return "etc";
}

export function groupPlayers(players: Player[]): Record<string, Player[]> {
  const groups: Record<string, Player[]> = {
    pitcher: [],
    catcher: [],
    infield: [],
    outfield: [],
    etc: [],
  };
  for (const player of players) {
    groups[classifyPosition(player.position)].push(player);
  }
  return groups;
}
