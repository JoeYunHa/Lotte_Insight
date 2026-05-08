import type { Article, LabelKey, Player, PlayerMention } from './types'

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
