-- Harden replace_topic_map: pin search_path to prevent schema-injection via
-- SECURITY DEFINER functions without a fixed search_path.
--
-- PostgreSQL resolves unqualified names at execution time using the caller's
-- search_path when no SET search_path clause is present on a SECURITY DEFINER
-- function. A superuser or session that has altered search_path could shadow
-- public.article_topic_points / public.topic_clusters with pg_temp objects.
-- SET search_path = public, pg_temp eliminates that vector.
-- 실행 완료(2026-05-22)

CREATE OR REPLACE FUNCTION replace_topic_map(
  p_map_date    DATE,
  p_clusters    JSONB,  -- array of cluster row objects
  p_points      JSONB   -- array of point row objects
) RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
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

-- Re-grant execute (CREATE OR REPLACE preserves existing grants, but explicit
-- re-grant ensures correctness if the function was ever dropped and recreated)
GRANT EXECUTE ON FUNCTION replace_topic_map(DATE, JSONB, JSONB) TO service_role;
