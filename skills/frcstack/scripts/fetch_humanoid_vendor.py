"""Download vendor STEP models used by the humanoid (Waveshare ST3215, Bus Servo Driver HAT A)."""
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

OUT = Path(__file__).resolve().parents[3] / ".frcstack" / "vendor" / "humanoid"
URLS = {
    "st3215": "https://files.waveshare.com/upload/5/59/ST3215-3D.zip",
    "driver_hat_a": "https://files.waveshare.com/wiki/Bus-Servo-Driver-HAT-(A)/Bus_Servo_Driver_HAT_(A)_3D.zip",
    "st3215_2d": "https://files.waveshare.com/upload/0/08/ST3215-2D.zip",
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, url in URLS.items():
        d = OUT / name
        d.mkdir(exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            data = urllib.request.urlopen(req, timeout=120).read()
        except Exception as e:  # noqa: BLE001
            print(name, "FAILED", e)
            continue
        try:
            zipfile.ZipFile(io.BytesIO(data)).extractall(d)
        except zipfile.BadZipFile:
            (d / Path(url).name).write_bytes(data)
        for f in sorted(d.rglob("*")):
            if f.is_file():
                print(name, f.relative_to(OUT), f.stat().st_size)


if __name__ == "__main__":
    sys.exit(main())
