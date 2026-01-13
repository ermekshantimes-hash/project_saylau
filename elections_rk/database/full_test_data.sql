-- Полная тестовая база данных для системы мониторинга выборов РК
-- UTF-8 encoding
-- Включает: регионы, участки, кандидатов, результаты по всем областям

SET client_encoding = 'UTF8';

-- Очистка существующих данных
TRUNCATE TABLE protocol_photos CASCADE;
TRUNCATE TABLE precinct_results CASCADE;
TRUNCATE TABLE election_subjects CASCADE;
TRUNCATE TABLE precincts CASCADE;
TRUNCATE TABLE regions CASCADE;
TRUNCATE TABLE elections CASCADE;

-- ==========================================
-- ВЫБОРЫ
-- ==========================================

INSERT INTO elections (id, name, election_date, election_type) VALUES
(1, 'Президентские выборы 2024', '2024-11-20', 'presidential'),
(2, 'Выборы в Мажилис 2024', '2024-11-20', 'parliamentary');

-- ==========================================
-- РЕГИОНЫ (Иерархическая структура)
-- ==========================================

-- Уровень 1: Области и города республиканского значения
INSERT INTO regions (id, code, name, type, parent_id) VALUES
-- Города республиканского значения
(1, 'AST', 'Астана', 'region', NULL),
(2, 'ALA', 'Алматы', 'region', NULL),
(3, 'SHY', 'Шымкент', 'region', NULL),

-- Области
(4, 'AKM', 'Акмолинская область', 'region', NULL),
(5, 'AKT', 'Актюбинская область', 'region', NULL),
(6, 'ALM', 'Алматинская область', 'region', NULL),
(7, 'ATY', 'Атырауская область', 'region', NULL),
(8, 'VKO', 'Восточно-Казахстанская область', 'region', NULL),
(9, 'ZHA', 'Жамбылская область', 'region', NULL),
(10, 'ZKO', 'Западно-Казахстанская область', 'region', NULL),
(11, 'KAR', 'Карагандинская область', 'region', NULL),
(12, 'KOS', 'Костанайская область', 'region', NULL),
(13, 'KYZ', 'Кызылординская область', 'region', NULL),
(14, 'MAN', 'Мангистауская область', 'region', NULL),
(15, 'PAV', 'Павлодарская область', 'region', NULL),
(16, 'SKO', 'Северо-Казахстанская область', 'region', NULL),
(17, 'TUR', 'Туркестанская область', 'region', NULL);

-- Уровень 2: Районы в Астане
INSERT INTO regions (id, code, name, type, parent_id) VALUES
(100, 'AST-BAY', 'Байконурский район', 'district', 1),
(101, 'AST-SAR', 'Сарыаркинский район', 'district', 1),
(102, 'AST-YES', 'Есильский район', 'district', 1);

-- Уровень 2: Районы в Алматы
INSERT INTO regions (id, code, name, type, parent_id) VALUES
(200, 'ALA-ALM', 'Алмалинский район', 'district', 2),
(201, 'ALA-AUS', 'Ауэзовский район', 'district', 2),
(202, 'ALA-BOS', 'Бостандыкский район', 'district', 2);

-- Уровень 2: Районы в Шымкенте
INSERT INTO regions (id, code, name, type, parent_id) VALUES
(300, 'SHY-ABA', 'Абайский район', 'district', 3),
(301, 'SHY-KAR', 'Каратауский район', 'district', 3);

-- Уровень 3: Микрорайоны (для примера в Алматы)
INSERT INTO regions (id, code, name, type, parent_id) VALUES
(2000, 'ALA-ALM-SAM1', 'Самал-1', 'local', 200),
(2001, 'ALA-ALM-SAM2', 'Самал-2', 'local', 200),
(2002, 'ALA-AUS-AKS', 'Аксай-1', 'local', 201);

-- ==========================================
-- УЧАСТКИ (УИК по всем регионам)
-- ==========================================

-- Астана (60 участков)
INSERT INTO precincts (precinct_number, address, region_id, voters_registered) 
SELECT 
    generate_series,
    'Астана, ул. ' || (ARRAY['Кабанбай батыра', 'Кунаева', 'Туран', 'Кенесары'])[1 + (generate_series % 4)] || ', д. ' || generate_series,
    (ARRAY[100, 101, 102])[1 + (generate_series % 3)],
    1000 + (generate_series * 50)
FROM generate_series(1, 60);

-- Алматы (100 участков)
INSERT INTO precincts (precinct_number, address, region_id, voters_registered) 
SELECT 
    (60 + generate_series),
    'Алматы, ул. ' || (ARRAY['Абая', 'Жибек Жолы', 'Фурманова', 'Розыбакиева', 'Сатпаева'])[1 + (generate_series % 5)] || ', д. ' || generate_series,
    CASE 
        WHEN generate_series <= 40 THEN 200
        WHEN generate_series <= 70 THEN 201
        ELSE 202
    END,
    1200 + (generate_series * 30)
FROM generate_series(1, 100);

-- Шымкент (50 участков)
INSERT INTO precincts (precinct_number, address, region_id, voters_registered) 
SELECT 
    (160 + generate_series),
    'Шымкент, ул. ' || (ARRAY['Байтурсынова', 'Темирлана', 'Казыбек би'])[1 + (generate_series % 3)] || ', д. ' || generate_series,
    (ARRAY[300, 301])[1 + (generate_series % 2)],
    900 + (generate_series * 40)
FROM generate_series(1, 50);

-- Акмолинская область (40 участков)
INSERT INTO precincts (precinct_number, address, region_id, voters_registered) 
SELECT 
    (210 + generate_series),
    'Акмолинская обл., город ' || (ARRAY['Кокшетау', 'Степногорск', 'Щучинск'])[1 + (generate_series % 3)] || ', участок ' || generate_series,
    4,
    800 + (generate_series * 35)
FROM generate_series(1, 40);

-- Алматинская область (60 участков)
INSERT INTO precincts (precinct_number, address, region_id, voters_registered) 
SELECT 
    (250 + generate_series),
    'Алматинская обл., город ' || (ARRAY['Талдыкорган', 'Капшагай', 'Текели', 'Талгар'])[1 + (generate_series % 4)] || ', участок ' || generate_series,
    6,
    850 + (generate_series * 25)
FROM generate_series(1, 60);

-- Карагандинская область (50 участков)
INSERT INTO precincts (precinct_number, address, region_id, voters_registered) 
SELECT 
    (310 + generate_series),
    'Карагандинская обл., город ' || (ARRAY['Караганда', 'Темиртау', 'Жезказган', 'Балхаш'])[1 + (generate_series % 4)] || ', участок ' || generate_series,
    11,
    1000 + (generate_series * 40)
FROM generate_series(1, 50);

-- Остальные области (по 20 участков)
INSERT INTO precincts (precinct_number, address, region_id, voters_registered) 
SELECT 
    (360 + (r.rn - 1) * 20 + generate_series),
    r.region_name || ', участок ' || generate_series,
    r.region_id,
    700 + (generate_series * 30)
FROM generate_series(1, 20),
(VALUES 
    (1, 5, 'Актюбинская обл.'),
    (2, 7, 'Атырауская обл.'),
    (3, 8, 'ВКО'),
    (4, 9, 'Жамбылская обл.'),
    (5, 10, 'ЗКО'),
    (6, 12, 'Костанайская обл.'),
    (7, 13, 'Кызылординская обл.'),
    (8, 14, 'Мангистауская обл.'),
    (9, 15, 'Павлодарская обл.'),
    (10, 16, 'СКО'),
    (11, 17, 'Туркестанская обл.')
) AS r(rn, region_id, region_name);

-- ==========================================
-- КАНДИДАТЫ В ПРЕЗИДЕНТЫ
-- ==========================================

INSERT INTO election_subjects (election_id, subject_type, name, ballot_number) VALUES
(1, 'candidate', 'Касым-Жомарт Токаев', 1),
(1, 'candidate', 'Марат Нурланов', 2),
(1, 'candidate', 'Айгуль Сейтжанова', 3),
(1, 'candidate', 'Бауыржан Калымбетов', 4),
(1, 'candidate', 'Жанар Айтбаева', 5),
(1, 'candidate', 'Против всех', 6);

-- ==========================================
-- ПАРТИИ ДЛЯ МАЖИЛИСА
-- ==========================================

INSERT INTO election_subjects (election_id, subject_type, name, ballot_number) VALUES
(2, 'party', 'Аманат', 1),
(2, 'party', 'Ауыл', 2),
(2, 'party', 'Ак жол', 3),
(2, 'party', 'Адал', 4),
(2, 'party', 'Байтак', 5),
(2, 'party', 'Казахстан халкы партиясы', 6),
(2, 'party', 'Против всех', 7);

-- ==========================================
-- РЕЗУЛЬТАТЫ ПРЕЗИДЕНТСКИХ ВЫБОРОВ
-- ==========================================

DO $$
DECLARE
    v_precinct_id INT;
    v_registered INT;
    v_turnout DECIMAL;
    v_total_votes INT;
    v_tokayev_pct DECIMAL := 0.62;
    v_nurlan_pct DECIMAL := 0.18;
    v_aigul_pct DECIMAL := 0.10;
    v_bauyr_pct DECIMAL := 0.06;
    v_zhanar_pct DECIMAL := 0.03;
    v_against_pct DECIMAL := 0.01;
    v_subject_ids INT[];
BEGIN
    -- Получить актуальные ID кандидатов
    SELECT ARRAY_AGG(id ORDER BY ballot_number) INTO v_subject_ids
    FROM election_subjects WHERE election_id = 1;
    
    FOR v_precinct_id, v_registered IN 
        SELECT id, voters_registered FROM precincts
    LOOP
        v_turnout := 0.65 + (random() * 0.20);
        v_total_votes := FLOOR(v_registered * v_turnout);
        
        INSERT INTO precinct_results (election_id, precinct_id, subject_id, votes)
        VALUES
            (1, v_precinct_id, v_subject_ids[1], FLOOR(v_total_votes * (v_tokayev_pct + (random() - 0.5) * 0.10))),
            (1, v_precinct_id, v_subject_ids[2], FLOOR(v_total_votes * (v_nurlan_pct + (random() - 0.5) * 0.08))),
            (1, v_precinct_id, v_subject_ids[3], FLOOR(v_total_votes * (v_aigul_pct + (random() - 0.5) * 0.06))),
            (1, v_precinct_id, v_subject_ids[4], FLOOR(v_total_votes * (v_bauyr_pct + (random() - 0.5) * 0.04))),
            (1, v_precinct_id, v_subject_ids[5], FLOOR(v_total_votes * (v_zhanar_pct + (random() - 0.5) * 0.03))),
            (1, v_precinct_id, v_subject_ids[6], FLOOR(v_total_votes * (v_against_pct + (random() - 0.5) * 0.02)));
    END LOOP;
END $$;

-- ==========================================
-- РЕЗУЛЬТАТЫ ВЫБОРОВ В МАЖИЛИС
-- ==========================================

DO $$
DECLARE
    v_precinct_id INT;
    v_registered INT;
    v_turnout DECIMAL;
    v_total_votes INT;
    v_party_ids INT[];
BEGIN
    -- Получить актуальные ID партий
    SELECT ARRAY_AGG(id ORDER BY ballot_number) INTO v_party_ids
    FROM election_subjects WHERE election_id = 2;
    
    FOR v_precinct_id, v_registered IN 
        SELECT id, voters_registered FROM precincts
    LOOP
        v_turnout := 0.60 + (random() * 0.20);
        v_total_votes := FLOOR(v_registered * v_turnout);
        
        INSERT INTO precinct_results (election_id, precinct_id, subject_id, votes)
        VALUES
            (2, v_precinct_id, v_party_ids[1], FLOOR(v_total_votes * (0.35 + (random() - 0.5) * 0.10))),
            (2, v_precinct_id, v_party_ids[2], FLOOR(v_total_votes * (0.20 + (random() - 0.5) * 0.08))),
            (2, v_precinct_id, v_party_ids[3], FLOOR(v_total_votes * (0.15 + (random() - 0.5) * 0.06))),
            (2, v_precinct_id, v_party_ids[4], FLOOR(v_total_votes * (0.12 + (random() - 0.5) * 0.05))),
            (2, v_precinct_id, v_party_ids[5], FLOOR(v_total_votes * (0.08 + (random() - 0.5) * 0.04))),
            (2, v_precinct_id, v_party_ids[6], FLOOR(v_total_votes * (0.07 + (random() - 0.5) * 0.03))),
            (2, v_precinct_id, v_party_ids[7], FLOOR(v_total_votes * (0.03 + (random() - 0.5) * 0.02)));
    END LOOP;
END $$;

-- ==========================================
-- ПРИМЕРЫ ПРОТОКОЛОВ
-- ==========================================

INSERT INTO protocol_photos (election_id, precinct_id, image_url, uploaded_at) 
SELECT 
    1,
    id,
    '/uploads/protocols/protocol_' || id || '.jpg',
    NOW() - (random() * INTERVAL '5 days')
FROM precincts 
WHERE id <= 20;

-- ==========================================
-- СТАТИСТИКА
-- ==========================================

SELECT 'СТАТИСТИКА ЗАГРУЖЕННЫХ ДАННЫХ' as title;

SELECT 
    'Всего регионов' as metric, 
    COUNT(*)::TEXT as value 
FROM regions
UNION ALL
SELECT 
    'Всего участков', 
    COUNT(*)::TEXT 
FROM precincts
UNION ALL
SELECT 
    'Всего кандидатов/партий', 
    COUNT(*)::TEXT 
FROM election_subjects
UNION ALL
SELECT 
    'Всего результатов', 
    COUNT(*)::TEXT 
FROM precinct_results
UNION ALL
SELECT 
    'Всего протоколов', 
    COUNT(*)::TEXT 
FROM protocol_photos;

SELECT 'РЕЗУЛЬТАТЫ ПРЕЗИДЕНТСКИХ ВЫБОРОВ' as title;

SELECT 
    es.name AS candidate,
    SUM(pr.votes) AS total_votes,
    ROUND(SUM(pr.votes) * 100.0 / (SELECT SUM(votes) FROM precinct_results WHERE election_id = 1), 2) AS percent
FROM precinct_results pr
JOIN election_subjects es ON pr.subject_id = es.id
WHERE pr.election_id = 1
GROUP BY es.id, es.name
ORDER BY SUM(pr.votes) DESC;

SELECT 'РЕЗУЛЬТАТЫ ВЫБОРОВ В МАЖИЛИС' as title;

SELECT 
    es.name AS party,
    SUM(pr.votes) AS total_votes,
    ROUND(SUM(pr.votes) * 100.0 / (SELECT SUM(votes) FROM precinct_results WHERE election_id = 2), 2) AS percent
FROM precinct_results pr
JOIN election_subjects es ON pr.subject_id = es.id
WHERE pr.election_id = 2
GROUP BY es.id, es.name
ORDER BY SUM(pr.votes) DESC;

COMMIT;
