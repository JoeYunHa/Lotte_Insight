interface TopicMapHeroProps {
  date: string
  articleCount: number
  clusterCount: number
  outlierCount: number
}

export function TopicMapHero({ date, articleCount, clusterCount, outlierCount }: TopicMapHeroProps) {
  const meta = [
    { label: 'stories', value: articleCount },
    { label: 'clusters', value: clusterCount },
    { label: 'outliers', value: outlierCount },
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
            className="text-xs font-mono-code px-2 py-0.5 rounded-full"
            style={{ background: 'var(--surface-2)', color: 'var(--dim)', border: '1px solid var(--border)' }}
          >
            {value} {label}
          </span>
        ))}
      </div>

      <h1 className="font-serif-kr text-3xl font-black leading-tight mb-2" style={{ color: 'var(--text)' }}>
        {"Today's Lotte Story Landscape"}
      </h1>
      <p className="text-sm leading-relaxed max-w-xl" style={{ color: 'var(--muted)' }}>
        Points closer together cover similar stories. Points sharing the same color belong to the same issue cluster. Select a cluster to read its brief.
      </p>
      <div className="h-px w-full mt-5" style={{ background: 'var(--border)' }} />
    </div>
  )
}
