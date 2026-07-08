"""Reserved entrypoint for the v1 queue-based worker.

MVP runs generation in-process inside the API container (see app/worker.py,
which spawns a daemon thread per job). This module is a long-lived no-op so the
`worker` service in docker-compose.yml stays healthy. When a Redis-backed
queue is introduced (v1), this loop will pop jobs from the queue and call
app.worker.run_job(job_id).
"""
from __future__ import annotations

import logging
import time

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("worker_loop")


def main() -> None:
    log.info("CityShapeRunner worker loop: MVP generation runs in-process in the API container.")
    log.info("This container is reserved for the v1 Redis-backed queue worker.")
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
