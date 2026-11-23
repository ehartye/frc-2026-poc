"""Write a generated file so a concurrent reader sees the previous bytes or the new bytes, never a gap."""
import os
from pathlib import Path
import tempfile
import time

# Windows refuses a rename while a reader holds the target open. The reader finishes shortly.
BUSY_SECONDS = 10


def write_atomic(path, data, *, exclusive=False):
    """Write bytes to a temporary file beside `path`, then rename it over the target.

    A failed write leaves the previous file intact and removes the temporary file. With `exclusive`,
    an existing target raises FileExistsError and is never replaced, even by a concurrent writer."""
    path = Path(path)
    if exclusive and os.path.lexists(path):
        raise FileExistsError(str(path))
    handle, name = tempfile.mkstemp(dir=path.parent, prefix="." + path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if os.name != "nt":
            # mkstemp creates an owner-only file; a generated file keeps the mode an ordinary write gives it.
            try:
                mode = os.stat(path).st_mode & 0o777
            except OSError:
                mask = os.umask(0)
                os.umask(mask)
                mode = 0o666 & ~mask
            os.chmod(name, mode)
        deadline = time.monotonic() + BUSY_SECONDS
        while True:
            try:
                if not exclusive:
                    os.replace(name, path)
                elif os.name == "nt":
                    os.rename(name, path)  # fails when the target exists
                else:
                    os.link(name, path)  # fails when the target exists
                    os.unlink(name)
                break
            except FileExistsError:
                raise
            except PermissionError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.02)
    except BaseException:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise
