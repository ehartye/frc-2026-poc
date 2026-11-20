"""Copy the exact Fusion-generated preview from the issued F3D. Python 3.14 supports its Zstandard ZIP entry."""

from pathlib import Path
import struct
from zipfile import ZipFile

ENTRY = "FusionAssetName[Active]/Previews/big.png"


def extract(source, output):
    with ZipFile(source) as archive:
        data = archive.read(ENTRY)
    if data[:8] != b"\x89PNG\r\n\x1a\n" or struct.unpack(">II", data[16:24]) != (
        1024,
        1024,
    ):
        raise ValueError(
            "The issued native preview is not the inspected 1024 by 1024 PNG."
        )
    output.write_bytes(data)


if __name__ == "__main__":
    folder = Path(__file__).resolve().parent
    extract(folder / "display.f3d", folder / "assembly.png")
