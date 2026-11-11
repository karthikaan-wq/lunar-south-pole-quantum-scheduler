
from pathlib import Path

import spiceypy as spice


# Project kernel directory
KERNEL_DIR = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "kernels"
)


# Required NASA/JPL SPICE kernels
KERNEL_FILES = [
    "naif0012.tls",
    "pck00011.tpc",
    "de440s.bsp",
    "moon_de440_250416.tf",
    "moon_pa_de440_200625.bpc",
]


_loaded = False


class KernelsMissing(Exception):
    """Raised when one or more required SPICE kernels are missing."""


def missing_kernels():
    """Return the names of missing kernel files."""
    return [
        name
        for name in KERNEL_FILES
        if not (KERNEL_DIR / name).is_file()
    ]


def kernels_present():
    """Check whether all required kernel files are present."""
    return len(missing_kernels()) == 0


def load_kernels():
    """
    Load all required SPICE kernels.

    Kernels are loaded only once during this Python process.
    """
    global _loaded

    if _loaded:
        return

    missing = missing_kernels()

    if missing:
        raise KernelsMissing(
            f"Missing SPICE kernel files in {KERNEL_DIR}: {missing}"
        )

    loaded_this_call = []

    try:
        for name in KERNEL_FILES:
            kernel_path = KERNEL_DIR / name

            spice.furnsh(str(kernel_path))
            loaded_this_call.append(name)

        _loaded = True

        print("SPICE kernels loaded successfully.")

    except Exception:
        # Roll back kernels loaded during this unsuccessful attempt.
        for name in reversed(loaded_this_call):
            spice.unload(str(KERNEL_DIR / name))

        raise
