# Parkwise Mobile

Android WebView wrapper for the Parkwise web application.

## Run the local backend

From the repository root:

```bash
python run_mobile_backend.py
```

Alternatively, use the cross-platform launcher from the repository root:

```bash
python parkwise.py --mobile
```

The script builds the React client and serves it through FastAPI on port 8000.
The Android emulator reaches the host through `http://10.0.2.2:8000/`.

## Build and install

```bash
cd mobile-app
./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```
