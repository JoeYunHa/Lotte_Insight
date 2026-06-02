interface TopicMapHeroProps {
  date: string
  articleCount: number
  clusterCount: number
  outlierCount: number
}

export function TopicMapHero({ date, articleCount, clusterCount, outlierCount }: TopicMapHeroProps) {
  const meta = [
    { label: '기사', value: articleCount },
    { label: '클러스터', value: clusterCount },
    { label: '아웃라이어', value: outlierCount },
  ]

  return (
    <div className="pt-10 pb-6">
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <p className="text-xs font-medium font-mono-code" style={{ color: 'var(--muted)' }}>
          {date}
        </p>
        {meta.map(({ label, value }) => (
          <span
            key={label}
            className="chip-surface text-xs font-mono-code px-2 py-0.5 rounded-full"
            style={{ color: 'var(--dim)' }}
          >
            {value} {label}
          </span>
        ))}
      </div>

      <h1 className="font-serif-kr text-3xl font-black leading-tight mb-2" style={{ color: 'var(--text)' }}>
        {"오늘의 롯데 이슈 지형도"}
      </h1>
      <p className="text-sm leading-relaxed max-w-xl" style={{ color: 'var(--muted)' }}>
        가까운 점들은 유사한 내용을 다룹니다. 같은 색상의 점들은 같은 이슈 클러스터에 속합니다. 클러스터를 선택하면 요약을 볼 수 있습니다.
      </p>
      <div className="h-px w-full mt-5" style={{ background: 'var(--border)' }} />
    </div>
  )
}
