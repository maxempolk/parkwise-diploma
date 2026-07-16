# Parkwise

Parkwise is an educational MVP for managing a private parking facility. Guests
can start parking immediately or book in advance, while administrators configure
spaces and tariffs and manage reservations and parking sessions.

The project includes a web application and an Android wrapper. The Android app
uses `WebView` to display the real web interface and communicate with the same
FastAPI backend.

## Features

- Instant parking with automatic space assignment.
- Advance booking by space type, date and time.
- Standard, EV charging and Accessible space types.
- Availability checks that consider active sessions, blocks, reservations and a
  10-minute booking buffer.
- Session extension and completion with USD pricing in 30-minute blocks.
- My parking page with current, upcoming and completed records.
- Administrator dashboard for spaces, blocks, tariffs, sessions, reservations,
  calendar and basic statistics.
- JWT authentication for the administrator.

## Technology stack

- Backend: Python, FastAPI, SQLAlchemy and Alembic.
- Database: SQLite for local development; PostgreSQL through `DATABASE_URL`.
- Web client: React, TypeScript, Vite and plain CSS.
- Mobile application: Kotlin and Android WebView.

## Project structure

- `backend/` — API, models, services, migrations and tests.
- `frontend/` — React interface for guests and administrators.
- `mobile-app/` — Kotlin Android project.
- `parkwise.py` — cross-platform development launcher.
- `run_mobile_backend.py` — starts the backend and built web client together.
- `PROJECT.MD` — project requirements.
- `UI.MD` — UI requirements.
- `docs/uk/README.md` — Ukrainian-language documentation.

## Quick start on macOS and Linux

Requirements: Python 3.11+, Node.js LTS and npm.

```bash
git clone <repository-url>
cd parking-booking

python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

cd frontend
npm install
cd ..

python run_mobile_backend.py
```

After startup:

- website: `http://localhost:8000`;
- admin panel: `http://localhost:8000/admin/login`;
- API health check: `http://localhost:8000/api/health`;
- API documentation: `http://localhost:8000/docs`.

`run_mobile_backend.py` builds the React client first and then starts FastAPI on
port `8000`.

## Cross-platform launcher

`parkwise.py` detects the operating system and resolves the local Python virtual
environment, Node.js, JDK 17 and Android SDK tools. It supports macOS, Windows
and Linux paths, including Android SDK locations used by Android Studio.

```bash
# Build the web client and start FastAPI at http://localhost:8000
python parkwise.py --backend

# Start the Vite development server at http://localhost:5173
python parkwise.py --frontend

# Start the backend when needed, boot an emulator, build the APK and open Parkwise
python parkwise.py --mobile
```

Flags can be combined:

```bash
python parkwise.py --backend --frontend --mobile
```

For mobile development, the launcher uses `PARKWISE_AVD` when it is set. If it
is not set, it prefers an AVD named `parking_test` and otherwise uses the first
available AVD. On Windows, set `ANDROID_SDK_ROOT` if Android Studio is installed
outside its default location.

## Quick start on Windows

Install Python 3.11+ and Node.js LTS, then open PowerShell in the project root.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt

cd frontend
npm install
cd ..

python run_mobile_backend.py
```

If PowerShell blocks virtual-environment activation, run this command once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Database configuration

The default local database is `backend/app.db`. To create a clean database,
apply migrations before the first run:

```bash
source .venv/bin/activate
cd backend
alembic upgrade head
```

To use PostgreSQL, create `backend/.env` from `backend/.env.example` and set a
connection string:

```env
DATABASE_URL=postgresql+psycopg://user:password@localhost/parkwise
```

Before a demonstration, configure at least one active parking space and a tariff
for the required space type in the admin panel.

## Administrator access

Default local credentials:

```text
Username: admin
Password: admin
```

For a different password, change `ADMIN_PASSWORD_HASH` and `JWT_SECRET` in
`backend/.env`. The password is stored as a SHA-256 hash.

## Android application

### Requirements

- Android Studio;
- Android SDK Platform 34;
- Android Emulator;
- JDK 17;
- a running `python run_mobile_backend.py` process.

Open `mobile-app/` in Android Studio, select or create an Android 14 / API 34
emulator and select **Run**.

Build a debug APK from a terminal:

```bash
cd mobile-app
./gradlew assembleDebug
```

On Windows:

```powershell
cd mobile-app
.\gradlew.bat assembleDebug
```

The APK is created at:

```text
mobile-app/app/build/outputs/apk/debug/app-debug.apk
```

The Android emulator reaches the host backend via `http://10.0.2.2:8000`. This
address is already configured in `mobile-app/app/build.gradle.kts`.

For a physical Android device, replace the address with the computer's local
network IP, for example `http://192.168.1.50:8000`, and rebuild the APK. The
phone and computer must use the same Wi-Fi network.

## Tests

Run backend tests:

```bash
cd backend
../.venv/bin/python -m pytest
```

Run the frontend test and production build:

```bash
cd frontend
npm test -- --run
npm run build
```

## Troubleshooting

| Symptom | Resolution |
| --- | --- |
| `Not Found` at `/admin/login` | Start the project with `python run_mobile_backend.py`, not an outdated standalone server. |
| Android shows a connection error | Confirm that the backend is running on port `8000`; use `10.0.2.2` in an emulator, not `localhost`. |
| No spaces are available | Add active spaces of the required type in the admin panel or unblock existing spaces. |
| A second parking session cannot start | This is expected: one vehicle may have only one active session. |
| An overlapping booking cannot be created | This is expected: the system checks capacity and prevents overlap for one vehicle. |

## Demonstration checklist

1. Start `python run_mobile_backend.py`.
2. Open the Android emulator and Parkwise.
3. Open the admin panel in a browser.
4. Confirm that spaces and tariffs exist in the database.
5. Prepare three short scenarios: administrator setup, instant parking and
   advance booking.
