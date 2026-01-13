-- Р‘Р°Р·Р° РґР°РЅРЅС‹С… РґР»СЏ СЃРёСЃС‚РµРјС‹ РІС‹Р±РѕСЂРѕРІ Р Рљ

-- РўР°Р±Р»РёС†Р° РІС‹Р±РѕСЂРѕРІ
CREATE TABLE elections (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,              -- "РџСЂРµР·РёРґРµРЅС‚СЃРєРёРµ РІС‹Р±РѕСЂС‹ 202X"
    election_date DATE NOT NULL,
    election_type VARCHAR(50) NOT NULL, -- 'presidential', 'majilis', 'maslikhat_obl', 'maslikhat_city'
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- РРµСЂР°СЂС…РёСЏ СЂРµРіРёРѕРЅРѕРІ
-- type:
-- 'country' -> 'region' (РѕР±Р»Р°СЃС‚СЊ/РіРѕСЂРѕРґ СЂРµСЃРї.Р·РЅР°С‡РµРЅРёСЏ) -> 'district' (СЂР°Р№РѕРЅ/РіРѕСЂРѕРґ)
-- -> 'local' (СЃРµР»СЊСЃРєРёР№ РѕРєСЂСѓРі / РіРѕСЂРѕРґСЃРєРѕР№ РєРІР°СЂС‚Р°Р») -> 'precinct' (СѓС‡Р°СЃС‚РѕРє)
CREATE TABLE regions (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT,                                -- РєРѕРґ РїРѕ Р¦РРљ/СЃС‚Р°С‚РёСЃС‚РёРєРµ, РµСЃР»Рё РµСЃС‚СЊ
    type VARCHAR(20) NOT NULL,                -- 'country', 'region', 'district', 'local', 'precinct'
    parent_id INT REFERENCES regions(id) ON DELETE CASCADE
);

-- РР·Р±РёСЂР°С‚РµР»СЊРЅС‹Рµ СѓС‡Р°СЃС‚РєРё
CREATE TABLE precincts (
    id SERIAL PRIMARY KEY,
    region_id INT NOT NULL REFERENCES regions(id) ON DELETE CASCADE,
    precinct_number INT NOT NULL,           -- в„– СѓС‡Р°СЃС‚РєР°
    address TEXT,
    voters_registered INT                   -- С‡РёСЃР»Рѕ Р·Р°СЂРµРіРёСЃС‚СЂРёСЂРѕРІР°РЅРЅС‹С… РёР·Р±РёСЂР°С‚РµР»РµР№
);

-- РљР°РЅРґРёРґР°С‚С‹ / РїР°СЂС‚РёРё (СѓРЅРёРІРµСЂСЃР°Р»СЊРЅР°СЏ СЃСѓС‰РЅРѕСЃС‚СЊ "subj" вЂ“ РєС‚Рѕ РїРѕР»СѓС‡Р°РµС‚ РіРѕР»РѕСЃР°)
CREATE TABLE election_subjects (
    id SERIAL PRIMARY KEY,
    election_id INT NOT NULL REFERENCES elections(id) ON DELETE CASCADE,
    name TEXT NOT NULL,                     -- Р¤РРћ РєР°РЅРґРёРґР°С‚Р° РёР»Рё РЅР°Р·РІР°РЅРёРµ РїР°СЂС‚РёРё
    subject_type VARCHAR(20) NOT NULL,      -- 'candidate' | 'party'
    ballot_number INT                       -- РЅРѕРјРµСЂ РІ Р±СЋР»Р»РµС‚РµРЅРµ
);

-- Р¤РѕС‚Рѕ РїСЂРѕС‚РѕРєРѕР»РѕРІ
CREATE TABLE protocol_photos (
    id SERIAL PRIMARY KEY,
    election_id INT NOT NULL REFERENCES elections(id) ON DELETE CASCADE,
    precinct_id INT NOT NULL REFERENCES precincts(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,                 -- РїСѓС‚СЊ Рє С„Р°Р№Р»Сѓ (S3/Р»РѕРєР°Р»СЊРЅРѕ)
    uploaded_at TIMESTAMP NOT NULL DEFAULT NOW(),
    ocr_raw_text TEXT,                       -- РЅРµРѕР±СЂР°Р±РѕС‚Р°РЅРЅС‹Р№ С‚РµРєСЃС‚ OCR
    parsed BOOLEAN NOT NULL DEFAULT FALSE    -- СЂР°Р·РѕР±СЂР°РЅ Р»Рё С‚РµРєСЃС‚ РІ С†РёС„СЂС‹
);

-- Р¦РёС„СЂРѕРІС‹Рµ СЂРµР·СѓР»СЊС‚Р°С‚С‹ РїРѕ СѓС‡Р°СЃС‚РєР°Рј
CREATE TABLE precinct_results (
    id SERIAL PRIMARY KEY,
    election_id INT NOT NULL REFERENCES elections(id) ON DELETE CASCADE,
    precinct_id INT NOT NULL REFERENCES precincts(id) ON DELETE CASCADE,
    subject_id INT NOT NULL REFERENCES election_subjects(id) ON DELETE CASCADE,
    votes INT NOT NULL,
    UNIQUE (election_id, precinct_id, subject_id)
);

-- РРЅРґРµРєСЃС‹ РґР»СЏ РїСЂРѕРёР·РІРѕРґРёС‚РµР»СЊРЅРѕСЃС‚Рё
CREATE INDEX idx_regions_parent ON regions(parent_id);
CREATE INDEX idx_regions_type ON regions(type);
CREATE INDEX idx_precincts_region ON precincts(region_id);
CREATE INDEX idx_precinct_results_election ON precinct_results(election_id);
CREATE INDEX idx_precinct_results_precinct ON precinct_results(precinct_id);
CREATE INDEX idx_protocol_photos_election ON protocol_photos(election_id);
CREATE INDEX idx_protocol_photos_precinct ON protocol_photos(precinct_id);
