# Labeling Guide / 라벨링 가이드

## 1. Purpose / 목적

This guide defines how to classify KBO / Lotte Giants news articles based only on article metadata, especially the article title.

본 가이드는 기사 본문을 열람하지 않고, 기사 제목 등 제한된 메타데이터만을 기준으로 KBO / 롯데 자이언츠 관련 기사를 분류하기 위한 기준을 정의한다.

The goal is not to summarize the article, but to assign a consistent topic label for fan analytics, issue tracking, and record-based reporting.

목적은 기사 내용을 요약하는 것이 아니라, 팬 분석, 이슈 추적, 기록 기반 리포트 생성을 위해 일관된 주제 라벨을 부여하는 것이다.

---

## 2. Input Scope / 입력 범위

라벨링은 다음 정보만을 사용하여 수행한다.

- Article title / 기사 제목 [주요 입력]
- API-provided description snippet (≤120자) [보조 입력 — 저장 금지]
- Source or publisher / 언론사 [보조 입력]
- Published date and time / 발행 일시 [보조 입력]
- Article URL structure / URL 섹션 구조 [보조 입력]
- Known team/player dictionary / 팀·선수명 사전 [보조 입력]

description snippet은 라벨 판단에만 사용하며 DB에 저장하지 않는다.
제목만으로 confidence_score 0.7 이상 판단이 가능한 경우
description을 열람하지 않아도 된다.

---

## 3. Labeling Output / 라벨링 결과 형식

Each article should have one primary label and may have multiple secondary labels.

각 기사는 하나의 기본 라벨(primary label)을 가져야 하며, 필요한 경우 보조 라벨(secondary labels)을 여러 개 가질 수 있다.

| Field                 | Description                                                              |
| --------------------- | ------------------------------------------------------------------------ |
| `primary_label`       | The most dominant topic of the article title                             |
| `secondary_labels`    | Additional relevant labels, if any                                       |
| `confidence_score`    | Label confidence from 0.0 to 1.0                                         |
| `confidence_note`     | Reason for uncertainty, if confidence is low                             |
| `detected_players`    | Player names detected from the title                                     |
| `detected_team`       | Team name detected from the title                                        |
| `is_lotte_related`    | Whether the article is related to the Lotte Giants (see Section 7)       |
| `game_date_candidate` | Candidate game date inferred from title or published date, if applicable |

---

## 4. Label Definitions / 라벨 정의

| Label                  | Definition                                                                                                                                           | Typical Title Signals                                                            | Examples                                    |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- | ------------------------------------------- |
| `MATCH_RELATED`        | Articles mainly about a specific game, game result, lineup, starting pitcher, bullpen, batting order, win/loss, or game review                       | 경기, 승리, 패배, 선발, 불펜, 타선, 라인업, 연승, 연패, 끝내기, 역전, 완봉, 이닝 | "롯데, 삼성 꺾고 3연승"                     |
| `INJURY_ROSTER`        | Articles mainly about injury, rehabilitation, return from injury, roster registration, roster removal, call-up, demotion, or Futures League movement | 부상, 재활, 복귀, 말소, 등록, 콜업, 1군 합류, 2군행, 엔트리, 퓨처스              | "나승엽, 부상 회복 후 1군 복귀"             |
| `INTERVIEW`            | Articles mainly centered on direct comments from a manager, coach, player, or official                                                               | 인터뷰, 밝혔다, 말했다, 전했다, 설명했다, 강조했다, 따옴표 인용                  | "김태형 감독 '선발진 안정이 중요하다'"      |
| `PERFORMANCE_ANALYSIS` | Articles mainly interpreting statistics, records, rankings, trends, or performance metrics                                                           | 타율, ERA, OPS, WHIP, 홈런, 기록, 성적, 지표, 순위, 분석, 반등, 부진, 상승세     | "롯데 타선 OPS 리그 하위권, 반등 가능성은?" |
| `TRANSACTION_CONTRACT` | Articles about signing, release, trade, contract renewal, foreign player replacement, salary, or transfer                                            | 계약, 영입, 방출, 트레이드, 재계약, 연봉, 이적, 새 외국인                        | "롯데, 새 외국인 투수 영입"                 |
| `CLUB_OPERATION`       | Articles about club management, stadium, ticketing, fan events, marketing, uniforms, ceremonies, or non-game operations                              | 구단, 구장, 티켓, 팬 행사, 유니폼, 이벤트, 시구, 마케팅                          | "롯데, 주말 홈경기 팬 이벤트 개최"          |
| `ETC`                  | Articles that do not clearly fit the above categories or are too ambiguous from the title alone                                                      | 기타, 모호한 제목, 정보 부족                                                     | "롯데의 봄은 다시 시작된다"                 |

---

## 5. Primary Label Priority / 기본 라벨 우선순위

When multiple labels appear possible, choose the primary label using the following priority order.

여러 라벨이 동시에 가능할 경우, 아래 우선순위에 따라 기본 라벨을 선택한다.

```text
INJURY_ROSTER
→ TRANSACTION_CONTRACT
→ MATCH_RELATED
→ PERFORMANCE_ANALYSIS
→ INTERVIEW
→ CLUB_OPERATION
→ ETC
```

---

## 6. Edge Cases / 경계 케이스

라벨 간 혼동이 잦은 조합을 아래에 명시한다. 우선순위 규칙(Section 5)과 함께 참고한다.

### INTERVIEW vs MATCH_RELATED

경기 후 감독·선수 코멘트가 제목의 중심이면 `INTERVIEW`를 우선 부여한다.
경기 결과·흐름이 중심이고 발언이 부수적이면 `MATCH_RELATED`를 부여한다.

### INTERVIEW vs PERFORMANCE_ANALYSIS

발언 내용이 성적·지표를 언급하더라도 인용 구조가 중심이면 `INTERVIEW`를 부여한다.

### INJURY_ROSTER vs TRANSACTION_CONTRACT

부상·재활·엔트리 이동이 중심이면 `INJURY_ROSTER`, 계약·영입·방출이 중심이면 `TRANSACTION_CONTRACT`를 부여한다.

---

## 7. is_lotte_related 판단 기준

| 값      | 조건                                                      |
| ------- | --------------------------------------------------------- |
| `true`  | 롯데 소속 선수, 롯데 구단, 롯데 경기가 기사의 주체인 경우 |
| `false` | 롯데가 상대팀으로만 언급된 경우                           |
| `true`  | 롯데 출신 선수의 이적 직후 관련 기사 (맥락상 롯데가 주체) |
| `false` | KBO 전체 순위·기록 기사에서 롯데가 부수적으로 언급된 경우 |

판단이 어려운 경우 `confidence_note`에 사유를 기록하고 `confidence_score`를 0.5 이하로 표기한다.

---

## 8. Confidence Score Guidelines / 신뢰도 점수 기준

| 점수 범위  | 의미                                  | 조치                               |
| ---------- | ------------------------------------- | ---------------------------------- |
| 0.9 ~ 1.0  | 제목만으로 라벨이 명확히 결정됨       | 그대로 사용                        |
| 0.7 ~ 0.89 | 대체로 명확하나 일부 모호한 요소 존재 | 그대로 사용, 필요시 note 기록      |
| 0.5 ~ 0.69 | 두 라벨 간 경계에 있음                | `confidence_note`에 사유 기록 필수 |
| 0.5 미만   | 제목만으로 판단 불가                  | `ETC` 부여 또는 보류 후 재검토     |

---

## 9. Labeling Prohibitions / 라벨링 금지 사항

- 기사 본문 열람 후 라벨링 금지
- 추측성 내용을 근거로 라벨 부여 금지
- 동일 기사에 동일 라벨을 primary와 secondary에 중복 부여 금지
- `confidence_score` 0.5 미만임에도 `ETC` 없이 확정 라벨 부여 금지

---

## 10. Phase 5 Model Redesign Rules

These rules supersede older instructions when preparing new Phase 5 training data.

### Model Outputs

The maintained model targets are:

- `is_lotte_related`: binary flag for whether Lotte Giants, Lotte players/coaches, or a Lotte game are the main subject.
- `team_stance`: article tone/outcome toward the Lotte Giants team, one of `positive`, `neutral`, `negative`.
- `player_stance`: article tone/outcome toward the specific target player, one of `positive`, `neutral`, `negative`.

The old 7-class article classifier is no longer a training target. Topic labels may still be generated by GPT for reporting and sampling, but should not drive KoELECTRA/RoBERTa training.

### Input Fields

- Use `title + description_snippet` for `is_lotte_related` and `team_stance`.
- Use `title + target_player + description_snippet` for `player_stance`.
- Do not use `event_summary` for any supervised model label. It is GPT-generated and creates train/inference distribution mismatch.
- Do not infer from article body text unless the body is explicitly included in the row and the same field will be available at inference time.

### is_lotte_related

Use precision-first labeling:

- `true`: Lotte Giants are the subject, the Lotte game is the subject, or a current Lotte player/manager/coach is a main subject.
- `false`: Lotte is only an opponent, schedule context, list item, search keyword collision, or commercial Lotte entity.
- Borderline cases should be labeled `false` unless the title/snippet makes Lotte central.

### team_stance

- `positive`: win, strong performance, successful signing, meaningful return, favorable record, or clear team benefit.
- `negative`: loss, injury/roster setback, poor performance, failed signing, criticism, or clear team harm.
- `neutral`: previews, factual roster notices, interviews without clear evaluation, ambiguous or mixed outcome.

### player_stance

Label only for the `target_player`.

- `positive`: the target player performs well, returns successfully, receives praise, or contributes materially.
- `negative`: the target player performs poorly, is injured, demoted, released, criticized, or causes a negative outcome.
- `neutral`: mention is factual, expected lineup/rotation, quote context, or the article is about the team rather than the player.

If the target player is not actually present in title/snippet after alias resolution, leave `player_stance` blank rather than forcing `neutral`.

### Nicknames and Aliases

- Add recurring verified nicknames to `player_nicknames`.
- Do not add one-off puns or ambiguous common words as nicknames.
- GPT-discovered aliases require manual review before seeding.
