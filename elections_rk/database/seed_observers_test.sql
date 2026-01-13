-- Генерация тестовых наблюдателей, заявок и протоколов
-- 1000 наблюдателей, 5000 заявок, 500 протоколов

SET client_encoding = 'UTF8';

-- ==================== ТЕСТОВЫЕ НАБЛЮДАТЕЛИ ====================

-- Создание 1000 пользователей-наблюдателей
DO $$
DECLARE
    i INTEGER;
    phone_num TEXT;
    email_addr TEXT;
BEGIN
    FOR i IN 1..1000 LOOP
        phone_num := '+7' || LPAD((7000000000 + i)::TEXT, 10, '0');
        email_addr := 'observer' || i || '@test.kz';
        
        -- Создаём пользователя
        INSERT INTO users (phone, email, password_hash, role, status, created_at)
        VALUES (
            phone_num,
            email_addr,
            '$argon2id$v=19$m=65536,t=2,p=4$test$testhash' || i,  -- Тестовый хеш
            'OBSERVER',
            'ACTIVE',
            CURRENT_TIMESTAMP - (random() * interval '90 days')
        );
        
        -- Создаём профиль наблюдателя
        INSERT INTO observer_profiles (
            user_id, 
            legal_type, 
            org_id,
            id_doc_type,
            id_doc_number,
            id_scan_hash,
            selfie_hash,
            training_passed,
            training_score,
            rating,
            risk_score,
            status,
            created_at
        )
        VALUES (
            (SELECT id FROM users WHERE phone = phone_num),
            (CASE 
                WHEN random() < 0.5 THEN 'ORG'
                WHEN random() < 0.8 THEN 'DELEGATE'
                ELSE 'INDEPENDENT'
            END)::observer_legal_type,
            CASE WHEN random() < 0.7 THEN (SELECT id FROM organizations ORDER BY random() LIMIT 1) ELSE NULL END,
            'ID_CARD',
            LPAD((100000000 + i)::TEXT, 9, '0'),
            md5(random()::TEXT),
            md5(random()::TEXT),
            random() < 0.85,  -- 85% прошли обучение
            CASE WHEN random() < 0.85 THEN FLOOR(70 + random() * 30)::INTEGER ELSE NULL END,
            FLOOR(random() * 5.0 * 10) / 10.0,  -- Рейтинг 0-5
            random() * 0.3,  -- Риск 0-0.3
            (CASE 
                WHEN random() < 0.80 THEN 'VERIFIED'
                WHEN random() < 0.95 THEN 'PENDING'
                ELSE 'REJECTED'
            END)::observer_status,
            CURRENT_TIMESTAMP - (random() * interval '90 days')
        );
    END LOOP;
    
    RAISE NOTICE 'Создано 1000 наблюдателей';
END $$;

-- ==================== ЗАЯВКИ НА УИК ====================

-- Генерация 5000 заявок (в среднем 5 заявок на наблюдателя)
DO $$
DECLARE
    i INTEGER;
    observer_rec RECORD;
    precinct_rec RECORD;
BEGIN
    -- Для каждого верифицированного наблюдателя создаём 3-8 заявок
    FOR observer_rec IN 
        SELECT id FROM observer_profiles WHERE status = 'VERIFIED' LIMIT 800
    LOOP
        FOR i IN 1..(3 + FLOOR(random() * 6)::INTEGER) LOOP
            SELECT id INTO precinct_rec 
            FROM precincts 
            ORDER BY random() 
            LIMIT 1;
            
            INSERT INTO observer_applications (
                observer_id,
                precinct_id,
                source,
                priority,
                shift,
                status,
                created_at
            )
            VALUES (
                observer_rec.id,
                precinct_rec.id,
                (CASE 
                    WHEN random() < 0.5 THEN 'ORG'
                    WHEN random() < 0.8 THEN 'NGO'
                    ELSE 'SELF'
                END)::app_source,
                FLOOR(random() * 10)::INTEGER,
                (CASE 
                    WHEN random() < 0.7 THEN 'FULL'
                    WHEN random() < 0.85 THEN 'MORNING'
                    ELSE 'EVENING'
                END)::shift_type,
                (CASE 
                    WHEN random() < 0.4 THEN 'ASSIGNED'
                    WHEN random() < 0.6 THEN 'REQUESTED'
                    WHEN random() < 0.8 THEN 'RESERVE'
                    ELSE 'CANCELLED'
                END)::app_status,
                CURRENT_TIMESTAMP - (random() * interval '60 days')
            );
        END LOOP;
    END LOOP;
    
    RAISE NOTICE 'Создано заявок: %', (SELECT COUNT(*) FROM observer_applications);
END $$;

-- ==================== ЧЕК-ИНЫ ====================

-- Чек-ины для assigned наблюдателей (50% сделали чек-ин)
INSERT INTO observer_checkins (
    observer_id,
    precinct_id,
    ts_in,
    qrcode_token,
    selfie_hash,
    device_fingerprint,
    geo_lat,
    geo_lon
)
SELECT 
    oa.observer_id,
    oa.precinct_id,
    CURRENT_TIMESTAMP - (random() * interval '30 days'),
    'qr_token_' || md5(random()::TEXT),
    md5(random()::TEXT),
    md5(random()::TEXT),
    43.0 + random() * 8.0,  -- Широта Казахстана ~43-51
    51.0 + random() * 36.0  -- Долгота ~51-87
FROM observer_applications oa
WHERE oa.status = 'ASSIGNED' AND random() < 0.5
LIMIT 2000;

-- ==================== ПРОТОКОЛЫ ====================

-- Генерация 500 протоколов от наблюдателей
DO $$
DECLARE
    i INTEGER;
    precinct_rec RECORD;
    observer_user_id INTEGER;
    protocol_id INTEGER;
    cand_rec RECORD;
BEGIN
    FOR i IN 1..500 LOOP
        -- Случайный УИК
        SELECT id INTO precinct_rec FROM precincts ORDER BY random() LIMIT 1;
        
        -- Случайный наблюдатель (пользователь)
        SELECT user_id INTO observer_user_id 
        FROM observer_profiles 
        WHERE status = 'VERIFIED' 
        ORDER BY random() 
        LIMIT 1;
        
        -- Создаём протокол
        INSERT INTO protocols (
            precinct_id,
            uploader_id,
            file_url,
            file_hash,
            file_size,
            version,
            source,
            status,
            created_at
        )
        VALUES (
            precinct_rec.id,
            observer_user_id,
            '/uploads/protocol_' || i || '.jpg',
            md5(random()::TEXT),
            FLOOR(1000000 + random() * 5000000)::INTEGER,
            1,
            (CASE 
                WHEN random() < 0.8 THEN 'PHOTO'
                ELSE 'SCAN'
            END)::protocol_source,
            (CASE 
                WHEN random() < 0.6 THEN 'VERIFIED'
                WHEN random() < 0.85 THEN 'UNDER_REVIEW'
                ELSE 'DRAFT'
            END)::protocol_status,
            CURRENT_TIMESTAMP - (random() * interval '20 days')
        )
        RETURNING id INTO protocol_id;
        
        -- Добавляем строки протокола (голоса по кандидатам)
        FOR cand_rec IN SELECT id FROM candidates WHERE is_active = true LOOP
            INSERT INTO protocol_items (protocol_id, candidate_id, votes)
            VALUES (
                protocol_id,
                cand_rec.id,
                FLOOR(50 + random() * 500)::INTEGER
            );
        END LOOP;
    END LOOP;
    
    RAISE NOTICE 'Создано протоколов: %', (SELECT COUNT(*) FROM protocols);
END $$;

-- ==================== ИНЦИДЕНТЫ ====================

-- Генерация 200 инцидентов
INSERT INTO incidents (
    precinct_id,
    reporter_id,
    type,
    severity,
    description,
    status,
    sla_deadline,
    created_at
)
SELECT 
    (SELECT id FROM precincts ORDER BY random() LIMIT 1),
    (SELECT user_id FROM observer_profiles WHERE status = 'VERIFIED'::observer_status ORDER BY random() LIMIT 1),
    (CASE 
        WHEN random() < 0.4 THEN 'BLOCK_ENTRY'
        WHEN random() < 0.7 THEN 'DOC_TAKEN'
        WHEN random() < 0.9 THEN 'BALLOT_STUFFING'
        ELSE 'OTHER'
    END)::incident_type,
    (CASE 
        WHEN random() < 0.5 THEN 'MEDIUM'
        WHEN random() < 0.8 THEN 'LOW'
        ELSE 'HIGH'
    END)::incident_severity,
    'Тестовый инцидент №' || generate_series,
    (CASE 
        WHEN random() < 0.4 THEN 'RESOLVED'
        WHEN random() < 0.7 THEN 'IN_PROGRESS'
        ELSE 'OPEN'
    END)::incident_status,
    CURRENT_TIMESTAMP + (random() * interval '48 hours'),
    CURRENT_TIMESTAMP - (random() * interval '15 days')
FROM generate_series(1, 200);

-- ==================== СТАТИСТИКА ====================

SELECT 
    'Пользователей' as entity, COUNT(*) as count FROM users
UNION ALL
SELECT 'Наблюдателей', COUNT(*) FROM observer_profiles
UNION ALL
SELECT 'Заявок', COUNT(*) FROM observer_applications
UNION ALL
SELECT 'Чек-инов', COUNT(*) FROM observer_checkins
UNION ALL
SELECT 'Протоколов', COUNT(*) FROM protocols
UNION ALL
SELECT 'Инцидентов', COUNT(*) FROM incidents;

-- Распределение по статусам
SELECT 
    'Заявки: ' || status::TEXT as category, 
    COUNT(*) as count 
FROM observer_applications 
GROUP BY status
UNION ALL
SELECT 
    'Протоколы: ' || status::TEXT, 
    COUNT(*) 
FROM protocols 
GROUP BY status
UNION ALL
SELECT 
    'Инциденты: ' || status::TEXT, 
    COUNT(*) 
FROM incidents 
GROUP BY status
ORDER BY category;

COMMIT;
