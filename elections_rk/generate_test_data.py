import csv
import random

# Кандидаты
candidates = [
    'Касым-Жомарт Токаев',
    'Марат Нурланов',
    'Айгуль Сейтжанова',
    'Бауыржан Калымбетов',
    'Жанар Айтбаева',
    'Против всех'
]

# Создать тестовый файл с результатами для 50 участков
with open('examples/bulk_test_data.csv', 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['precinct_number', 'candidate_name', 'votes'])
    
    # 50 участков
    for precinct in range(1168, 1218):
        for candidate in candidates:
            votes = random.randint(600, 1500)
            writer.writerow([precinct, candidate, votes])

print("✅ Создан файл examples/bulk_test_data.csv")
print("   50 участков × 6 кандидатов = 300 записей")
print("\nДля загрузки запустите:")
print("   python upload_results.py examples/bulk_test_data.csv")
