-- Triggers to keep tsvector columns up to date without heavy memory usage

-- For archon_crawled_pages: maintain content_search_vector on insert/update
CREATE OR REPLACE FUNCTION archon_crawled_pages_tsvector_update() RETURNS trigger AS $$
BEGIN
  NEW.content_search_vector := to_tsvector('english', COALESCE(NEW.content, ''));
  RETURN NEW;
END
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_archon_crawled_pages_tsv_update ON archon_crawled_pages;
CREATE TRIGGER trg_archon_crawled_pages_tsv_update
BEFORE INSERT OR UPDATE OF content ON archon_crawled_pages
FOR EACH ROW EXECUTE FUNCTION archon_crawled_pages_tsvector_update();

-- For archon_code_examples: maintain content_search_vector on insert/update
CREATE OR REPLACE FUNCTION archon_code_examples_tsvector_update() RETURNS trigger AS $$
BEGIN
  NEW.content_search_vector := to_tsvector('english', COALESCE(NEW.content,'') || ' ' || COALESCE(NEW.summary,''));
  RETURN NEW;
END
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_archon_code_examples_tsv_update ON archon_code_examples;
CREATE TRIGGER trg_archon_code_examples_tsv_update
BEFORE INSERT OR UPDATE OF content, summary ON archon_code_examples
FOR EACH ROW EXECUTE FUNCTION archon_code_examples_tsvector_update();

