-- Миграция: добавление таблиц для системы наблюдателей (RBAC, KYC, инциденты, аудит)
-- Версия: 2024-01-01

-- ==================== ТИПЫ ====================

CREATE TYPE user_role AS ENUM ('ADMIN', 'COORD', 'OBSERVER', 'MEDIA', 'PUBLIC');
CREATE TYPE org_type AS ENUM ('PARTY', 'OO', 'IP', 'INDEPENDENT');
CREATE TYPE observer_legal_type AS ENUM ('ORG', 'DELEGATE', 'INDEPENDENT');
CREATE TYPE observer_status AS ENUM ('DRAFT', 'PENDING', 'VERIFIED', 'REJECTED', 'BANNED');
CREATE TYPE app_status AS ENUM ('REQUESTED', 'RESERVE', 'ASSIGNED', 'CHECKED_IN', 'COMPLETED', 'CANCELLED');
CREATE TYPE app_source AS ENUM ('ORG', 'SELF', 'NGO');
CREATE TYPE shift_type AS ENUM ('FULL', 'MORNING', 'EVENING');
CREATE TYPE protocol_status AS ENUM ('DRAFT', 'UNDER_REVIEW', 'VERIFIED', 'DISPUTED', 'REJECTED');
CREATE TYPE protocol_source AS ENUM ('PHOTO', 'SCAN', 'CSV', 'API');
CREATE TYPE tally_basis AS ENUM ('PROTOCOL', 'CORRECTION');
CREATE TYPE tally_status AS ENUM ('PRELIM', 'VERIFIED', 'DISPUTED');
CREATE TYPE incident_type AS ENUM ('BLOCK_ENTRY', 'DOC_TAKEN', 'BALLOT_STUFFING', 'OTHER');
CREATE TYPE incident_severity AS ENUM ('LOW', 'MEDIUM', 'HIGH');
CREATE TYPE incident_status AS ENUM ('OPEN', 'IN_PROGRESS', 'RESOLVED');
CREATE TYPE audit_scope AS ENUM ('SYSTEM', 'USER');

-- ==================== ТАБЛИЦЫ ====================

-- 1. Организации
CREATE TABLE organizations (
    id SERIAL PRIMARY KEY,
    type org_type NOT NULL,
    short_name VARCHAR(100) NOT NULL,
    full_name TEXT NOT NULL,
    color_idx INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. Кандидаты
CREATE TABLE candidates (
    id SERIAL PRIMARY KEY,
    org_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 3. Пользователи
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    phone VARCHAR(20) UNIQUE,
    email VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role user_role NOT NULL DEFAULT 'PUBLIC',
    
    -- MFA
    mfa_enabled BOOLEAN NOT NULL DEFAULT false,
    mfa_secret VARCHAR(32),
    
    -- Статус
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    device_fingerprint TEXT,
    last_login_at TIMESTAMP,
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE INDEX idx_user_phone ON users(phone);
CREATE INDEX idx_user_email ON users(email);

-- 4. Профили наблюдателей
CREATE TABLE observer_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    
    -- Тип
    legal_type observer_legal_type NOT NULL,
    org_id INTEGER REFERENCES organizations(id),
    
    -- Документы (хеши)
    id_doc_type VARCHAR(50),
    id_doc_number VARCHAR(50),
    id_scan_hash VARCHAR(64),
    selfie_hash VARCHAR(64),
    
    -- Обучение
    training_passed BOOLEAN NOT NULL DEFAULT false,
    training_score INTEGER,
    training_completed_at TIMESTAMP,
    
    -- Рейтинг
    rating FLOAT DEFAULT 0.0,
    risk_score FLOAT DEFAULT 0.0,
    
    -- Статус
    status observer_status NOT NULL DEFAULT 'DRAFT',
    verified_by INTEGER REFERENCES users(id),
    verified_at TIMESTAMP,
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE INDEX idx_observer_user ON observer_profiles(user_id);
CREATE INDEX idx_observer_status ON observer_profiles(status);

-- 5. Заявки наблюдателей
CREATE TABLE observer_applications (
    id SERIAL PRIMARY KEY,
    observer_id INTEGER NOT NULL REFERENCES observer_profiles(id) ON DELETE CASCADE,
    precinct_id INTEGER NOT NULL REFERENCES precincts(id) ON DELETE CASCADE,
    
    -- Источник и приоритет
    source app_source NOT NULL,
    priority INTEGER DEFAULT 0,
    shift shift_type NOT NULL DEFAULT 'FULL',
    
    -- Статус
    status app_status NOT NULL DEFAULT 'REQUESTED',
    assigned_by INTEGER REFERENCES users(id),
    assigned_at TIMESTAMP,
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE INDEX idx_app_precinct ON observer_applications(precinct_id, status);
CREATE INDEX idx_app_observer ON observer_applications(observer_id, status);

-- 6. Чек-ины
CREATE TABLE observer_checkins (
    id SERIAL PRIMARY KEY,
    observer_id INTEGER NOT NULL REFERENCES observer_profiles(id) ON DELETE CASCADE,
    precinct_id INTEGER NOT NULL REFERENCES precincts(id) ON DELETE CASCADE,
    
    -- Время
    ts_in TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ts_out TIMESTAMP,
    
    -- Верификация
    qrcode_token VARCHAR(255),
    selfie_hash VARCHAR(64),
    device_fingerprint TEXT,
    geo_lat FLOAT,
    geo_lon FLOAT,
    
    verified_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_checkin_precinct ON observer_checkins(precinct_id, ts_in);

-- 7. Протоколы (расширенная версия)
CREATE TABLE protocols (
    id SERIAL PRIMARY KEY,
    precinct_id INTEGER NOT NULL REFERENCES precincts(id) ON DELETE CASCADE,
    uploader_id INTEGER NOT NULL REFERENCES users(id),
    
    -- Файл
    file_url TEXT NOT NULL,
    file_hash VARCHAR(64) NOT NULL,
    file_size INTEGER,
    
    -- Метаданные
    exif_json JSON,
    ocr_json JSON,
    
    -- Версионирование
    version INTEGER NOT NULL DEFAULT 1,
    source protocol_source NOT NULL DEFAULT 'PHOTO',
    
    -- Статус
    status protocol_status NOT NULL DEFAULT 'DRAFT',
    verified_by INTEGER REFERENCES users(id),
    verified_at TIMESTAMP,
    verification_notes TEXT,
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE INDEX idx_protocol_precinct ON protocols(precinct_id, status);
CREATE INDEX idx_protocol_uploader ON protocols(uploader_id);

-- 8. Строки протокола
CREATE TABLE protocol_items (
    id SERIAL PRIMARY KEY,
    protocol_id INTEGER NOT NULL REFERENCES protocols(id) ON DELETE CASCADE,
    candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    votes INTEGER NOT NULL
);

-- 9. Подсчёты по УИК
CREATE TABLE precinct_tallies (
    id SERIAL PRIMARY KEY,
    precinct_id INTEGER NOT NULL REFERENCES precincts(id) ON DELETE CASCADE,
    candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    votes INTEGER NOT NULL,
    
    -- Основание
    basis tally_basis NOT NULL DEFAULT 'PROTOCOL',
    protocol_id INTEGER REFERENCES protocols(id),
    
    -- Статус
    status tally_status NOT NULL DEFAULT 'PRELIM',
    version INTEGER NOT NULL DEFAULT 1,
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tally_precinct ON precinct_tallies(precinct_id, status);
CREATE INDEX idx_tally_candidate ON precinct_tallies(candidate_id);

-- 10. Инциденты
CREATE TABLE incidents (
    id SERIAL PRIMARY KEY,
    precinct_id INTEGER NOT NULL REFERENCES precincts(id) ON DELETE CASCADE,
    reporter_id INTEGER NOT NULL REFERENCES users(id),
    
    -- Тип и серьёзность
    type incident_type NOT NULL,
    severity incident_severity NOT NULL DEFAULT 'MEDIUM',
    
    -- Описание
    description TEXT NOT NULL,
    media_urls JSON,
    
    -- Статус
    status incident_status NOT NULL DEFAULT 'OPEN',
    sla_deadline TIMESTAMP,
    
    -- Модерация
    assigned_to INTEGER REFERENCES users(id),
    resolution_notes TEXT,
    resolved_at TIMESTAMP,
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE INDEX idx_incident_precinct ON incidents(precinct_id, status);
CREATE INDEX idx_incident_severity ON incidents(severity, status);

-- 11. Аудит-лог
CREATE TABLE audit_events (
    id SERIAL PRIMARY KEY,
    actor_user_id INTEGER REFERENCES users(id),
    
    -- Событие
    scope audit_scope NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    payload_json JSON,
    
    -- Хеширование
    ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    hash VARCHAR(64) NOT NULL,
    prev_hash VARCHAR(64)
);

CREATE INDEX idx_audit_ts ON audit_events(ts);
CREATE INDEX idx_audit_actor ON audit_events(actor_user_id);

-- ==================== НАЧАЛЬНЫЕ ДАННЫЕ ====================

-- Создать админа по умолчанию (пароль: admin123, захешировать в приложении!)
INSERT INTO users (phone, email, password_hash, role, status)
VALUES ('+77000000000', 'admin@elections.kz', 'PLACEHOLDER_HASH', 'ADMIN', 'ACTIVE');

-- Создать тестовые организации
INSERT INTO organizations (type, short_name, full_name, color_idx) VALUES
('PARTY', 'Аманат', 'Республиканская политическая партия "Аманат"', 1),
('PARTY', 'Ауыл', 'Народная партия Казахстана "Ауыл"', 2),
('OO', 'Qoǵam', 'ОО "Институт наблюдателей Казахстана"', 10);

COMMIT;
