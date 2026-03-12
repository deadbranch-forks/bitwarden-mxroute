#!/usr/bin/env python3
"""Dev entrypoint — optionally starts debugpy before gunicorn.

Set DEBUGPY_ENABLE=1 in compose to activate the remote debugger
on port 5678. Without it, this just execs gunicorn normally.
"""
import os
import sys

def main():
    if os.environ.get("DEBUGPY_ENABLE", "0") == "1":
        import debugpy
        debugpy.listen(("0.0.0.0", 5678))
        print("[dev-entrypoint] debugpy listening on 0.0.0.0:5678", flush=True)
        if os.environ.get("DEBUGPY_WAIT", "0") == "1":
            print("[dev-entrypoint] waiting for debugger to attach…", flush=True)
            debugpy.wait_for_client()

    # Exec gunicorn — replaces this process.
    os.execvp("gunicorn", [
        "gunicorn",
        "-w", "1",
        "-b", "0.0.0.0:6123",
        "--reload",
        "--reload-engine", "auto",
        "--access-logfile", "-",
        "--error-logfile", "-",
        "--log-level", "debug",
        "app:app",
    ])

if __name__ == "__main__":
    main()
