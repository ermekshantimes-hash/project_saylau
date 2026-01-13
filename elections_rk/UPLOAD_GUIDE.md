# 📤 Инструкция по загрузке результатов выборов

## 🎯 Что можно загружать?

### 1. **CSV файл с результатами голосования**

#### Формат файла:
```csv
precinct_number,candidate_name,votes
1165,Касым-Жомарт Токаев,1250
1165,Марат Нурланов,980
1165,Айгуль Сейтжанова,750
```

#### Поля:
- `precinct_number` - номер участка (например: 1165, 1166, 1167)
- `candidate_name` - полное имя кандидата (должно точно совпадать с именем в БД)
- `votes` - количество голосов (целое число)

#### Кандидаты (должны точно совпадать):
- Касым-Жомарт Токаев
- Марат Нурланов
- Айгуль Сейтжанова
- Бауыржан Калымбетов
- Жанар Айтбаева
- Против всех

### 2. **Фото/скан протокола участка**

Форматы: JPG, PNG, PDF
Размер: до 10 МБ

---

## 🚀 Как загрузить CSV файл?

### Вариант 1: Через Python скрипт

```python
import requests

# Путь к вашему CSV файлу
csv_file = 'examples/sample_results.csv'

# ID выборов (обычно 1 для президентских выборов 2024)
election_id = 1

# Загрузка
with open(csv_file, 'rb') as f:
    response = requests.post(
        'http://localhost:8888/api/results/upload-csv',
        data={'election_id': election_id},
        files={'file': f}
    )

print(response.json())
```

### Вариант 2: Через curl (PowerShell)

```powershell
curl -X POST "http://localhost:8888/api/results/upload-csv" `
  -F "election_id=1" `
  -F "file=@examples/sample_results.csv"
```

### Вариант 3: Через веб-интерфейс

Откройте: **http://localhost:8888/static/upload.html**

1. Выберите выборы (Президентские выборы 2024)
2. Нажмите "Загрузить CSV" (кнопку нужно добавить на страницу)
3. Выберите файл
4. Нажмите "Загрузить"

---

## 📋 Примеры файлов

### `examples/sample_results.csv` - минимальный пример
3 участка × 6 кандидатов = 18 записей

### Создание своего файла:

**Excel/Google Sheets:**
1. Создайте таблицу с 3 колонками: `precinct_number`, `candidate_name`, `votes`
2. Заполните данные
3. Сохраните как CSV (UTF-8)

**Python:**
```python
import csv

data = [
    {'precinct_number': 1165, 'candidate_name': 'Касым-Жомарт Токаев', 'votes': 1250},
    {'precinct_number': 1165, 'candidate_name': 'Марат Нурланов', 'votes': 980},
    # ... добавьте больше записей
]

with open('my_results.csv', 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['precinct_number', 'candidate_name', 'votes'])
    writer.writeheader()
    writer.writerows(data)
```

---

## ✅ Проверка результатов

После загрузки откройте:
- **http://localhost:8888/static/index.html** - общая статистика
- **http://localhost:8888/static/map.html** - карта результатов
- **http://localhost:8888/api/elections/1/stats** - API статистики

---

## ⚠️ Частые ошибки

### "Участок не найден"
- Проверьте, что номер участка существует в БД (номера от 1001 до 12999)
- В примере используются участки: 1165, 1166, 1167

### "Кандидат не найден"
- Имя должно точно совпадать (с пробелами и дефисами)
- Используйте имена из списка выше

### "Ошибка кодировки"
- Сохраняйте CSV в кодировке **UTF-8**
- В Excel: "Сохранить как" → "CSV UTF-8"

---

## 📊 Номера участков в БД

Участки с результатами находятся в диапазоне: **1001-12999**

Проверить доступные участки:
```python
import requests
response = requests.get('http://localhost:8888/api/regions/101/precincts')
print(response.json())
```

---

## 🎨 Массовая генерация тестовых данных

```python
import csv
import random

candidates = [
    'Касым-Жомарт Токаев',
    'Марат Нурланов',
    'Айгуль Сейтжанова',
    'Бауыржан Калымбетов',
    'Жанар Айтбаева',
    'Против всех'
]

with open('bulk_test_data.csv', 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['precinct_number', 'candidate_name', 'votes'])
    
    # 100 участков
    for precinct in range(1165, 1265):
        for candidate in candidates:
            votes = random.randint(500, 1500)
            writer.writerow([precinct, candidate, votes])

print("Создано 600 записей для 100 участков")
```

Загрузите этот файл и получите данные для 100 участков!
