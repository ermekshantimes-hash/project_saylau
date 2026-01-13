import os, json
from urllib.request import urlopen
import ssl

# Попытка взять токен из .env
token = None
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
try:
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('TELEGRAM_BOT_TOKEN='):
                token = line.split('=', 1)[1]
                break
except FileNotFoundError:
    pass

# fallback на переменную окружения
if not token:
    token = os.environ.get('TELEGRAM_BOT_TOKEN')

if not token:
    print('NO_TOKEN')
    raise SystemExit(0)

# Запрос к Telegram API getMe
url = f'https://api.telegram.org/bot{token}/getMe'
try:
    # some environments have SSL verification issues; create unverified context
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    data = json.load(urlopen(url, timeout=10, context=ctx))
except Exception as e:
    print('ERROR_REQUEST', str(e))
    raise SystemExit(1)

if not data.get('ok'):
    print('ERROR_RESPONSE', data)
    raise SystemExit(1)

result = data['result']
first_name = result.get('first_name') or ''
username = result.get('username') or ''
print('BOT_NAME:' + first_name)
print('BOT_USERNAME:@' + username)
