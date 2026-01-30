-- =============================================
-- 1. EXTENSIONS
-- =============================================
-- Enable pgvector for semantic search
CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================
-- 2. MASTER ANCHOR TABLE (role_definitions)
-- Matches your RoleIngestor code
-- =============================================
CREATE TABLE IF NOT EXISTS role_definitions (
    job_title TEXT PRIMARY KEY,          -- The unique role name (e.g. "Senior Python Dev")
    internal_category TEXT,              -- e.g. "Software Engineering"
    priority_tier TEXT,                  -- e.g. "High", "Medium"
    anchor_embedding vector(768),        -- 768 dim for all-mpnet-base-v2
    full_definition JSONB,               -- The full KB blob (summary, skills, etc.)
    resume_keywords TEXT[]               -- Array of strings for keyword matching
);

-- Indexes for Role Definitions
-- Fast semantic search for roles
CREATE INDEX IF NOT EXISTS idx_role_anchor_vec 
    ON role_definitions USING hnsw (anchor_embedding vector_cosine_ops);

-- Fast filtering by JSON properties
CREATE INDEX IF NOT EXISTS idx_role_full_def_gin 
    ON role_definitions USING GIN (full_definition);

-- =============================================
-- 3. SCRAPED JOBS TABLE (job_embeddings)
-- Matches your Ingest Main code
-- =============================================
CREATE TABLE IF NOT EXISTS job_embeddings (
    job_id TEXT PRIMARY KEY,             -- Unique ID from source (e.g. SerpApi ID)
    job_title TEXT,                      -- Display title
    category TEXT,                       -- Filter category
    location TEXT,                       -- Filter location
    description_embedding vector(768),   -- The semantic vector of the job description
    metadata JSONB,                      -- Salary, link, posted_at, source
    ingestion_month TEXT                 -- Versioning (e.g. '2026-01-30')
);

-- Indexes for Job Embeddings
-- Critical: HNSW Index for finding similar jobs instantly
CREATE INDEX IF NOT EXISTS idx_job_desc_vec 
    ON job_embeddings USING hnsw (description_embedding vector_cosine_ops);

-- Index for cleanup/filtering by month
CREATE INDEX IF NOT EXISTS idx_job_ingest_month 
    ON job_embeddings (ingestion_month);