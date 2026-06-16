from app.modules.job_recovery.job_checkpoint_service import JobCheckpointService
from app.modules.job_recovery.job_lock_service import JobLockService
from app.modules.job_recovery.job_reconciliation_service import JobReconciliationService
from app.modules.job_recovery.job_recovery_schema import (
    JobCheckpoint,
    JobRecoveryCandidatesData,
    JobRecoveryCandidatesResponse,
    JobRecoveryJobData,
    JobRecoveryJobResponse,
    JobRecoveryActionResponse,
    JobRunStatus,
    JobStepStatus,
    RecoverableStep,
    RecoveryCandidate,
    ResumeJobRequest,
    ResumeJobResult,
    VideoStepCheckpoint,
)
from app.modules.job_recovery.job_recovery_service import JobRecoveryService

__all__ = [
    "JobCheckpoint",
    "JobCheckpointService",
    "JobLockService",
    "JobRecoveryActionResponse",
    "JobRecoveryCandidatesData",
    "JobRecoveryCandidatesResponse",
    "JobRecoveryJobData",
    "JobRecoveryJobResponse",
    "JobRecoveryService",
    "JobReconciliationService",
    "JobResumeService",
    "JobRunStatus",
    "JobStepStatus",
    "RecoverableStep",
    "RecoveryCandidate",
    "ResumeJobRequest",
    "ResumeJobResult",
    "VideoStepCheckpoint",
]


def __getattr__(name: str):
    if name == "JobResumeService":
        from app.modules.job_recovery.job_resume_service import JobResumeService

        return JobResumeService
    raise AttributeError(name)
