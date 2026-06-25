DROP INDEX IF EXISTS sc.idx_stocks_favorited_at;

ALTER TABLE sc.stocks
  DROP COLUMN IF EXISTS favorited_at;
