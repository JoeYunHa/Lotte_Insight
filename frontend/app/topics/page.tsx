import { FanVoiceLayer } from '@/components/FanVoice/FanVoiceLayer'
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
        { href: '/', label: '오늘' },
        { href: '/players', label: '선수단' },
        { href: '/archive', label: '아카이브' },
      ]}
    >
      <TopicMapHero
        date={formatDateKo(today)}
        articleCount={articleCount}
        clusterCount={clusterCount}
        outlierCount={outlierCount}
      />

      <FanVoiceLayer contextType="topic" contextId={data?.map_date ?? today} />

      {fetchError ? (
        <div
          className="rounded-[28px] p-10 text-center"
          style={{ background: 'rgba(248,113,113,0.07)', border: '1px solid rgba(248,113,113,0.25)' }}
        >
          <p className="text-sm font-medium mb-2" style={{ color: '#f87171' }}>
            백엔드 연결 실패
          </p>
          <p className="text-xs leading-6 max-w-sm mx-auto" style={{ color: 'var(--muted)' }}>
            토픽 맵 API가 예상치 못한 오류를 반환했습니다. 백엔드가 실행 중이고 API URL이 올바르게 설정되었는지 확인하세요.
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
            오늘의 토픽 맵이 아직 없습니다
          </p>
          <p className="text-xs leading-6 max-w-sm mx-auto" style={{ color: 'var(--muted)' }}>
            클러스터링 파이프라인은 기사 수집이 완료된 후 실행됩니다. 일일 배치가 완료되면 다시 확인하세요.
          </p>
        </div>
      )}
    </PageShell>
  )
}
