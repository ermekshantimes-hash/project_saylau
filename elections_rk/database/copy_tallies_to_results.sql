-- Быстрое копирование данных из precinct_tallies в precinct_results

-- 1. Очистить precinct_results
TRUNCATE TABLE precinct_results CASCADE;

-- 2. Создать election_subjects для кандидатов (если нет)
INSERT INTO election_subjects (election_id, name, subject_type, ballot_number, created_at)
SELECT DISTINCT 
    1 as election_id,
    c.name,
    'candidate' as subject_type,
    c.id as ballot_number,
    NOW() as created_at
FROM candidates c
WHERE NOT EXISTS (
    SELECT 1 FROM election_subjects es 
    WHERE es.election_id = 1 AND es.name = c.name
);

-- 3. Копировать данные
INSERT INTO precinct_results (election_id, precinct_id, subject_id, votes)
SELECT 
    1 as election_id,
    pt.precinct_id,
    es.id as subject_id,
    pt.votes
FROM precinct_tallies pt
JOIN candidates c ON pt.candidate_id = c.id
JOIN election_subjects es ON es.name = c.name AND es.election_id = 1
WHERE pt.status = 'VERIFIED';

-- 4. Проверка
SELECT 
    'Всего записей' as info,
    COUNT(*) as count,
    SUM(votes) as total_votes
FROM precinct_results
WHERE election_id = 1;
