#!/usr/bin/env bash
# One-shot setup on Raspberry Pi OS (Bookworm, 64-bit).  Run from the repo's software/ dir:
#     bash install.sh
set -euo pipefail
cd "$(dirname "$0")"

echo "== apt packages"
sudo apt-get update
sudo apt-get install -y python3-venv python3-dev libportaudio2 libatlas-base-dev \
     libopenblas0 git curl i2c-tools

echo "== enable SPI + I2C"
sudo raspi-config nonint do_spi 0
sudo raspi-config nonint do_i2c 0

echo "== I2S audio (MAX98357A amp + INMP441 mic, Google Voice HAT overlay)"
CFG=/boot/firmware/config.txt; [ -f "$CFG" ] || CFG=/boot/config.txt
grep -q "googlevoicehat-soundcard" "$CFG" || {
  sudo sed -i 's/^dtparam=audio=on/dtparam=audio=off/' "$CFG"
  echo "dtoverlay=googlevoicehat-soundcard" | sudo tee -a "$CFG" >/dev/null
}
sudo tee /etc/asound.conf >/dev/null <<'ASOUND'
pcm.!default {
  type asym
  playback.pcm { type plug slave.pcm "hw:0,0" }
  capture.pcm  { type plug slave.pcm "hw:0,0" }
}
ctl.!default { type hw card 0 }
ASOUND

echo "== python venv"
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install --upgrade pip wheel
pip install -r requirements.txt

echo "== models"
mkdir -p models
# Piper voice (warm US male, medium quality ~60 MB).  Swap for any voice from
# https://huggingface.co/rhasspy/piper-voices - "joe", "ryan" and "lessac" all work well.
V=https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/medium
[ -f models/en_US-ryan-medium.onnx ] || curl -L -o models/en_US-ryan-medium.onnx "$V/en_US-ryan-medium.onnx"
[ -f models/en_US-ryan-medium.onnx.json ] || curl -L -o models/en_US-ryan-medium.onnx.json "$V/en_US-ryan-medium.onnx.json"
# openWakeWord bundled models (hey_jarvis is the fallback until you train hey_ghost.onnx)
python -c "import openwakeword; openwakeword.utils.download_models()"
# faster-whisper downloads base.en on first run

[ -f .env ] || cp .env.example .env

echo "== systemd service"
sed "s#__DIR__#$(pwd)#g; s#__USER__#$USER#g" ghost.service | sudo tee /etc/systemd/system/ghost.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable ghost

cat <<MSG

Done.  Next:
  1. edit software/.env  (API key, city, name)
  2. put models/hey_ghost.onnx in place (docs/05-software-setup.md) - optional, 'hey jarvis' works meanwhile
  3. sudo reboot   (activates the I2S overlay), then:  sudo systemctl start ghost
  4. logs:  journalctl -u ghost -f
MSG
