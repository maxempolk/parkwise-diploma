# Parkwise

Parkwise — навчальний MVP для керування приватним паркуванням. Гість може
розпочати паркування одразу або забронювати місце заздалегідь. Адміністратор
налаштовує місця й тарифи, керує бронюваннями та активними сесіями.

## Основні можливості

- Швидке паркування з автоматичним призначенням місця.
- Попереднє бронювання за типом місця, датою та часом.
- Типи місць: Standard, EV charging та Accessible.
- Перевірка доступності з урахуванням бронювань, активних сесій, блокувань і
  10-хвилинного буфера.
- Продовження та завершення сесії з розрахунком вартості в USD.
- Сторінка My parking з активними, майбутніми й завершеними записами.
- Адміністративна панель для місць, тарифів, бронювань, календаря та
  статистики.

## Швидкий запуск

Потрібні Python 3.11+, Node.js LTS і npm.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

cd frontend
npm install
cd ..

python run_mobile_backend.py
```

Після запуску вебсайт доступний за адресою `http://localhost:8000`, а панель
адміністратора — за адресою `http://localhost:8000/admin/login`.

Локальні облікові дані адміністратора:

```text
Username: admin
Password: admin
```

## Android

Відкрийте папку `mobile-app/` в Android Studio, запустіть Android-емулятор і
натисніть **Run**. Backend має бути запущений заздалегідь.

Емулятор звертається до backend комп’ютера за адресою
`http://10.0.2.2:8000`. Для фізичного телефона замініть цю адресу в
`mobile-app/app/build.gradle.kts` на локальну IP-адресу комп’ютера та
перезберіть APK.

## Кросплатформний запуск

Файл `parkwise.py` визначає операційну систему та шукає локальні Python, Node.js,
JDK 17 і Android SDK. Він підтримує macOS, Windows і Linux.

```bash
# Зібрати web-клієнт і запустити backend
python parkwise.py --backend

# Запустити Vite у режимі розробки
python parkwise.py --frontend

# Запустити backend за потреби, емулятор і Parkwise Android app
python parkwise.py --mobile
```

Прапорці можна поєднувати. Якщо потрібен конкретний Android Virtual Device,
встановіть змінну середовища `PARKWISE_AVD`. Без неї launcher спочатку шукає
емулятор з назвою `parking_test`.

## Тести

```bash
cd backend
../.venv/bin/python -m pytest

cd ../frontend
npm test -- --run
npm run build
```
