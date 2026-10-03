"""Run the finite basic, TCP, and FatTree examples without a display."""

import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    environment = {**os.environ, "MPLBACKEND": "Agg"}
    for name in ("basic.py", "tcp.py", "fattree.py"):
        start = perf_counter()
        try:
            subprocess.run(
                [sys.executable, str(root / "examples" / name)],
                cwd=root,
                env=environment,
                capture_output=True,
                timeout=90,
                check=True,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            # Preserve the example's output when a failure needs diagnosis.
            for output in (error.stdout, error.stderr):
                if output:
                    sys.stderr.buffer.write(output)
            print(f"{name}: {error}", file=sys.stderr)
            return 1
        print(f"{name}: passed ({perf_counter() - start:.2f}s)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
