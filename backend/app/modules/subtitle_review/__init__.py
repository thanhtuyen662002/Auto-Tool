from app.modules.subtitle_review.subtitle_review_schema import (
    ApproveSubtitleDocumentRequest,
    BulkUpdateSubtitleLinesRequest,
    RenderApprovedSubtitleDocumentsRequest,
    RenderSubtitleReviewDocumentRequest,
    SaveSubtitleReviewRequest,
    SubtitleReviewDocument,
    SubtitleReviewDocumentListResponse,
    SubtitleReviewRenderResponse,
    SubtitleReviewStatus,
    SubtitleLine,
    UpdateSubtitleLineRequest,
)
__all__ = [
    "ApproveSubtitleDocumentRequest",
    "BulkUpdateSubtitleLinesRequest",
    "RenderApprovedSubtitleDocumentsRequest",
    "RenderSubtitleReviewDocumentRequest",
    "SaveSubtitleReviewRequest",
    "SubtitleReviewDocument",
    "SubtitleReviewDocumentListResponse",
    "SubtitleReviewRenderResponse",
    "SubtitleReviewService",
    "SubtitleReviewStatus",
    "SubtitleLine",
    "UpdateSubtitleLineRequest",
]


def __getattr__(name: str):
    if name == "SubtitleReviewService":
        from app.modules.subtitle_review.subtitle_review_service import SubtitleReviewService

        return SubtitleReviewService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
