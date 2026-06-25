CREATE TABLE IF NOT EXISTS sc.stock_groups (
  id SERIAL PRIMARY KEY,
  name VARCHAR(64) NOT NULL UNIQUE,
  description VARCHAR(255),
  color VARCHAR(32),
  sort_order INTEGER NOT NULL DEFAULT 0,
  is_pinned BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sc.stock_group_members (
  id SERIAL PRIMARY KEY,
  group_id INTEGER NOT NULL REFERENCES sc.stock_groups(id) ON DELETE CASCADE,
  stock_id INTEGER NOT NULL REFERENCES sc.stocks(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_stock_group_members UNIQUE (group_id, stock_id)
);

CREATE INDEX IF NOT EXISTS idx_stock_group_members_group_id
  ON sc.stock_group_members(group_id);

CREATE INDEX IF NOT EXISTS idx_stock_group_members_stock_id
  ON sc.stock_group_members(stock_id);

CREATE TABLE IF NOT EXISTS sc.stock_tags (
  id SERIAL PRIMARY KEY,
  name VARCHAR(64) NOT NULL UNIQUE,
  color VARCHAR(32),
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sc.stock_tag_bindings (
  id SERIAL PRIMARY KEY,
  stock_id INTEGER NOT NULL REFERENCES sc.stocks(id) ON DELETE CASCADE,
  tag_id INTEGER NOT NULL REFERENCES sc.stock_tags(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_stock_tag_bindings UNIQUE (stock_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_stock_tag_bindings_stock_id
  ON sc.stock_tag_bindings(stock_id);

CREATE INDEX IF NOT EXISTS idx_stock_tag_bindings_tag_id
  ON sc.stock_tag_bindings(tag_id);
