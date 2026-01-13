import requests
import sys

# Конфигурация
API_BASE = 'http://localhost:8888'
CSV_FILE = 'examples/sample_results.csv'
ELECTION_ID = 1

def upload_csv(file_path, election_id):
    """Загрузить CSV файл с результатами"""
    url = f'{API_BASE}/api/results/upload-csv'
    
    try:
        with open(file_path, 'rb') as f:
            response = requests.post(
                url,
                data={'election_id': election_id},
                files={'file': ('results.csv', f, 'text/csv')}
            )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ {result['message']}")
            print(f"   Добавлено: {result['added']}")
            
            if result.get('errors'):
                print(f"\n⚠️ Ошибки ({len(result['errors'])}):")
                for error in result['errors'][:10]:  # Показать первые 10 ошибок
                    print(f"   - {error}")
        else:
            print(f"❌ Ошибка {response.status_code}: {response.text}")
            
    except FileNotFoundError:
        print(f"❌ Файл не найден: {file_path}")
    except requests.exceptions.ConnectionError:
        print(f"❌ Не удалось подключиться к серверу {API_BASE}")
        print("   Убедитесь, что сервер запущен (start_server_8888.bat)")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == '__main__':
    # Использование: python upload_results.py [file.csv] [election_id]
    file_path = sys.argv[1] if len(sys.argv) > 1 else CSV_FILE
    election_id = int(sys.argv[2]) if len(sys.argv) > 2 else ELECTION_ID
    
    print(f"📤 Загрузка результатов...")
    print(f"   Файл: {file_path}")
    print(f"   Выборы: {election_id}")
    print()
    
    upload_csv(file_path, election_id)
