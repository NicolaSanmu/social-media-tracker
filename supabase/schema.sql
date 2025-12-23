-- =====================================================
-- Social Media Tracker - Supabase Schema
-- =====================================================
-- Run this in Supabase SQL Editor (Dashboard > SQL Editor)
-- =====================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- 1. TABLES
-- =====================================================

-- Accounts table: stores tracked social media accounts
CREATE TABLE accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    platform TEXT NOT NULL CHECK (platform IN ('instagram', 'tiktok', 'youtube', 'twitter')),
    username TEXT NOT NULL,
    display_name TEXT,
    account_id TEXT, -- Platform-specific ID (e.g., YouTube channel ID)
    bio TEXT,
    profile_url TEXT,
    follower_count BIGINT DEFAULT 0,
    following_count BIGINT DEFAULT 0,
    post_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(platform, username)
);

-- Posts table: stores individual posts/videos
CREATE TABLE posts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    post_id TEXT NOT NULL, -- Platform-specific post ID
    post_type TEXT DEFAULT 'video', -- video, image, reel, story, tweet
    caption TEXT,
    url TEXT,
    thumbnail_url TEXT,
    duration INTEGER, -- Duration in seconds (for videos)
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(platform, post_id)
);

-- Post metrics table: time-series data for post performance
CREATE TABLE post_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    views BIGINT DEFAULT 0,
    likes BIGINT DEFAULT 0,
    comments BIGINT DEFAULT 0,
    shares BIGINT DEFAULT 0,
    saves BIGINT DEFAULT 0,
    engagement_rate DECIMAL(5,2), -- Calculated: (likes + comments) / views * 100
    collected_at TIMESTAMPTZ DEFAULT NOW()
);

-- Account metrics table: time-series data for account stats
CREATE TABLE account_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    follower_count BIGINT DEFAULT 0,
    following_count BIGINT DEFAULT 0,
    post_count INTEGER DEFAULT 0,
    total_views BIGINT DEFAULT 0,
    total_likes BIGINT DEFAULT 0,
    collected_at TIMESTAMPTZ DEFAULT NOW()
);

-- Collection logs table: track data collection runs
CREATE TABLE collection_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID REFERENCES accounts(id) ON DELETE SET NULL,
    platform TEXT,
    status TEXT CHECK (status IN ('success', 'failed', 'partial')),
    posts_collected INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);


-- =====================================================
-- 2. INDEXES (for query performance)
-- =====================================================

-- Accounts indexes
CREATE INDEX idx_accounts_platform ON accounts(platform);
CREATE INDEX idx_accounts_username ON accounts(username);
CREATE INDEX idx_accounts_created_at ON accounts(created_at DESC);

-- Posts indexes
CREATE INDEX idx_posts_account_id ON posts(account_id);
CREATE INDEX idx_posts_platform ON posts(platform);
CREATE INDEX idx_posts_published_at ON posts(published_at DESC);
CREATE INDEX idx_posts_account_published ON posts(account_id, published_at DESC);

-- Post metrics indexes
CREATE INDEX idx_post_metrics_post_id ON post_metrics(post_id);
CREATE INDEX idx_post_metrics_collected_at ON post_metrics(collected_at DESC);
CREATE INDEX idx_post_metrics_post_collected ON post_metrics(post_id, collected_at DESC);

-- Account metrics indexes
CREATE INDEX idx_account_metrics_account_id ON account_metrics(account_id);
CREATE INDEX idx_account_metrics_collected_at ON account_metrics(collected_at DESC);


-- =====================================================
-- 3. FUNCTIONS
-- =====================================================

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for accounts table
CREATE TRIGGER accounts_updated_at
    BEFORE UPDATE ON accounts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Function to get latest metrics for each post
CREATE OR REPLACE FUNCTION get_posts_with_latest_metrics(p_account_id UUID)
RETURNS TABLE (
    post_id UUID,
    platform TEXT,
    post_type TEXT,
    caption TEXT,
    url TEXT,
    published_at TIMESTAMPTZ,
    views BIGINT,
    likes BIGINT,
    comments BIGINT,
    shares BIGINT,
    saves BIGINT,
    collected_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT ON (p.id)
        p.id,
        p.platform,
        p.post_type,
        p.caption,
        p.url,
        p.published_at,
        pm.views,
        pm.likes,
        pm.comments,
        pm.shares,
        pm.saves,
        pm.collected_at
    FROM posts p
    LEFT JOIN post_metrics pm ON p.id = pm.post_id
    WHERE p.account_id = p_account_id
    ORDER BY p.id, pm.collected_at DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to get top posts by views
CREATE OR REPLACE FUNCTION get_top_posts(p_limit INTEGER DEFAULT 10)
RETURNS TABLE (
    post_id UUID,
    account_id UUID,
    platform TEXT,
    username TEXT,
    display_name TEXT,
    caption TEXT,
    url TEXT,
    published_at TIMESTAMPTZ,
    views BIGINT,
    likes BIGINT,
    comments BIGINT,
    shares BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT ON (p.id)
        p.id,
        a.id,
        p.platform,
        a.username,
        a.display_name,
        p.caption,
        p.url,
        p.published_at,
        pm.views,
        pm.likes,
        pm.comments,
        pm.shares
    FROM posts p
    JOIN accounts a ON p.account_id = a.id
    LEFT JOIN post_metrics pm ON p.id = pm.post_id
    ORDER BY p.id, pm.collected_at DESC, pm.views DESC NULLS LAST
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Function to get platform statistics
CREATE OR REPLACE FUNCTION get_platform_stats()
RETURNS TABLE (
    platform TEXT,
    account_count BIGINT,
    total_followers BIGINT,
    total_posts BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        a.platform,
        COUNT(*)::BIGINT as account_count,
        COALESCE(SUM(a.follower_count), 0)::BIGINT as total_followers,
        COALESCE(SUM(a.post_count), 0)::BIGINT as total_posts
    FROM accounts a
    GROUP BY a.platform
    ORDER BY account_count DESC;
END;
$$ LANGUAGE plpgsql;


-- =====================================================
-- 4. VIEWS (for common queries)
-- =====================================================

-- View: Posts with their latest metrics
CREATE OR REPLACE VIEW posts_with_metrics AS
SELECT DISTINCT ON (p.id)
    p.id,
    p.account_id,
    p.platform,
    p.post_id as platform_post_id,
    p.post_type,
    p.caption,
    p.url,
    p.thumbnail_url,
    p.duration,
    p.published_at,
    p.created_at,
    COALESCE(pm.views, 0) as views,
    COALESCE(pm.likes, 0) as likes,
    COALESCE(pm.comments, 0) as comments,
    COALESCE(pm.shares, 0) as shares,
    COALESCE(pm.saves, 0) as saves,
    pm.collected_at as metrics_collected_at
FROM posts p
LEFT JOIN post_metrics pm ON p.id = pm.post_id
ORDER BY p.id, pm.collected_at DESC NULLS LAST;

-- View: Dashboard summary
CREATE OR REPLACE VIEW dashboard_summary AS
SELECT
    (SELECT COUNT(*) FROM accounts) as total_accounts,
    (SELECT COUNT(*) FROM posts) as total_posts,
    (SELECT COALESCE(SUM(follower_count), 0) FROM accounts) as total_followers,
    (SELECT MAX(collected_at) FROM post_metrics) as last_collection_time;


-- =====================================================
-- 5. ROW LEVEL SECURITY (RLS)
-- =====================================================

-- Enable RLS on all tables
ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE post_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE account_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE collection_logs ENABLE ROW LEVEL SECURITY;

-- Public read access (for dashboard viewing without auth)
-- Note: Change these policies if you need authentication

CREATE POLICY "Allow public read access on accounts"
    ON accounts FOR SELECT
    USING (true);

CREATE POLICY "Allow public read access on posts"
    ON posts FOR SELECT
    USING (true);

CREATE POLICY "Allow public read access on post_metrics"
    ON post_metrics FOR SELECT
    USING (true);

CREATE POLICY "Allow public read access on account_metrics"
    ON account_metrics FOR SELECT
    USING (true);

CREATE POLICY "Allow public read access on collection_logs"
    ON collection_logs FOR SELECT
    USING (true);

-- Service role can do everything (for data collectors)
-- These use the service_role key, not anon key

CREATE POLICY "Service role full access on accounts"
    ON accounts FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access on posts"
    ON posts FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access on post_metrics"
    ON post_metrics FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access on account_metrics"
    ON account_metrics FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access on collection_logs"
    ON collection_logs FOR ALL
    USING (auth.role() = 'service_role');


-- =====================================================
-- 6. SAMPLE DATA (optional - for testing)
-- =====================================================

-- Uncomment to insert test data:
/*
INSERT INTO accounts (platform, username, display_name, follower_count, following_count, post_count, bio)
VALUES
    ('instagram', 'testuser1', 'Test User 1', 10000, 500, 100, 'This is a test account'),
    ('tiktok', 'testuser2', 'Test User 2', 50000, 200, 250, 'TikTok test account'),
    ('youtube', 'testchannel', 'Test Channel', 100000, 50, 500, 'YouTube test channel');
*/


-- =====================================================
-- DONE! Your Supabase database is ready.
-- =====================================================
