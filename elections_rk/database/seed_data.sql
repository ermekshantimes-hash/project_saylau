-- Тестовые данные для системы выборов РК

-- Создание выборов
INSERT INTO elections (name, election_date, election_type) VALUES
('Президентские выборы 2024', '2024-11-20', 'presidential'),
('Выборы в Мажилис 2024', '2024-03-19', 'majilis');

-- Создание иерархии регионов
-- 1. РК (страна)
INSERT INTO regions (name, code, type, parent_id) VALUES
('Республика Казахстан', 'KZ', 'country', NULL);

-- 2. Области и города республиканского значения (17 областей + 3 города)
INSERT INTO regions (name, code, type, parent_id) VALUES
('Алматы', 'ALA', 'region', 1),
('Астана', 'AST', 'region', 1),
('Шымкент', 'SHY', 'region', 1),
('Акмолинская область', 'AKM', 'region', 1),
('Актюбинская область', 'AKT', 'region', 1),
('Алматинская область', 'ALM', 'region', 1),
('Атырауская область', 'ATY', 'region', 1),
('Восточно-Казахстанская область', 'VKO', 'region', 1),
('Жамбылская область', 'ZHA', 'region', 1),
('Западно-Казахстанская область', 'ZKO', 'region', 1),
('Карагандинская область', 'KAR', 'region', 1),
('Костанайская область', 'KOS', 'region', 1),
('Кызылординская область', 'KYZ', 'region', 1),
('Мангистауская область', 'MAN', 'region', 1),
('Павлодарская область', 'PAV', 'region', 1),
('Северо-Казахстанская область', 'SKO', 'region', 1),
('Туркестанская область', 'TUR', 'region', 1),
('Улытауская область', 'ULY', 'region', 1),
('Абайская область', 'ABA', 'region', 1),
('Жетысуская область', 'ZHE', 'region', 1);

-- 3. Районы города Алматы (примеры)
INSERT INTO regions (name, code, type, parent_id) VALUES
('Алмалинский район', 'ALA-ALM', 'district', 2),
('Бостандыкский район', 'ALA-BOS', 'district', 2),
('Ауэзовский район', 'ALA-AUE', 'district', 2),
('Медеуский район', 'ALA-MED', 'district', 2);

-- 4. Микрорайоны/кварталы (примеры для Алмалинского района)
INSERT INTO regions (name, code, type, parent_id) VALUES
('Микрорайон Самал-1', 'ALA-ALM-SAM1', 'local', 22),
('Микрорайон Самал-2', 'ALA-ALM-SAM2', 'local', 22),
('Центральный квартал', 'ALA-ALM-CEN', 'local', 22);

-- 5. Участки (примеры)
INSERT INTO regions (name, code, type, parent_id) VALUES
('УИК №1', 'ALA-ALM-SAM1-001', 'precinct', 26),
('УИК №2', 'ALA-ALM-SAM1-002', 'precinct', 26),
('УИК №3', 'ALA-ALM-SAM2-001', 'precinct', 27),
('УИК №4', 'ALA-ALM-CEN-001', 'precinct', 28);

-- Создание записей участков
INSERT INTO precincts (region_id, precinct_number, address, voters_registered) VALUES
(29, 1, 'ул. Достык 123, Алматы', 1500),
(30, 2, 'ул. Достык 456, Алматы', 1800),
(31, 3, 'ул. Абая 789, Алматы', 2000),
(32, 4, 'пр. Назарбаева 111, Алматы', 1600);

-- Кандидаты на президентские выборы (примеры)
INSERT INTO election_subjects (election_id, name, subject_type, ballot_number) VALUES
(1, 'Касым-Жомарт Токаев', 'candidate', 1),
(1, 'Жигули Дайрабаев', 'candidate', 2),
(1, 'Карелбек Кокешев', 'candidate', 3),
(1, 'Мейрам Кажыкен', 'candidate', 4),
(1, 'Нурлан Аубакиров', 'candidate', 5),
(1, 'Салтанат Турсынбекова', 'candidate', 6);

-- Партии для выборов в Мажилис (примеры)
INSERT INTO election_subjects (election_id, name, subject_type, ballot_number) VALUES
(2, 'Amanat', 'party', 1),
(2, 'Ак жол', 'party', 2),
(2, 'Народная партия Казахстана', 'party', 3),
(2, 'Auyl', 'party', 4),
(2, 'Республика', 'party', 5);

-- Тестовые результаты по участкам (президентские выборы)
-- Участок №1
INSERT INTO precinct_results (election_id, precinct_id, subject_id, votes) VALUES
(1, 1, 1, 890),
(1, 1, 2, 120),
(1, 1, 3, 95),
(1, 1, 4, 110),
(1, 1, 5, 85),
(1, 1, 6, 100);

-- Участок №2
INSERT INTO precinct_results (election_id, precinct_id, subject_id, votes) VALUES
(1, 2, 1, 1050),
(1, 2, 2, 150),
(1, 2, 3, 140),
(1, 2, 4, 130),
(1, 2, 5, 120),
(1, 2, 6, 110);

-- Участок №3
INSERT INTO precinct_results (election_id, precinct_id, subject_id, votes) VALUES
(1, 3, 1, 1200),
(1, 3, 2, 180),
(1, 3, 3, 160),
(1, 3, 4, 150),
(1, 3, 5, 140),
(1, 3, 6, 120);

-- Участок №4
INSERT INTO precinct_results (election_id, precinct_id, subject_id, votes) VALUES
(1, 4, 1, 950),
(1, 4, 2, 140),
(1, 4, 3, 125),
(1, 4, 4, 115),
(1, 4, 5, 105),
(1, 4, 6, 95);
