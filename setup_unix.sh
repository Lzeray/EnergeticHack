#!/usr/bin/env bash
set -euo pipefail

PYBIN=""
for candidate in python3.12 python3.11 python3.13 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PYBIN="$candidate"
        break
    fi
done

if [ -z "$PYBIN" ]; then
    echo "[X] Не найден python3. Установи Python 3.11-3.13 (https://www.python.org/downloads/) и запусти скрипт снова."
    exit 1
fi

echo "[OK] Использую $PYBIN ($($PYBIN --version))"

"$PYBIN" -m venv .venv
source .venv/bin/activate

pip install --upgrade pip -q
pip install -r requirements.txt

cat <<'EOF'

=== Готово ===
Дальше в этом же терминале:
  python -m scripts.run_demo --period daily
  uvicorn app.main:app --host 0.0.0.0 --port 8899

В следующий раз перед запуском активируй окружение:
  source .venv/bin/activate
EOF
