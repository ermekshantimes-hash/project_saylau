from app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    # Проверка подключения
    result = conn.execute(text('SELECT current_database()'))
    print('Database:', result.fetchone()[0])
    
    # Проверка таблиц
    result = conn.execute(text("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name
    """))
    print('\nТаблицы:')
    for row in result:
        print(f'  - {row[0]}')
    
    # Проверка данных
    result = conn.execute(text('SELECT COUNT(*) FROM precincts'))
    print(f'\nУИК: {result.fetchone()[0]}')
    
    result = conn.execute(text('SELECT COUNT(*) FROM candidates'))
    print(f'Кандидаты: {result.fetchone()[0]}')
    
    result = conn.execute(text('SELECT COUNT(*) FROM precinct_tallies'))
    print(f'Результаты: {result.fetchone()[0]}')
