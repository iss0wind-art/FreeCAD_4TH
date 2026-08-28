#!/bin/bash
set -e
echo "[deploy] 의존성 설치..."
pip install -r requirements.txt --quiet
echo "[deploy] 완료."
