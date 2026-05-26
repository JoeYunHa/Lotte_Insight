"use client";

import type { LabelFilter, ViewMode } from "@/lib/types";

export type { ViewMode, LabelFilter };

interface TopicMapToolbarProps {
  labelFilter: LabelFilter;
  viewMode: ViewMode;
  hasOutliers: boolean;
  onLabelFilter: (filter: LabelFilter) => void;
  onViewMode: (mode: ViewMode) => void;
  onReset: () => void;
}

const FILTER_TABS: { key: LabelFilter; name: string }[] = [
  { key: "ALL", name: "전체" },
  { key: "MATCH_RELATED", name: "경기" },
  { key: "INJURY_ROSTER", name: "엔트리" },
  { key: "TRANSACTION_CONTRACT", name: "트레이드" },
  { key: "PERFORMANCE_ANALYSIS", name: "성적" },
  { key: "INTERVIEW", name: "인터뷰" },
  { key: "CLUB_OPERATION", name: "구단" },
];

const VIEW_TABS: { key: ViewMode; name: string }[] = [
  { key: "cluster", name: "클러스터" },
  { key: "label", name: "라벨" },
  { key: "outlier", name: "아웃라이어" },
];

export function TopicMapToolbar({
  labelFilter,
  viewMode,
  hasOutliers,
  onLabelFilter,
  onViewMode,
  onReset,
}: TopicMapToolbarProps) {
  return (
    <div className="flex flex-wrap items-center gap-2 mb-3">
      <div className="flex gap-1 overflow-x-auto flex-1 min-w-0 pb-0.5">
        {FILTER_TABS.map(({ key, name }) => {
          const isActive = labelFilter === key;
          return (
            <button
              key={key}
              onClick={() => onLabelFilter(key)}
              className="flex-none rounded-full px-3 py-1 text-[11px] font-medium transition-all whitespace-nowrap"
              style={{
                color: isActive ? "var(--text)" : "var(--dim)",
                fontWeight: isActive ? 700 : 500,
                border: isActive
                  ? "1px solid rgba(225,6,44,0.28)"
                  : "1px solid var(--border)",
                background: isActive
                  ? "rgba(225,6,44,0.1)"
                  : "rgba(255,255,255,0.62)",
              }}
            >
              {name}
            </button>
          );
        })}
      </div>

      <div className="flex items-center gap-1 shrink-0">
        {VIEW_TABS.filter(({ key }) => key !== "outlier" || hasOutliers).map(
          ({ key, name }) => {
            const isActive = viewMode === key;
            return (
              <button
                key={key}
                onClick={() => onViewMode(key)}
                className="rounded-full px-3 py-1 text-[11px] font-medium transition-all"
                style={{
                  background: isActive ? "var(--text)" : "var(--surface-2)",
                  color: isActive ? "var(--bg)" : "var(--muted)",
                  border: "1px solid var(--border)",
                }}
              >
                {name}
              </button>
            );
          },
        )}
        <button
          onClick={onReset}
          className="rounded-full px-3 py-1 text-[11px] font-medium transition-all"
          style={{
            background: "transparent",
            color: "var(--dim)",
            border: "1px solid var(--border)",
          }}
        >
          초기화
        </button>
      </div>
    </div>
  );
}
