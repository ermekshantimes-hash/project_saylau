-- Миграция для таблицы audit_events (Task #10)
-- Append-only лог с hash chains для проверки целостности

-- Таблица audit_events уже создана в migration_rbac.sql
-- Но на случай если её нет, создаём с проверкой:

DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'audit_events') THEN
        CREATE TABLE audit_events (
            id SERIAL PRIMARY KEY,
            actor_user_id INT REFERENCES users(id) ON DELETE SET NULL,
            scope audit_scope NOT NULL,
            event_type VARCHAR(100) NOT NULL,
            payload_json JSONB NOT NULL DEFAULT '{}',
            ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            hash VARCHAR(64) NOT NULL,  -- SHA256 хеш события
            prev_hash VARCHAR(64),      -- Хеш предыдущего события для цепочки
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Индексы для быстрого поиска
        CREATE INDEX idx_audit_actor ON audit_events(actor_user_id);
        CREATE INDEX idx_audit_scope ON audit_events(scope);
        CREATE INDEX idx_audit_type ON audit_events(event_type);
        CREATE INDEX idx_audit_ts ON audit_events(ts);
        CREATE INDEX idx_audit_hash ON audit_events(hash);
        
        RAISE NOTICE 'Table audit_events created';
    ELSE
        RAISE NOTICE 'Table audit_events already exists';
    END IF;
END $$;

-- Индексы для JSONB payload (GIN)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes WHERE indexname = 'idx_audit_payload_gin'
    ) THEN
        CREATE INDEX idx_audit_payload_gin ON audit_events USING gin(payload_json jsonb_path_ops);
        RAISE NOTICE 'GIN index on payload_json created';
    END IF;
END $$;

-- Функция для проверки целостности цепочки
CREATE OR REPLACE FUNCTION verify_audit_chain_integrity(start_id INT DEFAULT NULL, end_id INT DEFAULT NULL)
RETURNS TABLE(
    event_id INT,
    issue_type VARCHAR,
    expected_value VARCHAR,
    actual_value VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    WITH events AS (
        SELECT 
            id,
            hash,
            prev_hash,
            LAG(hash) OVER (ORDER BY id) as expected_prev_hash
        FROM audit_events
        WHERE (start_id IS NULL OR id >= start_id)
          AND (end_id IS NULL OR id <= end_id)
        ORDER BY id
    )
    SELECT 
        e.id::INT as event_id,
        'prev_hash_mismatch'::VARCHAR as issue_type,
        e.expected_prev_hash::VARCHAR as expected_value,
        e.prev_hash::VARCHAR as actual_value
    FROM events e
    WHERE e.prev_hash IS DISTINCT FROM e.expected_prev_hash;
END;
$$ LANGUAGE plpgsql;

-- View for recent audit events
CREATE OR REPLACE VIEW v_recent_audit_events AS
SELECT 
    ae.id,
    ae.actor_user_id,
    u.phone as actor_phone,
    ae.scope,
    ae.event_type,
    ae.payload_json,
    ae.ts,
    ae.hash
FROM audit_events ae
LEFT JOIN users u ON ae.actor_user_id = u.id
ORDER BY ae.id DESC
LIMIT 1000;

-- Trigger to prevent modification/deletion of records (append-only)
CREATE OR REPLACE FUNCTION prevent_audit_modification()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Delete operation forbidden on audit_events (append-only log)';
    END IF;
    
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'Update operation forbidden on audit_events (append-only log)';
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'audit_events_immutable'
    ) THEN
        CREATE TRIGGER audit_events_immutable
            BEFORE UPDATE OR DELETE ON audit_events
            FOR EACH ROW
            EXECUTE FUNCTION prevent_audit_modification();
        
        RAISE NOTICE 'Trigger for audit_events protection created';
    END IF;
END $$;

-- Функция для статистики аудита
CREATE OR REPLACE FUNCTION get_audit_statistics()
RETURNS TABLE(
    metric VARCHAR,
    value BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 'total_events'::VARCHAR, COUNT(*)::BIGINT FROM audit_events
    UNION ALL
    SELECT 'events_last_24h'::VARCHAR, COUNT(*)::BIGINT 
    FROM audit_events 
    WHERE ts >= NOW() - INTERVAL '24 hours'
    UNION ALL
    SELECT 'events_last_7d'::VARCHAR, COUNT(*)::BIGINT 
    FROM audit_events 
    WHERE ts >= NOW() - INTERVAL '7 days'
    UNION ALL
    SELECT 'unique_actors'::VARCHAR, COUNT(DISTINCT actor_user_id)::BIGINT 
    FROM audit_events
    UNION ALL
    SELECT 'system_events'::VARCHAR, COUNT(*)::BIGINT 
    FROM audit_events 
    WHERE scope = 'SYSTEM';
END;
$$ LANGUAGE plpgsql;

-- Create test records to verify chain
DO $$
DECLARE
    prev_hash_val VARCHAR(64) := NULL;
    current_hash VARCHAR(64);
    event_data TEXT;
BEGIN
    -- Event 1: System initialization
    event_data := '{"actor_user_id":null,"scope":"SYSTEM","event_type":"SYSTEM_INIT","payload":{"message":"Audit log initialized"},"ts":"' || NOW()::TEXT || '"}';
    current_hash := encode(digest(event_data || COALESCE(prev_hash_val, ''), 'sha256'), 'hex');
    
    INSERT INTO audit_events (actor_user_id, scope, event_type, payload_json, ts, hash, prev_hash)
    VALUES (NULL, 'SYSTEM'::audit_scope, 'SYSTEM_INIT', '{"message":"Audit log initialized"}'::jsonb, NOW(), current_hash, prev_hash_val);
    
    prev_hash_val := current_hash;
    
    -- Event 2: Database migration
    event_data := '{"actor_user_id":null,"scope":"SYSTEM","event_type":"DB_MIGRATION","payload":{"migration":"audit_events_table"},"ts":"' || NOW()::TEXT || '"}';
    current_hash := encode(digest(event_data || prev_hash_val, 'sha256'), 'hex');
    
    INSERT INTO audit_events (actor_user_id, scope, event_type, payload_json, ts, hash, prev_hash)
    VALUES (NULL, 'SYSTEM'::audit_scope, 'DB_MIGRATION', '{"migration":"audit_events_table"}'::jsonb, NOW(), current_hash, prev_hash_val);
    
    RAISE NOTICE 'Created 2 test events in audit_events';
END $$;

-- Проверка целостности цепочки
SELECT * FROM verify_audit_chain_integrity();

-- Показать статистику
SELECT * FROM get_audit_statistics();

-- Показать последние события
SELECT id, scope, event_type, ts, substring(hash, 1, 16) as hash_preview
FROM audit_events
ORDER BY id DESC
LIMIT 10;
