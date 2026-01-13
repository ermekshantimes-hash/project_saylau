-- База данных для системы выборов РК

-- Таблица выборов
CREATE TABLE elections (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,              -- "Президентские выборы 202X"
    election_date DATE NOT NULL,
    election_type VARCHAR(50) NOT NULL, -- 'presidential', 'majilis', 'maslikhat_obl', 'maslikhat_city'
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Иерархия регионов
-- type:
-- 'country' -> 'region' (область/город респ.значения) -> 'district' (район/город)
-- -> 'local' (сельский округ / городской квартал) -> 'precinct' (участок)
CREATE TABLE regions (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT,                                -- код по ЦИК/статистике, если есть
    type VARCHAR(20) NOT NULL,                -- 'country', 'region', 'district', 'local', 'precinct'
    parent_id INT REFERENCES regions(id) ON DELETE CASCADE
);

-- Избирательные участки
CREATE TABLE precincts (
    id SERIAL PRIMARY KEY,
    region_id INT NOT NULL REFERENCES regions(id) ON DELETE CASCADE,
    precinct_number INT NOT NULL,           -- № участка
    address TEXT,
    voters_registered INT                   -- число зарегистрированных избирателей
);

-- Кандидаты / партии (универсальная сущность "subj" – кто получает голоса)
CREATE TABLE election_subjects (
    id SERIAL PRIMARY KEY,
    election_id INT NOT NULL REFERENCES elections(id) ON DELETE CASCADE,
    name TEXT NOT NULL,                     -- ФИО кандидата или название партии
    subject_type VARCHAR(20) NOT NULL,      -- 'candidate' | 'party'
    ballot_number INT                       -- номер в бюллетене
);

-- Фото протоколов
CREATE TABLE protocol_photos (
    id SERIAL PRIMARY KEY,
    election_id INT NOT NULL REFERENCES elections(id) ON DELETE CASCADE,
    precinct_id INT NOT NULL REFERENCES precincts(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,                 -- путь к файлу (S3/локально)
    uploaded_at TIMESTAMP NOT NULL DEFAULT NOW(),
    ocr_raw_text TEXT,                       -- необработанный текст OCR
    parsed BOOLEAN NOT NULL DEFAULT FALSE    -- разобран ли текст в цифры
);

-- Цифровые результаты по участкам
CREATE TABLE precinct_results (
    id SERIAL PRIMARY KEY,
    election_id INT NOT NULL REFERENCES elections(id) ON DELETE CASCADE,
    precinct_id INT NOT NULL REFERENCES precincts(id) ON DELETE CASCADE,
    subject_id INT NOT NULL REFERENCES election_subjects(id) ON DELETE CASCADE,
    votes INT NOT NULL,
    UNIQUE (election_id, precinct_id, subject_id)
);

-- Индексы для производительности
CREATE INDEX idx_regions_parent ON regions(parent_id);
CREATE INDEX idx_regions_type ON regions(type);
CREATE INDEX idx_precincts_region ON precincts(region_id);
CREATE INDEX idx_precinct_results_election ON precinct_results(election_id);
CREATE INDEX idx_precinct_results_precinct ON precinct_results(precinct_id);
CREATE INDEX idx_protocol_photos_election ON protocol_photos(election_id);
CREATE INDEX idx_protocol_photos_precinct ON protocol_photos(precinct_id);
