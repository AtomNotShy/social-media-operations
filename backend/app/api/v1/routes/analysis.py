import uuid

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import (
    WorkspaceContext,
    get_app_settings,
    get_db,
    get_workspace_context,
    require_editor,
)
from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import AnalysisRun, Transcript
from app.jobs.service import create_job
from app.modules.analysis.budget import reserve_ai_budget
from app.modules.analysis.schemas import (
    AnalysisAccepted,
    AnalysisRunRead,
    AnalyzeRequest,
    TranscriptAccepted,
    TranscriptRead,
)
from app.modules.analysis.service import (
    inspiration_content,
    request_analysis,
    request_transcript,
)
from app.schemas.common import DataResponse, ResponseMeta

router = APIRouter(prefix="/api/v1", tags=["analysis"])


@router.post(
    "/inspirations/{inspiration_id}/analyze",
    response_model=DataResponse[AnalysisAccepted],
)
def analyze_inspiration(
    inspiration_id: uuid.UUID,
    body: AnalyzeRequest,
    request: Request,
    response: Response,
    context: WorkspaceContext = Depends(require_editor),
    settings: Settings = Depends(get_app_settings),
    db: Session = Depends(get_db),
) -> DataResponse:
    run, reused = request_analysis(
        db,
        workspace_id=context.workspace.id,
        inspiration_id=inspiration_id,
        level=body.level,
        force=body.force,
        settings=settings,
    )
    db.commit()
    response.status_code = 200 if reused and run.status == "succeeded" else 202
    return DataResponse(
        data=AnalysisAccepted(
            analysis=AnalysisRunRead.model_validate(run),
            reused=reused,
        ),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get(
    "/inspirations/{inspiration_id}/analyses",
    response_model=DataResponse[list[AnalysisRunRead]],
)
def list_inspiration_analyses(
    inspiration_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    content = inspiration_content(
        db,
        workspace_id=context.workspace.id,
        inspiration_id=inspiration_id,
    )
    runs = db.scalars(
        select(AnalysisRun)
        .where(
            AnalysisRun.workspace_id == context.workspace.id,
            AnalysisRun.external_content_id == content.id,
        )
        .order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc())
    ).all()
    return DataResponse(
        data=[AnalysisRunRead.model_validate(run) for run in runs],
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get(
    "/analyses/{analysis_id}",
    response_model=DataResponse[AnalysisRunRead],
)
def get_analysis(
    analysis_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    run = db.scalar(
        select(AnalysisRun).where(
            AnalysisRun.workspace_id == context.workspace.id,
            AnalysisRun.id == analysis_id,
        )
    )
    if run is None:
        raise AppError(404, "NOT_FOUND", "Analysis not found", "Analysis not found.")
    return DataResponse(
        data=AnalysisRunRead.model_validate(run),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/analyses/{analysis_id}/retry",
    response_model=DataResponse[AnalysisRunRead],
)
def retry_analysis(
    analysis_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    settings: Settings = Depends(get_app_settings),
    db: Session = Depends(get_db),
) -> DataResponse:
    run = db.scalar(
        select(AnalysisRun).where(
            AnalysisRun.workspace_id == context.workspace.id,
            AnalysisRun.id == analysis_id,
        )
    )
    if run is None:
        raise AppError(404, "NOT_FOUND", "Analysis not found", "Analysis not found.")
    if run.status != "failed":
        raise AppError(
            409,
            "VERSION_CONFLICT",
            "Analysis cannot be retried",
            "Only failed analyses can be retried.",
        )
    run.status = "queued"
    run.error_code = None
    run.error_message = None
    run.finished_at = None
    job, _ = create_job(
        db,
        workspace_id=context.workspace.id,
        job_type="AI_ANALYSIS",
        dedupe_key=f"analysis:{run.analysis_level}:{run.input_hash}",
        payload={"analysis_run_id": str(run.id)},
        priority=60 if run.analysis_level == "l1" else 50,
    )
    run.sync_job_id = job.id
    reserve_ai_budget(
        db,
        workspace_id=context.workspace.id,
        sync_job_id=job.id,
        resource_type="analysis",
        resource_id=run.id,
        provider=run.model_provider,
        model=run.model,
        estimated_cost_usd=(
            settings.ai_l1_estimated_cost_usd
            if run.analysis_level == "l1"
            else settings.ai_l2_estimated_cost_usd
        ),
    )
    db.commit()
    return DataResponse(
        data=AnalysisRunRead.model_validate(run),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/inspirations/{inspiration_id}/transcribe",
    response_model=DataResponse[TranscriptAccepted],
)
def transcribe_inspiration(
    inspiration_id: uuid.UUID,
    request: Request,
    response: Response,
    context: WorkspaceContext = Depends(require_editor),
    settings: Settings = Depends(get_app_settings),
    db: Session = Depends(get_db),
) -> DataResponse:
    transcript, reused = request_transcript(
        db,
        workspace_id=context.workspace.id,
        inspiration_id=inspiration_id,
        settings=settings,
    )
    db.commit()
    response.status_code = 200 if reused and transcript.status == "succeeded" else 202
    return DataResponse(
        data=TranscriptAccepted(
            transcript=TranscriptRead.model_validate(transcript),
            reused=reused,
        ),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get(
    "/inspirations/{inspiration_id}/transcripts",
    response_model=DataResponse[list[TranscriptRead]],
)
def list_inspiration_transcripts(
    inspiration_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    content = inspiration_content(
        db,
        workspace_id=context.workspace.id,
        inspiration_id=inspiration_id,
    )
    transcripts = db.scalars(
        select(Transcript)
        .where(
            Transcript.workspace_id == context.workspace.id,
            Transcript.external_content_id == content.id,
        )
        .order_by(Transcript.created_at.desc(), Transcript.id.desc())
    ).all()
    return DataResponse(
        data=[TranscriptRead.model_validate(item) for item in transcripts],
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get(
    "/transcripts/{transcript_id}",
    response_model=DataResponse[TranscriptRead],
)
def get_transcript(
    transcript_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    transcript = db.scalar(
        select(Transcript).where(
            Transcript.workspace_id == context.workspace.id,
            Transcript.id == transcript_id,
        )
    )
    if transcript is None:
        raise AppError(404, "NOT_FOUND", "Transcript not found", "Transcript not found.")
    return DataResponse(
        data=TranscriptRead.model_validate(transcript),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/transcripts/{transcript_id}/retry",
    response_model=DataResponse[TranscriptRead],
)
def retry_transcript(
    transcript_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    settings: Settings = Depends(get_app_settings),
    db: Session = Depends(get_db),
) -> DataResponse:
    transcript = db.scalar(
        select(Transcript).where(
            Transcript.workspace_id == context.workspace.id,
            Transcript.id == transcript_id,
        )
    )
    if transcript is None:
        raise AppError(404, "NOT_FOUND", "Transcript not found", "Transcript not found.")
    if transcript.status != "failed":
        raise AppError(
            409,
            "VERSION_CONFLICT",
            "Transcript cannot be retried",
            "Only failed transcripts can be retried.",
        )
    transcript.status = "queued"
    transcript.error_code = None
    transcript.error_message = None
    transcript.finished_at = None
    job, _ = create_job(
        db,
        workspace_id=context.workspace.id,
        job_type="TRANSCRIBE",
        dedupe_key=f"transcript:{transcript.input_hash}",
        payload={"transcript_id": str(transcript.id)},
        priority=55,
    )
    transcript.sync_job_id = job.id
    reserve_ai_budget(
        db,
        workspace_id=context.workspace.id,
        sync_job_id=job.id,
        resource_type="transcript",
        resource_id=transcript.id,
        provider=transcript.provider,
        model=transcript.model,
        estimated_cost_usd=settings.asr_estimated_cost_usd,
    )
    db.commit()
    return DataResponse(
        data=TranscriptRead.model_validate(transcript),
        meta=ResponseMeta(request_id=request.state.request_id),
    )
