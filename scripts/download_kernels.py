
import urllib.request
from pathlib import Path

BASE = "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/"

FILES = {
    "naif0012.tls":
        BASE + "lsk/naif0012.tls",

    "pck00011.tpc":
        BASE + "pck/pck00011.tpc",

    "de440s.bsp":
        BASE + "spk/planets/de440s.bsp",

    "moon_pa_de440_200625.bpc":
        BASE + "pck/moon_pa_de440_200625.bpc",

    "moon_de440_250416.tf":
        BASE + "fk/satellites/moon_de440_250416.tf",
}

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGET_DIR = PROJECT_ROOT / "data" / "kernels"

def download_file(name, url):
    destination = TARGET_DIR / name
    temporary = TARGET_DIR / (name + ".part")

    if destination.exists() and destination.stat().st_size > 0:
        print(f"Already downloaded: {name}")
        return

    print(f"\nDownloading: {name}")

    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "LunarQuantumScheduler/1.0"}
        )

        with urllib.request.urlopen(request, timeout=60) as response:
            total = int(response.headers.get("Content-Length", 0))
            downloaded = 0

            with open(temporary, "wb") as output:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break

                    output.write(chunk)
                    downloaded += len(chunk)

                    if total:
                        percent = downloaded * 100 / total
                        print(
                            f"\rProgress: {percent:.1f}%",
                            end=""
                        )

        if temporary.stat().st_size == 0:
            raise RuntimeError("Downloaded file is empty")

        temporary.replace(destination)

        print(
            f"\nSaved: {name} "
            f"({destination.stat().st_size:,} bytes)"
        )

    except Exception:
        if temporary.exists():
            temporary.unlink()

        raise

def main():
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    print("NASA/JPL SPICE Kernel Downloader")
    print("Destination:", TARGET_DIR)

    for name, url in FILES.items():
        download_file(name, url)

    print("\nAll five kernel files are ready.")

if __name__ == "__main__":
    main()
