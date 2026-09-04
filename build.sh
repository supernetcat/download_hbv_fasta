#!/usr/bin/env bash
# 一键编译 HBV FASTA 下载器为独立二进制
# 用法: ./build.sh    （产物: dist/download_hbv_fasta）
set -euo pipefail
cd "$(dirname "$0")"

APP=download_hbv_fasta

if ! python3 -c "import PyInstaller" 2>/dev/null; then
  echo "未检测到 pyinstaller，正在安装..."
  pip3 install --user pyinstaller
fi

echo "==> 编译 $APP ..."
python3 -m PyInstaller --onefile --clean --name "$APP" "$APP.py"

echo "==> 完成。二进制: $(cd dist && ls -lh $APP | awk '{print $5"\t"$9}')"
echo "    试运行: dist/$APP -n 5 -o /tmp/sample.fasta"
