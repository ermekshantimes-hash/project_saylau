-- Расширение базы до 12,000 УИК с полной иерархией
-- Регионы → Районы → Города → Округа → УИК

SET client_encoding = 'UTF8';

-- ==================== ОЧИСТКА СТАРЫХ ДАННЫХ ====================

-- Сохраним elections и organizations
TRUNCATE TABLE precinct_results CASCADE;
TRUNCATE TABLE protocol_photos CASCADE;
TRUNCATE TABLE precincts CASCADE;
TRUNCATE TABLE regions CASCADE;

-- ==================== РЕГИОНЫ (17 областей + 3 города) ====================

INSERT INTO regions (id, name, code, type, parent_id) VALUES
-- Города республиканского значения
(1, 'Астана', '75', 'CITY', NULL),
(2, 'Алматы', '19', 'CITY', NULL),
(3, 'Шымкент', '79', 'CITY', NULL),

-- Области
(10, 'Акмолинская область', '11', 'REGION', NULL),
(11, 'Актюбинская область', '15', 'REGION', NULL),
(12, 'Алматинская область', '19', 'REGION', NULL),
(13, 'Атырауская область', '23', 'REGION', NULL),
(14, 'Восточно-Казахстанская область', '63', 'REGION', NULL),
(15, 'Жамбылская область', '31', 'REGION', NULL),
(16, 'Западно-Казахстанская область', '27', 'REGION', NULL),
(17, 'Карагандинская область', '35', 'REGION', NULL),
(18, 'Костанайская область', '39', 'REGION', NULL),
(19, 'Кызылординская область', '43', 'REGION', NULL),
(20, 'Мангистауская область', '47', 'REGION', NULL),
(21, 'Павлодарская область', '55', 'REGION', NULL),
(22, 'Северо-Казахстанская область', '59', 'REGION', NULL),
(23, 'Туркестанская область', '61', 'REGION', NULL),
(24, 'Улытауская область', '62', 'REGION', NULL),
(25, 'Абайская область', '10', 'REGION', NULL),
(26, 'Жетысуская область', '33', 'REGION', NULL);

-- Сброс последовательности
SELECT setval('regions_id_seq', 100);

-- ==================== РАЙОНЫ (примеры по регионам) ====================

-- Астана - районы
INSERT INTO regions (name, code, type, parent_id) VALUES
('Алматинский район', '7501', 'DISTRICT', 1),
('Байконурский район', '7502', 'DISTRICT', 1),
('Есильский район', '7503', 'DISTRICT', 1),
('Сарыаркинский район', '7504', 'DISTRICT', 1);

-- Алматы - районы
INSERT INTO regions (name, code, type, parent_id) VALUES
('Алатауский район', '1901', 'DISTRICT', 2),
('Алмалинский район', '1902', 'DISTRICT', 2),
('Ауэзовский район', '1903', 'DISTRICT', 2),
('Бостандыкский район', '1904', 'DISTRICT', 2),
('Жетысуский район', '1905', 'DISTRICT', 2),
('Медеуский район', '1906', 'DISTRICT', 2),
('Наурызбайский район', '1907', 'DISTRICT', 2),
('Турксибский район', '1908', 'DISTRICT', 2);

-- Шымкент - районы
INSERT INTO regions (name, code, type, parent_id) VALUES
('Абайский район', '7901', 'DISTRICT', 3),
('Аль-Фарабийский район', '7902', 'DISTRICT', 3),
('Енбекшинский район', '7903', 'DISTRICT', 3),
('Каратауский район', '7904', 'DISTRICT', 3);

-- Акмолинская область - 5 крупнейших районов
INSERT INTO regions (name, code, type, parent_id) VALUES
('Кокшетау', '1101', 'DISTRICT', 10),
('Степногорск', '1102', 'DISTRICT', 10),
('Аккольский район', '1103', 'DISTRICT', 10),
('Аршалынский район', '1104', 'DISTRICT', 10),
('Атбасарский район', '1105', 'DISTRICT', 10);

-- Актюбинская область
INSERT INTO regions (name, code, type, parent_id) VALUES
('Актобе', '1501', 'DISTRICT', 11),
('Алгинский район', '1502', 'DISTRICT', 11),
('Айтекебийский район', '1503', 'DISTRICT', 11),
('Байганинский район', '1504', 'DISTRICT', 11);

-- Алматинская область
INSERT INTO regions (name, code, type, parent_id) VALUES
('Талдыкорган', '1901', 'DISTRICT', 12),
('Конаев', '1902', 'DISTRICT', 12),
('Алакольский район', '1903', 'DISTRICT', 12),
('Енбекшиказахский район', '1904', 'DISTRICT', 12),
('Карасайский район', '1905', 'DISTRICT', 12);

-- ВКО
INSERT INTO regions (name, code, type, parent_id) VALUES
('Усть-Каменогорск', '6301', 'DISTRICT', 14),
('Семей', '6302', 'DISTRICT', 14),
('Риддер', '6303', 'DISTRICT', 14),
('Глубоковский район', '6304', 'DISTRICT', 14);

-- Карагандинская область
INSERT INTO regions (name, code, type, parent_id) VALUES
('Караганда', '3501', 'DISTRICT', 17),
('Темиртау', '3502', 'DISTRICT', 17),
('Сатпаев', '3503', 'DISTRICT', 17),
('Балхашский район', '3504', 'DISTRICT', 17),
('Бухар-Жырауский район', '3505', 'DISTRICT', 17);

-- Остальные области (упрощённо)
INSERT INTO regions (name, code, type, parent_id) 
SELECT name || ' - центр', code || '01', 'DISTRICT', id 
FROM regions 
WHERE id IN (13, 15, 16, 18, 19, 20, 21, 22, 23, 24, 25, 26) AND type = 'REGION';

-- ==================== ГЕНЕРАЦИЯ 12,000 УИК ====================

-- Функция для генерации УИК
DO $$
DECLARE
    district_rec RECORD;
    precinct_num INTEGER;
    total_count INTEGER := 0;
    base_num INTEGER;
    district_precincts INTEGER;
BEGIN
    -- Для каждого района генерируем УИК
    FOR district_rec IN 
        SELECT id, code, name, parent_id 
        FROM regions 
        WHERE type = 'DISTRICT' 
        ORDER BY parent_id, id
    LOOP
        -- Базовый номер УИК = код района * 100
        base_num := CAST(district_rec.code AS INTEGER);
        
        -- Количество УИК в районе (варьируется от 50 до 400)
        district_precincts := CASE 
            -- Столичные районы - много УИК
            WHEN district_rec.parent_id IN (1, 2, 3) THEN 
                FLOOR(150 + random() * 250)::INTEGER
            -- Областные центры
            WHEN district_rec.name LIKE '%центр%' THEN
                FLOOR(100 + random() * 150)::INTEGER
            -- Крупные города
            WHEN district_rec.name IN ('Караганда', 'Темиртау', 'Усть-Каменогорск', 'Семей', 'Актобе', 'Талдыкорган') THEN
                FLOOR(150 + random() * 200)::INTEGER
            -- Остальные
            ELSE 
                FLOOR(50 + random() * 100)::INTEGER
        END;
        
        -- Ограничиваем общее количество
        IF total_count + district_precincts > 12000 THEN
            district_precincts := 12000 - total_count;
        END IF;
        
        -- Генерируем УИК для района
        FOR precinct_num IN 1..district_precincts LOOP
            INSERT INTO precincts (region_id, precinct_number, address, voters_registered)
            VALUES (
                district_rec.id,
                base_num + precinct_num,
                district_rec.name || ', УИК №' || (base_num + precinct_num),
                FLOOR(500 + random() * 1500)::INTEGER  -- От 500 до 2000 избирателей
            );
            
            total_count := total_count + 1;
            
            IF total_count >= 12000 THEN
                EXIT;
            END IF;
        END LOOP;
        
        IF total_count >= 12000 THEN
            EXIT;
        END IF;
    END LOOP;
    
    RAISE NOTICE 'Создано УИК: %', total_count;
END $$;

-- ==================== МИГРАЦИЯ КАНДИДАТОВ ====================

-- Перенос из election_subjects в candidates (если не пусто)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM election_subjects LIMIT 1) THEN
        INSERT INTO candidates (org_id, name, is_active)
        SELECT 
            COALESCE((SELECT id FROM organizations WHERE short_name LIKE '%' || SPLIT_PART(es.name, ' ', 1) || '%' LIMIT 1), 1),
            es.name,
            true
        FROM election_subjects es
        WHERE NOT EXISTS (SELECT 1 FROM candidates WHERE name = es.name);
        
        RAISE NOTICE 'Кандидаты мигрированы из election_subjects';
    END IF;
END $$;

-- ==================== СТАТИСТИКА ====================

SELECT 
    'Регионов' as entity, COUNT(*) as count 
FROM regions WHERE type = 'REGION' AND parent_id IS NULL
UNION ALL
SELECT 'Городов РЗ', COUNT(*) FROM regions WHERE type = 'CITY'
UNION ALL
SELECT 'Районов', COUNT(*) FROM regions WHERE type = 'DISTRICT'
UNION ALL
SELECT 'УИК', COUNT(*) FROM precincts
UNION ALL
SELECT 'Кандидатов', COUNT(*) FROM candidates;

-- Проверка иерархии
SELECT 
    r1.name as region,
    COUNT(DISTINCT r2.id) as districts,
    COUNT(p.id) as precincts,
    SUM(p.voters_registered) as total_voters
FROM regions r1
LEFT JOIN regions r2 ON r2.parent_id = r1.id AND r2.type = 'DISTRICT'
LEFT JOIN precincts p ON p.region_id = r2.id
WHERE r1.parent_id IS NULL
GROUP BY r1.id, r1.name
ORDER BY precincts DESC
LIMIT 10;

COMMIT;
