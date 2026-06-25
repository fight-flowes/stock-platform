ALTER TABLE sc.stocks
  ADD COLUMN IF NOT EXISTS favorited_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_stocks_favorited_at
  ON sc.stocks(favorited_at DESC);

WITH ranked_favorites AS (
  SELECT
    id,
    ROW_NUMBER() OVER (ORDER BY id DESC) AS rn
  FROM sc.stocks
  WHERE is_favorite = TRUE
    AND favorited_at IS NULL
)
UPDATE sc.stocks AS stocks
SET favorited_at = NOW() - ((ranked_favorites.rn - 1) * INTERVAL '1 second')
FROM ranked_favorites
WHERE stocks.id = ranked_favorites.id;
