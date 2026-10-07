from datetime import datetime
import csv
import io
import random
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.database import get_db
from core.init_db import initialize_database
from models.experiment import Experiment
from models.measurement import Measurement
from services.rto_engine import RTOEstimator


app = FastAPI(
    title="RTTune API",
    version="2.0.0",
    description="Adaptive retransmission timeout monitoring and simulation system.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_PACKET_COUNT = 10000
MAX_RTT_SECONDS = 60.0
MAX_DELAY_SECONDS = 60.0
MAX_JITTER_SECONDS = 60.0

FIXED_RTO = 0.1

estimator = RTOEstimator()
current_experiment_id: Optional[int] = None
sequence_number = 0


class ExperimentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=500)
    mode: str = Field(default="adaptive", pattern="^(adaptive|fixed|comparison)$")
    packet_count: int = Field(default=100, ge=1, le=MAX_PACKET_COUNT)
    base_delay: float = Field(default=0.05, gt=0, le=MAX_DELAY_SECONDS)
    jitter: float = Field(default=0.01, ge=0, le=MAX_JITTER_SECONDS)
    packet_loss: float = Field(default=0.0, ge=0, le=100)


class RTTRequest(BaseModel):
    rtt: float = Field(gt=0, le=MAX_RTT_SECONDS)


def get_experiment_or_404(experiment_id: int, db: Session) -> Experiment:
    experiment = db.get(Experiment, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found.")
    return experiment


def experiment_to_dict(experiment: Experiment) -> dict:
    return {
        "id": experiment.id,
        "name": experiment.name,
        "description": experiment.description,
        "mode": experiment.mode,
        "packet_count": experiment.packet_count,
        "base_delay": experiment.base_delay,
        "jitter": experiment.jitter,
        "packet_loss": experiment.packet_loss,
        "status": experiment.status,
        "started_at": experiment.started_at.isoformat() if experiment.started_at else None,
        "completed_at": experiment.completed_at.isoformat() if experiment.completed_at else None,
    }


def measurement_to_dict(measurement: Measurement) -> dict:
    return {
        "id": measurement.id,
        "experiment_id": measurement.experiment_id,
        "sequence_number": measurement.sequence_number,
        "rtt": measurement.rtt,
        "srtt": measurement.srtt,
        "rttvar": measurement.rttvar,
        "rto": measurement.rto,
        "was_retransmission": measurement.was_retransmission,
        "timeout_occurred": measurement.timeout_occurred,
        "timestamp": measurement.timestamp.isoformat(),
    }


def reset_runtime_state():
    global estimator, current_experiment_id, sequence_number
    estimator = RTOEstimator()
    current_experiment_id = None
    sequence_number = 0


def measurements_for(db: Session, experiment_id: int):
    return (
        db.query(Measurement)
        .filter(Measurement.experiment_id == experiment_id)
        .order_by(Measurement.sequence_number.asc())
        .all()
    )


def build_summary(db: Session, experiment_id: int) -> dict:
    rows = measurements_for(db, experiment_id)
    successful = [m for m in rows if not m.timeout_occurred and m.rtt > 0]
    timeouts = [m for m in rows if m.timeout_occurred]

    rtts = [m.rtt for m in successful]
    rtos = [m.rto for m in rows]

    return {
        "total_measurements": len(rows),
        "successful_measurements": len(successful),
        "timeouts": len(timeouts),
        "average_rtt": sum(rtts) / len(rtts) if rtts else None,
        "minimum_rtt": min(rtts) if rtts else None,
        "maximum_rtt": max(rtts) if rtts else None,
        "average_rto": sum(rtos) / len(rtos) if rtos else None,
        "latest_rto": rows[-1].rto if rows else None,
        "latest_srtt": rows[-1].srtt if rows else None,
        "latest_rttvar": rows[-1].rttvar if rows else None,
    }


def generate_rtt_sequence(
    packet_count: int,
    base_delay: float,
    jitter: float,
    packet_loss: float,
    rng: random.Random,
) -> list[Optional[float]]:
    sequence: list[Optional[float]] = []
    for _ in range(packet_count):
        if rng.random() < packet_loss / 100:
            sequence.append(None)
            continue

        value = base_delay + rng.uniform(-jitter, jitter)
        sequence.append(max(0.001, value))
    return sequence


@app.on_event("startup")
def startup():
    initialize_database()


@app.get("/")
def root():
    return {
        "name": "RTTune API",
        "version": "2.0.0",
        "status": "running",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/experiments")
def list_experiments(db: Session = Depends(get_db)):
    rows = (
        db.query(Experiment)
        .order_by(Experiment.id.desc())
        .all()
    )
    return [experiment_to_dict(row) for row in rows]


@app.get("/api/experiments/{experiment_id}")
def get_experiment(experiment_id: int, db: Session = Depends(get_db)):
    return experiment_to_dict(get_experiment_or_404(experiment_id, db))


@app.get("/api/experiments/{experiment_id}/summary")
def get_summary(experiment_id: int, db: Session = Depends(get_db)):
    get_experiment_or_404(experiment_id, db)
    return build_summary(db, experiment_id)


@app.get("/api/experiments/{experiment_id}/measurements")
def get_measurements(
    experiment_id: int,
    db: Session = Depends(get_db),
):
    get_experiment_or_404(experiment_id, db)
    return [measurement_to_dict(m) for m in measurements_for(db, experiment_id)]


@app.post("/api/experiments")
def create_experiment(
    request: ExperimentRequest,
    db: Session = Depends(get_db),
):
    global current_experiment_id, sequence_number, estimator

    experiment = Experiment(
        name=request.name.strip(),
        description=request.description.strip() if request.description else None,
        mode=request.mode,
        packet_count=request.packet_count,
        base_delay=request.base_delay,
        jitter=request.jitter,
        packet_loss=request.packet_loss,
        status="created",
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)

    current_experiment_id = experiment.id
    sequence_number = 0
    estimator = RTOEstimator()

    return experiment_to_dict(experiment)


@app.post("/api/experiments/{experiment_id}/select")
def select_experiment(
    experiment_id: int,
    db: Session = Depends(get_db),
):
    global current_experiment_id, sequence_number, estimator

    get_experiment_or_404(experiment_id, db)

    latest = (
        db.query(Measurement)
        .filter(Measurement.experiment_id == experiment_id)
        .order_by(Measurement.sequence_number.desc())
        .first()
    )

    current_experiment_id = experiment_id
    estimator = RTOEstimator()

    if latest:
        estimator.state.srtt = latest.srtt
        estimator.state.rttvar = latest.rttvar
        estimator.state.rto = latest.rto
        sequence_number = latest.sequence_number
    else:
        sequence_number = 0

    return {
        "success": True,
        "experiment_id": experiment_id,
        "sequence_number": sequence_number,
        "state": estimator.get_state(),
    }


@app.post("/api/rto/update")
def update_rto(
    request: RTTRequest,
    db: Session = Depends(get_db),
):
    global current_experiment_id, sequence_number

    if current_experiment_id is None:
        raise HTTPException(
            status_code=400,
            detail="Select or create an experiment first.",
        )

    experiment = get_experiment_or_404(current_experiment_id, db)
    state = estimator.update(request.rtt)

    sequence_number += 1

    measurement = Measurement(
        experiment_id=experiment.id,
        sequence_number=sequence_number,
        rtt=request.rtt,
        srtt=state.srtt,
        rttvar=state.rttvar,
        rto=state.rto,
        was_retransmission=False,
        timeout_occurred=False,
    )
    db.add(measurement)

    experiment.status = "running"
    if experiment.started_at is None:
        experiment.started_at = datetime.utcnow()

    db.commit()
    db.refresh(measurement)

    return {
        "success": True,
        "measurement": measurement_to_dict(measurement),
        "state": estimator.get_state(),
    }


@app.post("/api/experiments/{experiment_id}/simulate")
def simulate_experiment(
    experiment_id: int,
    db: Session = Depends(get_db),
):
    global current_experiment_id, sequence_number, estimator

    experiment = get_experiment_or_404(experiment_id, db)

    db.query(Measurement).filter(
        Measurement.experiment_id == experiment_id
    ).delete(synchronize_session=False)

    current_experiment_id = experiment_id
    sequence_number = 0
    estimator = RTOEstimator()

    experiment.status = "running"
    experiment.started_at = datetime.utcnow()
    experiment.completed_at = None

    rng = random.Random()
    generated = generate_rtt_sequence(
        experiment.packet_count,
        experiment.base_delay,
        experiment.jitter,
        experiment.packet_loss,
        rng,
    )

    successful = 0
    lost = 0

    for rtt in generated:
        sequence_number += 1

        if rtt is None:
            lost += 1
            continue

        successful += 1
        state = estimator.update(rtt)

        db.add(
            Measurement(
                experiment_id=experiment_id,
                sequence_number=sequence_number,
                rtt=rtt,
                srtt=state.srtt,
                rttvar=state.rttvar,
                rto=state.rto,
                was_retransmission=False,
                timeout_occurred=False,
            )
        )

    experiment.status = "completed"
    experiment.completed_at = datetime.utcnow()

    db.commit()

    return {
        "success": True,
        "experiment_id": experiment_id,
        "packet_count": experiment.packet_count,
        "successful_packets": successful,
        "lost_packets": lost,
        "summary": build_summary(db, experiment_id),
    }


@app.post("/api/experiments/{experiment_id}/timeout")
def timeout_experiment(
    experiment_id: int,
    db: Session = Depends(get_db),
):
    global current_experiment_id, sequence_number, estimator

    experiment = get_experiment_or_404(experiment_id, db)

    if current_experiment_id != experiment_id:
        current_experiment_id = experiment_id
        latest = (
            db.query(Measurement)
            .filter(Measurement.experiment_id == experiment_id)
            .order_by(Measurement.sequence_number.desc())
            .first()
        )
        estimator = RTOEstimator()
        if latest:
            estimator.state.srtt = latest.srtt
            estimator.state.rttvar = latest.rttvar
            estimator.state.rto = latest.rto
            sequence_number = latest.sequence_number
        else:
            sequence_number = 0

    state = estimator.timeout_backoff()
    sequence_number += 1

    measurement = Measurement(
        experiment_id=experiment_id,
        sequence_number=sequence_number,
        rtt=0.0,
        srtt=state.srtt if state.srtt is not None else 0.0,
        rttvar=state.rttvar if state.rttvar is not None else 0.0,
        rto=state.rto,
        was_retransmission=True,
        timeout_occurred=True,
    )
    db.add(measurement)
    experiment.status = "timeout"
    db.commit()
    db.refresh(measurement)

    return {
        "success": True,
        "message": "Timeout recorded and RTO backed off.",
        "measurement": measurement_to_dict(measurement),
        "state": estimator.get_state(),
    }


@app.post("/api/experiments/{experiment_id}/compare")
def compare_experiment(
    experiment_id: int,
    db: Session = Depends(get_db),
):
    experiment = get_experiment_or_404(experiment_id, db)

    rng = random.Random()
    generated = generate_rtt_sequence(
        experiment.packet_count,
        experiment.base_delay,
        experiment.jitter,
        experiment.packet_loss,
        rng,
    )

    adaptive = RTOEstimator()
    fixed_timeouts = 0
    adaptive_timeouts = 0
    fixed_rtos: list[float] = []
    adaptive_rtos: list[float] = []
    adaptive_results = []
    fixed_results = []

    for index, rtt in enumerate(generated, start=1):
        if rtt is None:
            fixed_timeouts += 1
            adaptive_timeouts += 1

            fixed_rtos.append(FIXED_RTO)
            adaptive_rtos.append(adaptive.state.rto)

            fixed_results.append({
                "sequence": index,
                "rtt": None,
                "rto": FIXED_RTO,
                "timeout": True,
            })
            adaptive_results.append({
                "sequence": index,
                "rtt": None,
                "rto": adaptive.state.rto,
                "timeout": True,
            })
            adaptive.timeout_backoff()
            continue

        fixed_timeout = rtt > FIXED_RTO
        if fixed_timeout:
            fixed_timeouts += 1

        state = adaptive.update(rtt)
        adaptive_timeout = rtt > state.rto
        if adaptive_timeout:
            adaptive_timeouts += 1

        fixed_rtos.append(FIXED_RTO)
        adaptive_rtos.append(state.rto)

        fixed_results.append({
            "sequence": index,
            "rtt": rtt,
            "rto": FIXED_RTO,
            "timeout": fixed_timeout,
        })
        adaptive_results.append({
            "sequence": index,
            "rtt": rtt,
            "rto": state.rto,
            "timeout": adaptive_timeout,
        })

        if adaptive_timeout:
            adaptive.timeout_backoff()

    return {
        "experiment_id": experiment_id,
        "fixed": {
            "rto": FIXED_RTO,
            "timeouts": fixed_timeouts,
            "average_rto": sum(fixed_rtos) / len(fixed_rtos) if fixed_rtos else 0,
            "results": fixed_results,
        },
        "adaptive": {
            "timeouts": adaptive_timeouts,
            "average_rto": sum(adaptive_rtos) / len(adaptive_rtos) if adaptive_rtos else 0,
            "results": adaptive_results,
        },
    }


@app.get("/api/experiments/{experiment_id}/export.csv")
def export_csv(
    experiment_id: int,
    db: Session = Depends(get_db),
):
    experiment = get_experiment_or_404(experiment_id, db)
    rows = measurements_for(db, experiment_id)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "experiment_id",
        "sequence_number",
        "rtt_seconds",
        "srtt_seconds",
        "rttvar_seconds",
        "rto_seconds",
        "was_retransmission",
        "timeout_occurred",
        "timestamp",
    ])

    for row in rows:
        writer.writerow([
            row.experiment_id,
            row.sequence_number,
            row.rtt,
            row.srtt,
            row.rttvar,
            row.rto,
            row.was_retransmission,
            row.timeout_occurred,
            row.timestamp.isoformat(),
        ])

    output.seek(0)

    filename = f"rttune_experiment_{experiment.id}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


@app.delete("/api/experiments/{experiment_id}")
def delete_experiment(
    experiment_id: int,
    db: Session = Depends(get_db),
):
    global current_experiment_id, sequence_number, estimator

    experiment = get_experiment_or_404(experiment_id, db)

    db.query(Measurement).filter(
        Measurement.experiment_id == experiment_id
    ).delete(synchronize_session=False)

    db.delete(experiment)
    db.commit()

    if current_experiment_id == experiment_id:
        reset_runtime_state()

    return {
        "success": True,
        "message": f"Experiment #{experiment_id} deleted.",
    }
