CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS incidents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  detected_at TIMESTAMPTZ DEFAULT NOW(),
  resource_type VARCHAR(50) NOT NULL,
  resource_name VARCHAR(255) NOT NULL,
  namespace VARCHAR(100) NOT NULL,
  problem_type VARCHAR(100) NOT NULL,
  severity VARCHAR(20) NOT NULL CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
  root_cause TEXT,
  confidence INTEGER CHECK (confidence BETWEEN 0 AND 100),
  auto_fixable BOOLEAN DEFAULT FALSE,
  fix_plan JSONB,
  prevention_tip TEXT,
  estimated_recovery VARCHAR(100),
  related_resources JSONB,
  status VARCHAR(30) DEFAULT 'open' CHECK (status IN (
    'open','diagnosing','needs_approval','fixing','fixed','still_broken','escalated','manual','skipped'
  )),
  resolved_at TIMESTAMPTZ,
  slack_message_ts VARCHAR(100),
  slack_channel VARCHAR(100),
  claude_prompt TEXT,
  claude_response TEXT,
  full_context JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fix_executions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  incident_id UUID REFERENCES incidents(id) ON DELETE CASCADE,
  executed_at TIMESTAMPTZ DEFAULT NOW(),
  fix_action VARCHAR(100) NOT NULL,
  fix_params JSONB,
  fix_description TEXT,
  kubectl_commands TEXT[],
  executed_by VARCHAR(50) DEFAULT 'auto',
  approver_slack_id VARCHAR(100),
  result VARCHAR(30) CHECK (result IN ('success','failed','partial','skipped')),
  verification_status VARCHAR(30) CHECK (verification_status IN ('fixed','still_broken','degraded','pending','skipped')),
  verified_at TIMESTAMPTZ,
  error_message TEXT,
  execution_duration_ms INTEGER
);

CREATE TABLE IF NOT EXISTS jenkins_incidents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  detected_at TIMESTAMPTZ DEFAULT NOW(),
  job_name VARCHAR(255) NOT NULL,
  build_number INTEGER,
  branch VARCHAR(255),
  commit_sha VARCHAR(100),
  failure_type VARCHAR(100),
  failing_stage VARCHAR(255),
  failing_line TEXT,
  ai_diagnosis JSONB,
  action_taken VARCHAR(100),
  retry_count INTEGER DEFAULT 0,
  resolved BOOLEAN DEFAULT FALSE,
  resolved_at TIMESTAMPTZ,
  github_issue_url VARCHAR(500),
  build_duration_seconds INTEGER,
  console_log_snippet TEXT
);

CREATE TABLE IF NOT EXISTS fix_patterns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  problem_pattern VARCHAR(100) NOT NULL,
  fix_action VARCHAR(100) NOT NULL,
  success_count INTEGER DEFAULT 0,
  failure_count INTEGER DEFAULT 0,
  last_used TIMESTAMPTZ,
  UNIQUE(problem_pattern, fix_action)
);

CREATE TABLE IF NOT EXISTS desired_state (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  recorded_at TIMESTAMPTZ DEFAULT NOW(),
  resource_type VARCHAR(50) NOT NULL,
  resource_name VARCHAR(255) NOT NULL,
  namespace VARCHAR(100) NOT NULL,
  spec_snapshot JSONB NOT NULL,
  image_tags JSONB,
  env_var_keys TEXT[],
  resource_limits JSONB,
  replica_count INTEGER,
  recorded_by VARCHAR(100) DEFAULT 'jenkins',
  UNIQUE(resource_type, resource_name, namespace)
);

CREATE TABLE IF NOT EXISTS drift_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  detected_at TIMESTAMPTZ DEFAULT NOW(),
  resource_type VARCHAR(50),
  resource_name VARCHAR(255),
  namespace VARCHAR(100),
  drift_type VARCHAR(100),
  old_value JSONB,
  new_value JSONB,
  auto_corrected BOOLEAN DEFAULT FALSE,
  corrected_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
CREATE INDEX IF NOT EXISTS idx_incidents_namespace ON incidents(namespace);
CREATE INDEX IF NOT EXISTS idx_incidents_severity ON incidents(severity);
CREATE INDEX IF NOT EXISTS idx_incidents_detected_at ON incidents(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_fix_executions_incident_id ON fix_executions(incident_id);
CREATE INDEX IF NOT EXISTS idx_jenkins_incidents_job_name ON jenkins_incidents(job_name);
CREATE INDEX IF NOT EXISTS idx_jenkins_incidents_detected_at ON jenkins_incidents(detected_at DESC);

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger
    WHERE tgname = 'incidents_updated_at'
  ) THEN
    CREATE TRIGGER incidents_updated_at
      BEFORE UPDATE ON incidents
      FOR EACH ROW EXECUTE FUNCTION update_updated_at();
  END IF;
END;
$$;
