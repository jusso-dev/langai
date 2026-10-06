"""Durable DB outbox + Redis/RQ execution. Restarting recovers enqueue failures."""

import logging
import time
from datetime import timedelta
from redis import Redis
from rq import Queue, SpawnWorker
from rq.job import Job
from rq.exceptions import NoSuchJobError
from sqlalchemy import select
from apps.api.config import settings
from apps.api.db import Session, now
from apps.api.models import TrainingRun, RunEvent
from apps.worker.jobs import execute


def dispatch(queue):
    with Session() as db:
        for run in db.scalars(select(TrainingRun).where(TrainingRun.status == "QUEUED")):
            if run.cancel_requested:
                run.status, run.completed_at = "CANCELLED", now()
                continue
            job_id = f"train-{run.id}"
            try:
                job = Job.fetch(job_id, connection=queue.connection)
                if job.get_status(refresh=True) in {"queued", "started", "deferred", "scheduled"}:
                    continue
                job.delete()
            except NoSuchJobError:
                pass
            queue.enqueue(
                execute,
                run.id,
                job_id=job_id,
                job_timeout=settings().job_timeout_seconds,
                result_ttl=86400,
                failure_ttl=604800,
            )
        cutoff = now() - timedelta(minutes=5)
        for run in db.scalars(
            select(TrainingRun).where(
                TrainingRun.status.in_(["PREPARING", "TRAINING", "EVALUATING"]),
                TrainingRun.heartbeat_at < cutoff,
            )
        ):
            run.status, run.completed_at = "FAILED", now()
            run.error = "Worker heartbeat expired. Create a new run to retry."
            db.add(RunEvent(run_id=run.id, message=run.error, data={}))
        db.commit()


def main():
    logging.basicConfig(level=logging.INFO)
    connection = Redis.from_url(settings().redis_url)
    queue = Queue("training", connection=connection)
    # A separate dispatcher process can be scaled independently of CPU/GPU workers.
    import sys

    if "--dispatch" in sys.argv:
        while True:
            try:
                dispatch(queue)
            except Exception:
                logging.exception("Job dispatch failed; retrying in 5 seconds")
            time.sleep(5)
    else:
        SpawnWorker([queue], connection=connection).work(with_scheduler=False)


if __name__ == "__main__":
    main()
