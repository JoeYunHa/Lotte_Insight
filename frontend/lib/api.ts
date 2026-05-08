/**
 * Data-fetching layer.
 *
 * ── HOW TO SWITCH FROM MOCK TO REAL API ───────────────────────────────────────
 * 1. Set NEXT_PUBLIC_API_URL in frontend/.env.local (e.g. http://localhost:8000)
 * 2. Each function below checks USE_MOCK first. When API_BASE is defined it calls
 *    the real FastAPI backend instead of returning mock data.
 * 3. The backend endpoint each function maps to is documented with a comment.
 * ─────────────────────────────────────────────────────────────────────────────
 */

import type {
  Article,
  LabelKey,
  Player,
  PlayerDailyReport,
  PlayerMention,
  PlayerStatDaily,
  TeamDailyReport,
} from './types'

// ── Config ────────────────────────────────────────────────────────────────────

const API_BASE = process.env.NEXT_PUBLIC_API_URL
const USE_MOCK = !API_BASE

// Next.js ISR: revalidate cached responses every 5 minutes.
// Increase for past dates (they don't change) — TODO once real API is wired up.
const FETCH_OPTIONS: RequestInit = { next: { revalidate: 300 } }

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, FETCH_OPTIONS)
  if (!res.ok) throw new Error(`GET ${path} → HTTP ${res.status}`)
  return res.json() as Promise<T>
}

// ── Team Reports ──────────────────────────────────────────────────────────────
// Backend: GET /reports/team/{date}

export async function getTeamReport(date: string): Promise<TeamDailyReport | null> {
  if (!USE_MOCK) return get<TeamDailyReport>(`/reports/team/${date}`)
  return mockTeamReports.find(r => r.date === date) ?? null
}

// Backend: GET /reports/team?limit=N
export async function getTeamReports(limit = 60): Promise<TeamDailyReport[]> {
  if (!USE_MOCK) return get<TeamDailyReport[]>(`/reports/team?limit=${limit}`)
  return mockTeamReports.slice(0, limit)
}

// ── Articles ──────────────────────────────────────────────────────────────────
// Backend: GET /articles?date=YYYY-MM-DD&label=X&player_id=Y

export async function getArticles(params: {
  date?: string
  label?: LabelKey
  player_id?: string
} = {}): Promise<Article[]> {
  if (!USE_MOCK) {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v != null) as [string, string][]
    )
    return get<Article[]>(`/articles?${qs}`)
  }
  let list = mockArticles
  if (params.date) {
    list = list.filter(a => a.published_at.startsWith(params.date!))
  }
  if (params.label) {
    list = list.filter(a => a.primary_label === params.label)
  }
  return list
}

// ── Players ───────────────────────────────────────────────────────────────────
// Backend: GET /players

export async function getPlayers(): Promise<Player[]> {
  if (!USE_MOCK) return get<Player[]>('/players')
  return mockPlayers
}

// Backend: GET /players/{id}
export async function getPlayer(id: string): Promise<Player | null> {
  if (!USE_MOCK) return get<Player>(`/players/${id}`)
  return mockPlayers.find(p => p.id === id) ?? null
}

// ── Player Reports ────────────────────────────────────────────────────────────
// Backend: GET /reports/players/{id}/{date}

export async function getPlayerReport(
  playerId: string,
  date: string
): Promise<PlayerDailyReport | null> {
  if (!USE_MOCK) return get<PlayerDailyReport>(`/reports/players/${playerId}/${date}`)
  return mockPlayerReports.find(r => r.player_id === playerId && r.date === date) ?? null
}

// ── Player Stats ──────────────────────────────────────────────────────────────
// Backend: GET /players/{id}/stats/{date}  (not yet implemented — returns null)

export async function getPlayerStats(
  playerId: string,
  date: string
): Promise<PlayerStatDaily | null> {
  if (!USE_MOCK) return null  // TODO: implement when backend endpoint exists
  return mockPlayerStats.find(s => s.player_id === playerId && s.date === date) ?? null
}

// ── Derived helpers ───────────────────────────────────────────────────────────
// These aggregate article_players data.
// Backend equivalent: article_players JOIN players GROUP BY player_id.

export async function getTopMentionedPlayers(
  date: string,
  limit = 5
): Promise<PlayerMention[]> {
  if (!USE_MOCK) {
    // TODO: add GET /articles/top-players?date=X&limit=N to the backend,
    // or derive from getArticles() + getPlayers() when the endpoint isn't ready.
    return []
  }
  return mockTopPlayers.slice(0, limit)
}

// ── Label count helper (derived from articles) ───────────────────────────────

export function computeLabelCounts(articles: Article[]): Record<LabelKey, number> {
  const counts: Record<LabelKey, number> = {
    MATCH_RELATED: 0,
    INJURY_ROSTER: 0,
    TRANSACTION_CONTRACT: 0,
    PERFORMANCE_ANALYSIS: 0,
    INTERVIEW: 0,
    CLUB_OPERATION: 0,
    ETC: 0,
  }
  for (const a of articles) {
    if (a.primary_label) counts[a.primary_label]++
  }
  return counts
}

// ═════════════════════════════════════════════════════════════════════════════
// Mock data — remove this entire section once the real API is wired up.
// ═════════════════════════════════════════════════════════════════════════════

const TODAY = '2026-05-08'

const mockArticles: Article[] = [
  {
    id: '1', title: '롯데, 삼성 원정 7-4 역전승... 안치홍 6회 쐐기 2점포',
    source_name: '스포츠조선', source_url: '#',
    published_at: `${TODAY}T07:00:00Z`,
    primary_label: 'MATCH_RELATED', lotte_stance: '긍정',
    event_summary: '롯데가 6회 안치홍의 결승 2점 홈런을 앞세워 삼성을 7-4로 역전, 시즌 3연승을 달렸다.',
    key_players: ['안치홍', '윤동희', '한현희'],
  },
  {
    id: '2', title: '나균안, 오른 어깨 통증 호소... 15일 재활 말소',
    source_name: '뉴스1', source_url: '#',
    published_at: `${TODAY}T05:00:00Z`,
    primary_label: 'INJURY_ROSTER', lotte_stance: '부정',
    event_summary: '나균안 선수가 어깨 통증으로 1군 엔트리에서 말소되어 재활 일정에 들어갔다.',
    key_players: ['나균안'],
  },
  {
    id: '3', title: '안치홍 인터뷰 "3연승 분위기 좋아, 우승 도전하겠다"',
    source_name: 'OSEN', source_url: '#',
    published_at: `${TODAY}T04:00:00Z`,
    primary_label: 'INTERVIEW', lotte_stance: '긍정',
    event_summary: '안치홍이 3연승 후 팀 분위기와 우승 의지를 밝혔다.',
    key_players: ['안치홍'],
  },
  {
    id: '4', title: '윤동희 OPS .891, 타격 10걸 진입... 커리어 하이 페이스',
    source_name: '스포츠서울', source_url: '#',
    published_at: `${TODAY}T03:00:00Z`,
    primary_label: 'PERFORMANCE_ANALYSIS', lotte_stance: '긍정',
    event_summary: '윤동희가 OPS .891로 리그 타격 10걸에 진입하며 커리어 하이 페이스를 이어가고 있다.',
    key_players: ['윤동희'],
  },
  {
    id: '5', title: '롯데, 외국인 타자 교체 검토... 오펜토파드 성적 부진',
    source_name: '일간스포츠', source_url: '#',
    published_at: `${TODAY}T01:00:00Z`,
    primary_label: 'TRANSACTION_CONTRACT', lotte_stance: '중립',
    event_summary: '롯데 구단이 외국인 타자 오펜토파드의 성적 부진을 이유로 교체를 검토 중이다.',
    key_players: ['오펜토파드'],
  },
  {
    id: '6', title: '사직구장 5월 홈 경기 매진 행진... 팬 열기 최고조',
    source_name: '부산일보', source_url: '#',
    published_at: `${TODAY}T00:30:00Z`,
    primary_label: 'CLUB_OPERATION', lotte_stance: '긍정',
    event_summary: '사직구장 5월 홈 경기 전 일정이 매진을 기록하며 팬들의 응원 열기가 달아오르고 있다.',
    key_players: [],
  },
  {
    id: '7', title: '류현진 말소 후 선발진 공백... 고승민 콜업 논의',
    source_name: '스포탈코리아', source_url: '#',
    published_at: `${TODAY}T00:00:00Z`,
    primary_label: 'INJURY_ROSTER', lotte_stance: '부정',
    event_summary: '류현진 부상 말소로 생긴 선발진 공백을 메우기 위해 고승민 2군 콜업이 논의 중이다.',
    key_players: ['류현진', '고승민'],
  },
  {
    id: '8', title: '롯데 마운드 평균자책 3.82, 10개 구단 중 4위',
    source_name: 'KBO스탯', source_url: '#',
    published_at: `2026-05-07T23:00:00Z`,
    primary_label: 'PERFORMANCE_ANALYSIS', lotte_stance: '긍정',
    event_summary: '롯데 투수진이 평균자책 3.82로 리그 4위를 기록하며 안정적인 마운드 운영을 이어가고 있다.',
    key_players: [],
  },
]

const mockTeamReports: TeamDailyReport[] = [
  { id: 'tr1', date: '2026-05-08', issue_summary: '롯데, 삼성 원정 7-4 역전승으로 3연승. 안치홍 2점 홈런, 윤동희 3안타 멀티히트 활약. 한현희 1이닝 무실점 마무리. 5위 KT에 1게임 차 4위.', article_count: 23, top_labels: ['MATCH_RELATED', 'INJURY_ROSTER', 'PERFORMANCE_ANALYSIS'] },
  { id: 'tr2', date: '2026-05-07', issue_summary: '삼성전 5-2 완승. 박세웅 6이닝 2실점 호투, 윤동희 3안타.', article_count: 19, top_labels: ['MATCH_RELATED', 'PERFORMANCE_ANALYSIS'] },
  { id: 'tr3', date: '2026-05-06', issue_summary: 'kt 원정 4-3 짜릿한 역전승. 9회 안치홍 결승타.', article_count: 17, top_labels: ['MATCH_RELATED', 'INTERVIEW'] },
  { id: 'tr4', date: '2026-05-05', issue_summary: '休경기일. 나균안 어깨 재활 이슈 보도.', article_count: 8, top_labels: ['INJURY_ROSTER', 'TRANSACTION_CONTRACT'] },
  { id: 'tr5', date: '2026-05-04', issue_summary: 'kt 홈 2-6 패. 선발진 난조, 불펜 3실점 추가.', article_count: 14, top_labels: ['MATCH_RELATED', 'PERFORMANCE_ANALYSIS'] },
  { id: 'tr6', date: '2026-05-03', issue_summary: 'NC전 1-4 완패. 류현진 어깨 통증 조기 강판.', article_count: 11, top_labels: ['MATCH_RELATED', 'INJURY_ROSTER'] },
  { id: 'tr7', date: '2026-05-02', issue_summary: 'NC 원정 6-2 승. 한현희 세이브 10호 달성.', article_count: 18, top_labels: ['MATCH_RELATED', 'INTERVIEW'] },
  { id: 'tr8', date: '2026-05-01', issue_summary: '5월 홈 개막, 두산전 3-1 승. 사직구장 만원 관중.', article_count: 21, top_labels: ['MATCH_RELATED', 'CLUB_OPERATION'] },
  { id: 'tr9', date: '2026-04-30', issue_summary: '두산전 3-3 무. 연장 12회까지 접전.', article_count: 9, top_labels: ['MATCH_RELATED'] },
  { id: 'tr10', date: '2026-04-29', issue_summary: '두산 홈 4-7 패. 타선 5이닝 침묵.', article_count: 13, top_labels: ['MATCH_RELATED', 'PERFORMANCE_ANALYSIS'] },
  { id: 'tr11', date: '2026-04-28', issue_summary: '休경기일. 외국인 타자 교체 검토 보도.', article_count: 6, top_labels: ['TRANSACTION_CONTRACT'] },
  { id: 'tr12', date: '2026-04-27', issue_summary: '한화전 7-3 쾌승. 이대호 2홈런 폭발.', article_count: 15, top_labels: ['MATCH_RELATED', 'INTERVIEW'] },
]

const mockPlayers: Player[] = [
  { id: '1', name: '안치홍', name_variants: ['안치홍'], position: '2루수', status: '1군', number: '25' },
  { id: '2', name: '윤동희', name_variants: ['윤동희'], position: '중견수', status: '1군', number: '51' },
  { id: '3', name: '한현희', name_variants: ['한현희'], position: '마무리투수', status: '1군', number: '37' },
  { id: '4', name: '나균안', name_variants: ['나균안'], position: '투수', status: '말소', number: '17' },
  { id: '5', name: '이대호', name_variants: ['이대호'], position: '1루수', status: '1군', number: '10' },
]

const mockPlayerReports: PlayerDailyReport[] = [
  { id: 'pr1', player_id: '1', date: TODAY, insight: '안치홍이 삼성전 결승 2점 홈런(시즌 7호)으로 3연승을 견인했다. 최근 5경기 타율 .381로 뜨거운 방망이를 이어가고 있으며, OPS .831로 리그 중견 타자 상위권에 위치한다.', stat_snapshot: { avg: 0.291, ops: 0.831 } },
  { id: 'pr2', player_id: '2', date: TODAY, insight: '윤동희가 OPS .891로 타격 10걸에 진입하며 커리어 하이 시즌을 보내고 있다. 삼성전 3안타 멀티히트로 팀의 역전승을 도왔다.', stat_snapshot: { avg: 0.318, ops: 0.891 } },
  { id: 'pr3', player_id: '3', date: TODAY, insight: '한현희가 삼성전 9회 1이닝 무실점으로 시즌 12세이브를 기록했다. 평균자책 2.14로 리그 최상급 마무리 자리를 유지 중이며, 최근 12경기 연속 무실점이다.', stat_snapshot: { era: 2.14 } },
]

const mockPlayerStats: PlayerStatDaily[] = [
  { player_id: '1', date: TODAY, avg: 0.291, ops: 0.831, raw_stats: { rbi: 34, hr: 7 } },
  { player_id: '2', date: TODAY, avg: 0.318, ops: 0.891, raw_stats: { rbi: 28, sb: 9 } },
  { player_id: '3', date: TODAY, era: 2.14, raw_stats: { sv: 12, k: 28 } },
  { player_id: '4', date: TODAY, era: 3.80, raw_stats: { w: 3, k: 22 } },
]

const mockTopPlayers: PlayerMention[] = [
  { player: { id: '1', name: '안치홍', position: '2루수' }, mention_count: 8 },
  { player: { id: '2', name: '윤동희', position: '중견수' }, mention_count: 6 },
  { player: { id: '3', name: '한현희', position: '마무리투수' }, mention_count: 5 },
  { player: { id: '4', name: '나균안', position: '투수' }, mention_count: 4 },
  { player: { id: '5', name: '이대호', position: '1루수' }, mention_count: 3 },
]
