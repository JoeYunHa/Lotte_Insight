-- Atomic topic map replacement RPC
-- delete + insert for a single map_date wrapped in one transaction,
-- so a mid-write failure never leaves the date's data partially wiped.
--
-- Supabase SQL Editor에서 실행 후 backend/_replace_topic_map()에서 호출됨.
-- 실행 완료(2026-05-22)

CREATE OR REPLACE FUNCTION replace_topic_map(
  p_map_date    DATE,
  p_clusters    JSONB,  -- array of cluster row objects
  p_points      JSONB   -- array of point row objects
) RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  -- Delete existing rows for this date (points first, clusters second
  -- to avoid FK violation on topic_clusters.id)
  DELETE FROM article_topic_points WHERE map_date = p_map_date;
  DELETE FROM topic_clusters        WHERE map_date = p_map_date;

  -- Insert clusters
  INSERT INTO topic_clusters (
    id, map_date, article_count, representative_article_id,
    title, summary, label_hint, key_players
  )
  SELECT
    (row_data->>'id'),
    p_map_date,
    (row_data->>'article_count')::INTEGER,
    (row_data->>'representative_article_id')::UUID,
    (row_data->>'title'),
    (row_data->>'summary'),
    (row_data->>'label_hint'),
    ARRAY(SELECT jsonb_array_elements_text(row_data->'key_players'))
  FROM jsonb_array_elements(p_clusters) AS row_data;

  -- Insert topic points
  INSERT INTO article_topic_points (
    map_date, article_id, cluster_id, cluster_rank,
    x, y, embedding_model, projection_model, is_outlier
  )
  SELECT
    p_map_date,
    (row_data->>'article_id')::UUID,
    NULLIF(row_data->>'cluster_id', 'null'),
    NULLIF(row_data->>'cluster_rank', 'null')::INTEGER,
    (row_data->>'x')::DOUBLE PRECISION,
    (row_data->>'y')::DOUBLE PRECISION,
    (row_data->>'embedding_model'),
    (row_data->>'projection_model'),
    (row_data->>'is_outlier')::BOOLEAN
  FROM jsonb_array_elements(p_points) AS row_data;
END;
$$;

-- Grant execute to the service role used by the backend
GRANT EXECUTE ON FUNCTION replace_topic_map(DATE, JSONB, JSONB) TO service_role;
