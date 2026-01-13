-- Добавление тестовых результатов голосования
-- Для демонстрации работы системы

-- 1. Создать результаты для первых 100 УИК
DO $$
DECLARE
    precinct_rec RECORD;
    candidate_rec RECORD;
    total_voters INTEGER;
    votes_cast INTEGER;
    remaining_votes INTEGER;
    candidate_votes INTEGER;
BEGIN
    -- Для каждого УИК (первые 100)
    FOR precinct_rec IN (SELECT id FROM precincts ORDER BY id LIMIT 100) LOOP
        
        -- Случайное количество избирателей (от 500 до 2000)
        total_voters := 500 + floor(random() * 1500)::INTEGER;
        
        -- Явка от 40% до 85%
        votes_cast := floor(total_voters * (0.4 + random() * 0.45))::INTEGER;
        remaining_votes := votes_cast;
        
        -- Распределить голоса между кандидатами
        FOR candidate_rec IN (
            SELECT id FROM candidates WHERE election_id = 1 ORDER BY id
        ) LOOP
            -- Последнему кандидату отдать остаток
            IF candidate_rec.id = (SELECT MAX(id) FROM candidates WHERE election_id = 1) THEN
                candidate_votes := remaining_votes;
            ELSE
                -- Случайная доля от оставшихся голосов (10-40%)
                candidate_votes := floor(remaining_votes * (0.1 + random() * 0.3))::INTEGER;
                remaining_votes := remaining_votes - candidate_votes;
            END IF;
            
            -- Вставить результат
            INSERT INTO precinct_tallies (
                precinct_id,
                candidate_id,
                votes,
                basis,
                status,
                version,
                created_at
            ) VALUES (
                precinct_rec.id,
                candidate_rec.id,
                candidate_votes,
                'PROTOCOL',
                'VERIFIED',
                1,
                NOW() - (random() * INTERVAL '7 days')
            );
        END LOOP;
        
    END LOOP;
    
    RAISE NOTICE 'Создано результатов для 100 УИК';
END $$;

-- 2. Создать агрегированные результаты по регионам
INSERT INTO region_aggregates (
    region_id,
    candidate_id,
    total_votes,
    precincts_counted,
    last_updated
)
SELECT 
    p.region_id,
    pt.candidate_id,
    SUM(pt.votes) as total_votes,
    COUNT(DISTINCT p.id) as precincts_counted,
    NOW()
FROM precinct_tallies pt
JOIN precincts p ON pt.precinct_id = p.id
WHERE pt.status = 'VERIFIED'
GROUP BY p.region_id, pt.candidate_id
ON CONFLICT (region_id, candidate_id) 
DO UPDATE SET
    total_votes = EXCLUDED.total_votes,
    precincts_counted = EXCLUDED.precincts_counted,
    last_updated = EXCLUDED.last_updated;

-- 3. Создать общереспубликанские результаты
INSERT INTO country_aggregates (
    candidate_id,
    total_votes,
    precincts_counted,
    regions_counted,
    last_updated
)
SELECT 
    pt.candidate_id,
    SUM(pt.votes) as total_votes,
    COUNT(DISTINCT pt.precinct_id) as precincts_counted,
    COUNT(DISTINCT p.region_id) as regions_counted,
    NOW()
FROM precinct_tallies pt
JOIN precincts p ON pt.precinct_id = p.id
WHERE pt.status = 'VERIFIED'
GROUP BY pt.candidate_id
ON CONFLICT (candidate_id)
DO UPDATE SET
    total_votes = EXCLUDED.total_votes,
    precincts_counted = EXCLUDED.precincts_counted,
    regions_counted = EXCLUDED.regions_counted,
    last_updated = EXCLUDED.last_updated;

-- Вывод статистики
SELECT 
    'Результаты добавлены!' as status,
    COUNT(*) as total_tallies,
    COUNT(DISTINCT precinct_id) as precincts_with_results,
    SUM(votes) as total_votes_cast
FROM precinct_tallies
WHERE status = 'VERIFIED';
