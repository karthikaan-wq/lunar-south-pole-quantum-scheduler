
from fastapi import APIRouter, HTTPException

from backend.scheduling.candidates import CandidateGenerationLimitError
from backend.scheduling.exact import ExactSolveError, ExactSolveLimitError
from backend.scheduling.models import SchedulingProblem
from backend.scheduling.service import run_classical_scheduler

router = APIRouter(prefix="/api/scheduling", tags=["Classical Scheduler"])


@router.post("/run")
def run_scheduler_endpoint(problem: SchedulingProblem):
    """Prepare real environmental constraints and run both schedulers."""

    try:
        return run_classical_scheduler(problem)

    except CandidateGenerationLimitError as error:
        raise HTTPException(status_code=422, detail=str(error))

    except (ExactSolveLimitError, ExactSolveError) as error:
        raise HTTPException(status_code=422, detail=str(error))

    except FileNotFoundError as error:
        raise HTTPException(status_code=503, detail=str(error))

    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
