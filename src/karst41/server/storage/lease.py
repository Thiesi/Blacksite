"""OS-held sidecar lease; file existence alone never means locked."""

import os
from pathlib import Path
from typing import BinaryIO


class Lease:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.stream: BinaryIO | None = None

    def acquire(self) -> None:
        stream = self.path.open("a+b")
        try:
            if stream.seek(0, os.SEEK_END) == 0:
                stream.write(b"\0")
                stream.flush()
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            stream.close()
            raise RuntimeError("another server holds the world.db.sessions lease") from exc
        self.stream = stream

    def release(self) -> None:
        if self.stream is None:
            return
        if os.name == "nt":
            import msvcrt
            self.stream.seek(0)
            msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
        self.stream.close()
        self.stream = None
        # Never unlink the sidecar: waiters must lock the same inode.
