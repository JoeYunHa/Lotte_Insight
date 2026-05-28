# Fan Voice Opinion Review - Deployment Checklist

**Date**: 2026-05-28
**Status**: Ready for Production
**Test Results**: 250/250 passing ✅

---

## Pre-Deployment Verification

- [x] All tests passing (250/250)
- [x] Code review completed (3 Critical + 4 Important issues fixed)
- [x] Migration files created and validated
- [x] Documentation updated

---

## Deployment Steps

### Step 1: Database Migrations (Supabase)

Execute in Supabase SQL Editor in this exact order:

#### Migration 1: Security Hardening for Existing RPCs
```bash
File: supabase/migrations/20260528_fan_voice_review_rpc.sql
```
**What it does**:
- Adds `security definer` to `aggregate_emotion_ranking` and `aggregate_player_ranking`
- Adds `set local search_path = public, pg_temp;` to prevent SQL injection
- Adds Python module reference comments

**Verification**:
```sql
-- Verify security settings
SELECT routine_name, security_type
FROM information_schema.routines
WHERE routine_name IN ('aggregate_emotion_ranking', 'aggregate_player_ranking');
-- Expected: security_type = 'DEFINER'
```

#### Migration 2: New Transaction-Safe RPC
```bash
File: supabase/migrations/20260528_fan_voice_review_replace_opinions_rpc.sql
```
**What it does**:
- Creates `replace_daily_opinions(p_review_id, p_opinions)` function
- Wraps DELETE + INSERT in single atomic transaction

**Verification**:
```sql
-- Verify function exists
SELECT routine_name, routine_type
FROM information_schema.routines
WHERE routine_name = 'replace_daily_opinions';
-- Expected: 1 row
```

---

### Step 2: Backend Deployment (Railway)

#### Option A: Auto-Deploy (Recommended)
```bash
# Push to main branch
git add .
git commit -m "Fix: All code review issues (3 Critical + 4 Important)"
git push origin main
# Railway auto-deploys
```

#### Option B: Manual Deploy
```bash
# Railway CLI
railway up
```

**Expected Changes**:
- New files: `scoring.py`, `cache_keys.py`
- Modified files: 8 files updated
- New tests: 22 tests added

---

### Step 3: Post-Deployment Verification

#### A. Health Check
```bash
# Check API is responsive
curl https://your-backend.railway.app/health
# Expected: {"status": "ok"}
```

#### B. Verify RPC Functions
```sql
-- In Supabase SQL Editor
SELECT routine_name, security_type
FROM information_schema.routines
WHERE routine_name LIKE '%opinion%' OR routine_name LIKE '%ranking%';

-- Expected output:
-- replace_daily_opinions | DEFINER
-- aggregate_emotion_ranking | DEFINER
-- aggregate_player_ranking | DEFINER
```

#### C. Test Opinion Review Endpoint
```bash
# GET request
curl https://your-backend.railway.app/fan-voice/opinion-review?scope=latest&context_type=home&context_id=today&review_type=final
# Should return valid review data or 404 if no data yet
```

#### D. Test Cache Key Format
```bash
# Check Redis for new cache key pattern
redis-cli KEYS "review:fanvoice:*"
# New keys should follow format: review:fanvoice:{context_type}:{context_id}:{date}:{review_type}

# Old keys (will auto-expire in 10 minutes)
redis-cli KEYS "fanvoice:review:*"
```

---

### Step 4: Monitoring (First 24 Hours)

#### Critical Metrics to Monitor

1. **API Error Rate**
   - Watch for validation errors from `OpinionClusterer._validate_messages()`
   - Expected: Near zero (unless data quality issues exist)

2. **Cache Hit Rate**
   - Monitor Redis hit/miss ratio
   - New key pattern: `review:fanvoice:*`
   - Expected: >80% hit rate after warmup

3. **Database RPC Performance**
   - Check execution time of `replace_daily_opinions`
   - Expected: <100ms for typical loads

4. **Transaction Success Rate**
   - Monitor for any transaction rollbacks
   - Expected: 100% success (atomic operations)

#### Monitoring Commands
```bash
# Railway logs
railway logs -f

# Redis stats
redis-cli INFO stats

# Database query stats (Supabase Dashboard)
# Navigate to: Database > Query Performance
```

---

## Rollback Plan

### If Critical Issues Arise

#### 1. Code Rollback (Railway)
```bash
# Identify last good commit
git log --oneline -10

# Rollback to previous commit
git revert HEAD
git push origin main
# Railway auto-deploys previous version
```

#### 2. Database Rollback (if needed)
```sql
-- Drop new RPC function (reversible)
DROP FUNCTION IF EXISTS replace_daily_opinions(bigint, jsonb);

-- Revert security changes (create old versions)
-- (Keep new versions, they're backwards compatible)
```

#### 3. Cache Flush (if needed)
```bash
# Clear all cache keys
redis-cli FLUSHDB

# Or just Fan Voice keys
redis-cli --scan --pattern "review:fanvoice:*" | xargs redis-cli DEL
```

---

## Common Issues & Solutions

### Issue 1: RPC Not Found
**Symptom**: `function replace_daily_opinions(bigint, jsonb) does not exist`

**Solution**:
```sql
-- Re-run migration
\i supabase/migrations/20260528_fan_voice_review_replace_opinions_rpc.sql
```

### Issue 2: Cache Keys Not Found
**Symptom**: Low cache hit rate

**Cause**: Key format changed from `fanvoice:review:*` to `review:fanvoice:*`

**Solution**: Wait 10 minutes for old keys to expire, or flush manually:
```bash
redis-cli --scan --pattern "fanvoice:review:*" | xargs redis-cli DEL
```

### Issue 3: Validation Errors in Clustering
**Symptom**: `ValueError: Message at index 0 missing required fields: {'id'}`

**Cause**: Data quality issue (messages missing `id` field)

**Solution**: Check data source and fix upstream:
```python
# Temporary workaround: filter out invalid messages before clustering
valid_messages = [m for m in messages if isinstance(m, dict) and 'id' in m]
```

### Issue 4: Score Calculation Mismatch
**Symptom**: Scores different from previous version

**Cause**: This should NOT happen (formulas unchanged)

**Solution**: Verify formula weights:
```python
from services.scoring import ReviewScoring
print(ReviewScoring.PLAYER_REACTION_WEIGHT)  # Should be 0.2
print(ReviewScoring.OPINION_MENTION_WEIGHT)  # Should be 0.7
print(ReviewScoring.OPINION_REACTION_WEIGHT) # Should be 0.3
```

---

## Post-Deployment Cleanup (After 24h)

### 1. Remove Old Cache Keys (Optional)
```bash
# After confirming new cache pattern works
redis-cli --scan --pattern "fanvoice:review:*" | xargs redis-cli DEL
```

### 2. Monitor Storage
```bash
# Check database size
SELECT pg_size_pretty(pg_database_size('postgres'));

# Check Redis memory usage
redis-cli INFO memory
```

### 3. Review Logs
```bash
# Check for any warnings or errors
railway logs --since 24h | grep -i "error\|warning"
```

---

## Success Criteria

Deployment is successful when:

- ✅ All migrations executed without errors
- ✅ API health check returns 200 OK
- ✅ All RPC functions exist with `DEFINER` security
- ✅ Cache hit rate >80% (after warmup)
- ✅ No validation errors in logs
- ✅ Transaction success rate 100%
- ✅ API response times normal (<500ms p95)

---

## Timeline

| Step | Time | Owner |
|------|------|-------|
| Database migrations | 5 min | DevOps |
| Code deployment | 3 min | Railway auto-deploy |
| Verification | 10 min | DevOps |
| Monitoring | 24 hours | DevOps + On-call |
| Cleanup | 5 min | DevOps (Day 2) |

**Total deployment time**: ~20 minutes
**Monitoring period**: 24 hours

---

## Contact

If issues arise:
1. Check this checklist first
2. Review `FAN_VOICE_REVIEW_FIXES_COMPLETE.md` for detailed context
3. Check individual fix summaries:
   - `CRITICAL_FIXES_SUMMARY.md`
   - `IMPORTANT_FIXES_SUMMARY.md`
4. Run test suite: `cd backend && pytest tests/ -v`

---

**Last Updated**: 2026-05-28
**Version**: 1.0
**Status**: Ready for Production ✅
