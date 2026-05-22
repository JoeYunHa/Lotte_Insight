import type { Article, LabelKey, Player, PlayerMention } from './types'

export interface SentimentRatio {
  positive: number  // ratio out of analyzed articles only
  neutral: number
  negative: number
  analyzed: number  // articles with lotte_stance populated
}

export function computeSentiment(articles: Article[]): SentimentRatio {
  let positive = 0, neutral = 0, negative = 0
  for (const a of articles) {
    if (a.lotte_stance === 'positive') positive++
    else if (a.lotte_stance === 'negative') negative++
    else if (a.lotte_stance === 'neutral') neutral++
  }
  const analyzed = positive + neutral + negative
  return {
    positive: analyzed ? positive / analyzed : 0,
    neutral: analyzed ? neutral / analyzed : 0,
    negative: analyzed ? negative / analyzed : 0,
    analyzed,
  }
}

export function getLeadLabel(labelCounts: Record<LabelKey, number>): LabelKey | null {
  const entries = Object.entries(labelCounts) as [LabelKey, number][]
  const sorted = entries.filter(([, count]) => count > 0).sort(([, a], [, b]) => b - a)
  return sorted[0]?.[0] ?? null
}

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

  for (const article of articles) {
    if (article.primary_label) counts[article.primary_label]++
  }

  return counts
}

export function getTopMentionedPlayersFromArticles(
  articles: Article[],
  players: Player[],
  limit = 5
): PlayerMention[] {
  const counts = new Map<string, PlayerMention>()
  const playerById = new Map<string, Player>()

  for (const player of players) {
    playerById.set(player.id, player)
  }

  for (const article of articles) {
    // Deduplicate player mentions within a single article
    const seen = new Set<string>()
    for (const ap of article.article_players ?? []) {
      if (!ap.players) continue
      const pid = String(ap.player_id)
      if (seen.has(pid)) continue
      seen.add(pid)

      const player = playerById.get(pid)
      if (!player) continue

      const current = counts.get(pid)
      if (current) {
        current.mention_count += 1
      } else {
        counts.set(pid, {
          player: { id: player.id, name: player.name, position: player.position },
          mention_count: 1,
        })
      }
    }
  }

  return [...counts.values()]
    .sort((a, b) => b.mention_count - a.mention_count)
    .slice(0, limit)
}
