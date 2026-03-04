-- Sirus AI CRM — 数据库 Schema v1
-- 数据库: PostgreSQL 16 + pgvector
-- 运行位置: mac_min_8T (172.16.12.50)
-- 数据库名: ai_crm
-- 约定: UUID 主键、软删除(deleted_at)、created_at/updated_at 自动管理

-- ============================================================
-- 扩展
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";    -- pgvector

-- ============================================================
-- 用户表 (从钉钉同步)
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dingtalk_id     VARCHAR(64) UNIQUE,
    name            VARCHAR(100) NOT NULL,
    phone           VARCHAR(20),
    email           VARCHAR(200),
    department      VARCHAR(200),
    role            VARCHAR(50) DEFAULT 'sales',  -- admin / manager / sales
    avatar_url      TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 线索表
-- ============================================================
CREATE TABLE IF NOT EXISTS leads (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_name    VARCHAR(200) NOT NULL,
    contact_name    VARCHAR(100) NOT NULL,
    phone           VARCHAR(20),
    email           VARCHAR(200),
    source          VARCHAR(20) DEFAULT 'other',  -- website/exhibition/referral/cold_call/dingtalk/other
    industry        VARCHAR(100),
    status          VARCHAR(20) DEFAULT 'new',    -- new/contacted/qualified/converted/closed
    owner_id        UUID REFERENCES users(id),
    pool_id         UUID,                         -- 所属线索池
    ai_score        NUMERIC(5,2),                 -- AI评分 0-100
    ai_score_reason TEXT,                         -- AI评分理由
    notes           TEXT,
    tags            TEXT[] DEFAULT '{}',
    converted_at    TIMESTAMPTZ,                  -- 转化时间
    deleted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_leads_company ON leads(company_name) WHERE deleted_at IS NULL;
CREATE INDEX idx_leads_status ON leads(status) WHERE deleted_at IS NULL;
CREATE INDEX idx_leads_owner ON leads(owner_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_leads_created ON leads(created_at DESC) WHERE deleted_at IS NULL;

-- ============================================================
-- 客户表
-- ============================================================
CREATE TABLE IF NOT EXISTS customers (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_name    VARCHAR(200) NOT NULL,
    industry        VARCHAR(100),
    region          VARCHAR(100),
    level           VARCHAR(1) DEFAULT 'C',       -- S/A/B/C/D
    address         TEXT,
    website         VARCHAR(500),
    owner_id        UUID REFERENCES users(id),
    lead_id         UUID REFERENCES leads(id),    -- 转化来源
    ai_summary      TEXT,                         -- AI客户画像
    ai_embedding    vector(1024),                 -- 客户向量 (pgvector)
    notes           TEXT,
    tags            TEXT[] DEFAULT '{}',
    deleted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_customers_company ON customers(company_name) WHERE deleted_at IS NULL;
CREATE INDEX idx_customers_level ON customers(level) WHERE deleted_at IS NULL;
CREATE INDEX idx_customers_owner ON customers(owner_id) WHERE deleted_at IS NULL;

-- ============================================================
-- 联系人表
-- ============================================================
CREATE TABLE IF NOT EXISTS contacts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id     UUID NOT NULL REFERENCES customers(id),
    name            VARCHAR(100) NOT NULL,
    title           VARCHAR(100),
    department      VARCHAR(100),
    phone           VARCHAR(20),
    email           VARCHAR(200),
    is_decision_maker BOOLEAN DEFAULT FALSE,
    notes           TEXT,
    deleted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_contacts_customer ON contacts(customer_id) WHERE deleted_at IS NULL;

-- ============================================================
-- 商机表
-- ============================================================
CREATE TABLE IF NOT EXISTS opportunities (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                VARCHAR(200) NOT NULL,
    customer_id         UUID NOT NULL REFERENCES customers(id),
    owner_id            UUID REFERENCES users(id),
    amount              NUMERIC(15,2) DEFAULT 0,
    stage               VARCHAR(30) DEFAULT 'initial_contact',
                        -- initial_contact → needs_confirmed → solution_review → negotiation → won/lost
    product_type        VARCHAR(20) DEFAULT 'standard',  -- standard/custom
    expected_close_date DATE,
    win_rate            NUMERIC(5,2),            -- AI预测赢率
    lost_reason         TEXT,
    notes               TEXT,
    deleted_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_opp_customer ON opportunities(customer_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_opp_stage ON opportunities(stage) WHERE deleted_at IS NULL;
CREATE INDEX idx_opp_owner ON opportunities(owner_id) WHERE deleted_at IS NULL;

-- ============================================================
-- 活动表
-- ============================================================
CREATE TABLE IF NOT EXISTS activities (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    type            VARCHAR(20) NOT NULL,         -- call/visit/email/meeting/note
    subject         VARCHAR(200) NOT NULL,
    content         TEXT,
    user_id         UUID REFERENCES users(id),
    customer_id     UUID REFERENCES customers(id),
    opportunity_id  UUID REFERENCES opportunities(id),
    lead_id         UUID REFERENCES leads(id),
    scheduled_at    TIMESTAMPTZ,
    ai_summary      TEXT,                         -- AI活动摘要
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_activities_customer ON activities(customer_id);
CREATE INDEX idx_activities_opp ON activities(opportunity_id);
CREATE INDEX idx_activities_created ON activities(created_at DESC);

-- ============================================================
-- 审计日志表 (不可变，仅追加)
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID,
    action          VARCHAR(50) NOT NULL,         -- create/update/delete/convert/stage_change
    entity_type     VARCHAR(50) NOT NULL,         -- lead/customer/opportunity/activity
    entity_id       UUID NOT NULL,
    old_values      JSONB,
    new_values      JSONB,
    ip_address      VARCHAR(45),
    user_agent      VARCHAR(500),
    created_at      TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- 按月分区 (示例: 2026年3-6月)
CREATE TABLE audit_log_2026_03 PARTITION OF audit_log
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
CREATE TABLE audit_log_2026_04 PARTITION OF audit_log
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE audit_log_2026_05 PARTITION OF audit_log
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE audit_log_2026_06 PARTITION OF audit_log
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_user ON audit_log(user_id);

-- ============================================================
-- Agent 日志表
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      VARCHAR(100),
    user_id         UUID,
    message         TEXT NOT NULL,
    reply           TEXT,
    intent          VARCHAR(50),
    agent_used      VARCHAR(50),
    tool_calls      JSONB,
    model_used      VARCHAR(100),
    latency_ms      INTEGER,
    tokens_in       INTEGER,
    tokens_out      INTEGER,
    error           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_agent_log_session ON agent_log(session_id);
CREATE INDEX idx_agent_log_created ON agent_log(created_at DESC);

-- ============================================================
-- 更新 updated_at 触发器
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_leads_updated BEFORE UPDATE ON leads
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_customers_updated BEFORE UPDATE ON customers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_contacts_updated BEFORE UPDATE ON contacts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_opportunities_updated BEFORE UPDATE ON opportunities
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_users_updated BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
