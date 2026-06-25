CREATE TABLE IF NOT EXISTS sc.stock_notes (
  id SERIAL PRIMARY KEY,
  stock_id INTEGER NOT NULL REFERENCES sc.stocks(id) ON DELETE CASCADE,
  note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_stock_notes_stock_id UNIQUE (stock_id)
);

CREATE INDEX IF NOT EXISTS idx_stock_notes_stock_id
  ON sc.stock_notes(stock_id);
