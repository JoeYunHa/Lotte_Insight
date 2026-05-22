import { PageShell } from '@/components/PageShell'
import { TopicMapExplorer } from '@/components/TopicMapExplorer'
import { TopicMapHero } from '@/components/TopicMapHero'
import { getTopicMap } from '@/lib/api'
import { formatDateKo, getTodayKST } from '@/lib/time'

export const dynamic = 'force-dynamic'

export default async function TopicsPage() {
  const today = getTodayKST()

  let data = null
  let fetchError = false
  try {
    data = await getTopicMap(today)
  } catch {
    fetchError = true
  }

  const clusterCount = data?.clusters.length ?? 0
  const outlierCount = data?.points.filter((p) => p.is_outlier).length ?? 0
  const articleCount = data?.points.length ?? 0

  return (
    <PageShell
      headerActions={[
        { href: '/', label: 'Today' },
        { href: '/players', label: 'Players' },
        { href: '/archive', label: 'Archive' },
      ]}
    >
      <TopicMapHero
        date={formatDateKo(today)}
        articleCount={articleCount}
        clusterCount={clusterCount}
        outlierCount={outlierCount}
      />

      {fetchError ? (
        <div
          className="rounded-[28px] p-10 text-center"
          style={{ background: 'rgba(248,113,113,0.07)', border: '1px solid rgba(248,113,113,0.25)' }}
        >
          <p className="text-sm font-medium mb-2" style={{ color: '#f87171' }}>
            Backend unreachable
          </p>
          <p className="text-xs leading-6 max-w-sm mx-auto" style={{ color: 'var(--muted)' }}>
            The topic map API returned an unexpected error. Check that the backend is running and the API URL is configured correctly.
          </p>
        </div>
      ) : data && data.points.length > 0 ? (
        <TopicMapExplorer data={data} />
      ) : (
        <div
          className="rounded-[28px] p-10 text-center"
          style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
        >
          <p className="text-sm font-medium mb-2" style={{ color: 'var(--text)' }}>
            No topic map for today yet
          </p>
          <p className="text-xs leading-6 max-w-sm mx-auto" style={{ color: 'var(--muted)' }}>
            The clustering pipeline runs after article collection finishes. Come back once the daily batch is complete.
          </p>
        </div>
      )}
    </PageShell>
  )
}
