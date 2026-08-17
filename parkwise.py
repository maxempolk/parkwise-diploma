"""Cross-platform launcher for the Parkwise development environment."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
MOBILE = ROOT / "mobile-app"
BACKEND_PORT = 8000
FRONTEND_PORT = 5173
PACKAGE_NAME = "com.parkwise.mobile"
ACTIVITY_NAME = f"{PACKAGE_NAME}/.MainActivity"


class LauncherError(RuntimeError):
    """Raised when a required local development tool cannot be found."""


@dataclass(frozen=True)
class AndroidTools:
    """Resolved Android SDK executables for the current operating system."""

    adb: Path
    emulator: Path


def is_windows() -> bool:
    return platform.system() == "Windows"


def executable_name(name: str) -> str:
    return f"{name}.exe" if is_windows() else name


def npm_command() -> str:
    return "npm.cmd" if is_windows() else "npm"


def virtualenv_python() -> Path:
    candidate = ROOT / ".venv" / ("Scripts/python.exe" if is_windows() else "bin/python")
    if candidate.exists():
        return candidate
    raise LauncherError("Virtual environment not found. Create .venv and install backend requirements first.")


def find_existing(paths: list[Path]) -> Path | None:
    return next((path for path in paths if path.exists()), None)


def android_sdk_roots() -> list[Path]:
    roots: list[Path] = []
    for variable in ("ANDROID_SDK_ROOT", "ANDROID_HOME"):
        value = os.environ.get(variable)
        if value:
            roots.append(Path(value))

    system = platform.system()
    if system == "Darwin":
        roots.extend([
            Path.home() / "Library/Android/sdk",
            Path("/opt/homebrew/share/android-commandlinetools"),
            Path("/usr/local/share/android-commandlinetools"),
        ])
    elif system == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            roots.append(Path(local_app_data) / "Android/Sdk")
    else:
        roots.append(Path.home() / "Android/Sdk")

    return [root for root in roots if root.exists()]


def resolve_android_tools() -> AndroidTools:
    adb_from_path = shutil.which(executable_name("adb"))
    emulator_from_path = shutil.which(executable_name("emulator"))
    if adb_from_path and emulator_from_path:
        return AndroidTools(Path(adb_from_path), Path(emulator_from_path))

    for sdk_root in android_sdk_roots():
        adb = find_existing([
            sdk_root / "platform-tools" / executable_name("adb"),
            sdk_root / executable_name("adb"),
        ])
        emulator = find_existing([
            sdk_root / "emulator" / executable_name("emulator"),
            sdk_root / executable_name("emulator"),
        ])
        if adb and emulator:
            return AndroidTools(adb, emulator)

    raise LauncherError(
        "Android SDK tools were not found. Set ANDROID_SDK_ROOT or install Android Studio with Android Emulator and Platform Tools."
    )


def java_home() -> Path | None:
    configured = os.environ.get("JAVA_HOME")
    if configured and Path(configured).exists():
        return Path(configured)

    system = platform.system()
    candidates: list[Path] = []
    if system == "Darwin":
        candidates.extend([Path("/opt/homebrew/opt/openjdk@17"), Path("/usr/local/opt/openjdk@17")])
    elif system == "Windows":
        program_files = os.environ.get("PROGRAMFILES")
        if program_files:
            candidates.append(Path(program_files) / "Android/Android Studio/jbr")
    else:
        candidates.extend([Path("/usr/lib/jvm/java-17-openjdk"), Path("/usr/lib/jvm/java-17-openjdk-amd64")])
    return find_existing(candidates)


def process_environment() -> dict[str, str]:
    environment = os.environ.copy()
    resolved_java_home = java_home()
    if resolved_java_home:
        environment["JAVA_HOME"] = str(resolved_java_home)
        java_bin = resolved_java_home / "bin"
        environment["PATH"] = f"{java_bin}{os.pathsep}{environment.get('PATH', '')}"
    return environment


def run_checked(command: list[str], cwd: Path | None = None, environment: dict[str, str] | None = None) -> None:
    print(f"Running: {' '.join(command)}")
    subprocess.run(command, cwd=cwd, env=environment, check=True)


def spawn(command: list[str], cwd: Path, environment: dict[str, str]) -> subprocess.Popen[bytes]:
    print(f"Starting: {' '.join(command)}")
    return subprocess.Popen(command, cwd=cwd, env=environment)


def port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(0.2)
        return connection.connect_ex(("127.0.0.1", port)) == 0


def wait_for_port(port: int, timeout_seconds: int = 30) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if port_is_open(port):
            return
        time.sleep(0.25)
    raise LauncherError(f"Timed out waiting for port {port}.")


def build_frontend(environment: dict[str, str]) -> None:
    run_checked([npm_command(), "run", "build"], cwd=FRONTEND, environment=environment)


def migrate_backend(environment: dict[str, str]) -> None:
    run_checked(
        [str(virtualenv_python()), "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND,
        environment=environment,
    )


def start_backend(environment: dict[str, str]) -> subprocess.Popen[bytes] | None:
    if port_is_open(BACKEND_PORT):
        print(f"Backend is already available at http://localhost:{BACKEND_PORT}.")
        return None

    build_frontend(environment)
    migrate_backend(environment)
    process = spawn(
        [str(virtualenv_python()), "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(BACKEND_PORT)],
        cwd=BACKEND,
        environment=environment,
    )
    wait_for_port(BACKEND_PORT)
    print(f"Backend started at http://localhost:{BACKEND_PORT}.")
    return process


def start_frontend(environment: dict[str, str]) -> subprocess.Popen[bytes] | None:
    if port_is_open(FRONTEND_PORT):
        print(f"Frontend is already available at http://localhost:{FRONTEND_PORT}.")
        return None

    process = spawn([npm_command(), "run", "dev", "--", "--host", "0.0.0.0"], cwd=FRONTEND, environment=environment)
    wait_for_port(FRONTEND_PORT)
    print(f"Frontend started at http://localhost:{FRONTEND_PORT}.")
    return process


def connected_emulator(adb: Path) -> bool:
    result = subprocess.run([str(adb), "devices"], check=True, capture_output=True, text=True)
    return any(line.startswith("emulator-") and line.endswith("\tdevice") for line in result.stdout.splitlines())


def selected_avd(emulator: Path) -> str:
    result = subprocess.run([str(emulator), "-list-avds"], check=True, capture_output=True, text=True)
    avds = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    requested = os.environ.get("PARKWISE_AVD")
    if requested:
        if requested not in avds:
            raise LauncherError(f"PARKWISE_AVD is set to '{requested}', but that AVD was not found.")
        return requested
    if "parking_test" in avds:
        return "parking_test"
    if avds:
        return avds[0]
    raise LauncherError("No Android Virtual Device was found. Create one in Android Studio first.")


def wait_for_emulator(adb: Path, timeout_seconds: int = 120) -> None:
    subprocess.run([str(adb), "wait-for-device"], check=True)
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        result = subprocess.run([str(adb), "shell", "getprop", "sys.boot_completed"], check=True, capture_output=True, text=True)
        if result.stdout.strip() == "1":
            return
        time.sleep(1)
    raise LauncherError("Android emulator did not finish booting in time.")


def gradle_command() -> list[str]:
    wrapper = MOBILE / ("gradlew.bat" if is_windows() else "gradlew")
    if not wrapper.exists():
        raise LauncherError("Gradle wrapper was not found in mobile-app.")
    if is_windows():
        return ["cmd", "/c", str(wrapper), "assembleDebug"]
    return [str(wrapper), "assembleDebug"]


def launch_mobile(environment: dict[str, str]) -> None:
    tools = resolve_android_tools()
    if connected_emulator(tools.adb):
        print("Using the running Android emulator.")
    else:
        avd = selected_avd(tools.emulator)
        print(f"Starting Android emulator: {avd}")
        subprocess.Popen(
            [str(tools.emulator), "-avd", avd],
            cwd=ROOT,
            env=environment,
            start_new_session=True,
        )
        wait_for_emulator(tools.adb)

    run_checked(gradle_command(), cwd=MOBILE, environment=environment)
    apk = MOBILE / "app/build/outputs/apk/debug/app-debug.apk"
    if not apk.exists():
        raise LauncherError("Debug APK was not created.")

    run_checked([str(tools.adb), "install", "-r", str(apk)], cwd=ROOT, environment=environment)
    run_checked([str(tools.adb), "shell", "am", "start", "-n", ACTIVITY_NAME], cwd=ROOT, environment=environment)
    print("Parkwise mobile application is running in the emulator.")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch Parkwise services and the Android application.")
    parser.add_argument("--backend", action="store_true", help="Build the web client and start FastAPI on port 8000.")
    parser.add_argument("--frontend", action="store_true", help="Start the Vite development server on port 5173.")
    parser.add_argument("--mobile", action="store_true", help="Build, install and open the Android application in an emulator.")
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    if not any((arguments.backend, arguments.frontend, arguments.mobile)):
        print("Choose at least one flag: --backend, --frontend or --mobile.")
        return 1

    system = platform.system()
    print(f"Detected operating system: {system} ({platform.release()})")
    environment = process_environment()
    running_processes: list[subprocess.Popen[bytes]] = []

    try:
        if arguments.backend or arguments.mobile:
            backend_process = start_backend(environment)
            if backend_process:
                running_processes.append(backend_process)

        if arguments.frontend:
            frontend_process = start_frontend(environment)
            if frontend_process:
                running_processes.append(frontend_process)

        if arguments.mobile:
            launch_mobile(environment)

        if not running_processes:
            return 0

        print("Press Ctrl+C to stop the launcher services.")
        while True:
            for process in running_processes:
                if process.poll() is not None:
                    raise LauncherError(f"A launcher process stopped with exit code {process.returncode}.")
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping launcher services.")
        return 0
    except (LauncherError, subprocess.CalledProcessError) as error:
        print(f"Launcher error: {error}", file=sys.stderr)
        return 1
    finally:
        for process in running_processes:
            if process.poll() is None:
                process.terminate()
        for process in running_processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
