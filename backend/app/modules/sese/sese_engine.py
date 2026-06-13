from __future__ import annotations

from app.adapters.ffmpeg_adapter import probe_media_duration
from app.modules.timeline_builder.timeline_builder import Timeline, TimelineClip, ClipType
from app.schemas.project_schema import ProjectConfig
from app.utils.logger import get_logger

logger = get_logger(__name__)


class SESEEngine:
    @staticmethod
    def synchronize(
        timeline: Timeline,
        voice_duration: float,
        config: ProjectConfig,
    ) -> Timeline:
        """
        Smart Ending Synchronization Engine (SESE)
        Synchronizes timeline duration with voiceover duration by adjusting only the end of the video.
        """
        # Ensure we don't mutate the original timeline in place
        adjusted_timeline = timeline.model_copy(
            update={
                "clips": [clip.model_copy() for clip in timeline.clips]
            }
        )
        
        if not adjusted_timeline.clips:
            return adjusted_timeline

        timeline_duration = sum(clip.duration for clip in adjusted_timeline.clips)
        delta = voice_duration - timeline_duration

        logger.info(
            f"[SESE] voice_duration={voice_duration:.3f}s, "
            f"timeline_duration={timeline_duration:.3f}s, delta={delta:.3f}s"
        )

        # Case 2 & 3: voice shorter OR delta tiny enough -> no adjustment
        if delta <= 0.5:
            if delta <= 0:
                logger.info("[SESE] Voice shorter than timeline (Case 2). No adjustment needed.")
            else:
                logger.info("[SESE] Delta <= 0.5s, no adjustment needed (Case 3).")
            return adjusted_timeline

        # Calculate max allowed extension based on seconds limit and ratio limit
        max_sec = getattr(config.render, "max_auto_extension_seconds", 8.0)
        max_ratio = getattr(config.render, "max_auto_extension_ratio", 0.4)
        
        max_allowed_extension = min(
            max_sec,
            max_ratio * timeline_duration
        )

        logger.info(
            f"[SESE] max_auto_extension_seconds={max_sec:.3f}s, "
            f"max_auto_extension_ratio={max_ratio:.3f}, "
            f"max_allowed_extension={max_allowed_extension:.3f}s"
        )

        # Check strategy or apply adjustments
        sese_failure_strategy = getattr(config.render, "sese_failure_strategy", "trim")
        
        # SESE Metadata block to record
        sese_metadata = {
            "applied": False,
            "strategy": "none",
            "added_duration": 0.0,
            "trimmed_voice": False,
            "original_duration": timeline_duration,
            "final_duration": timeline_duration,
            "warnings": []
        }

        # If delta exceeds max allowed limit
        if delta > max_allowed_extension:
            if sese_failure_strategy == "fail":
                error_msg = (
                    f"SESE failed: Voiceover duration ({voice_duration:.3f}s) exceeds "
                    f"timeline duration ({timeline_duration:.3f}s) by {delta:.3f}s, "
                    f"which is larger than max_allowed_extension ({max_allowed_extension:.3f}s)."
                )
                logger.error(error_msg)
                raise ValueError(error_msg)
            else:
                # strategy is "trim" - we apply max allowed extension and trim the rest
                logger.warning(
                    f"[SESE] Delta ({delta:.3f}s) exceeds max limit ({max_allowed_extension:.3f}s). "
                    f"Applying max extension and trimming the rest."
                )
                delta_to_apply = max_allowed_extension
                sese_metadata["trimmed_voice"] = True
                sese_metadata["warnings"].append("voice_cut_detected")
        else:
            delta_to_apply = delta

        # Apply adjustments for delta_to_apply
        applied = False
        
        # 1. Try to extend the last clip
        last_clip = adjusted_timeline.clips[-1]
        try:
            source_dur = probe_media_duration(last_clip.source_path)
            available_source = source_dur - last_clip.end
            needed_source = delta_to_apply * last_clip.speed
            if available_source >= needed_source:
                last_clip.end = round(last_clip.end + needed_source, 3)
                last_clip.duration = round(last_clip.duration + delta_to_apply, 3)
                applied = True
                sese_metadata["strategy"] = "extend_last"
                logger.info(f"[SESE] Applied strategy: extend_last (+{delta_to_apply:.3f}s)")
        except Exception as e:
            logger.warning(f"[SESE] Failed to probe/extend last clip: {e}")

        # 2. Try to extend nearby clip (second-to-last clip) if last clip not possible
        if not applied and len(adjusted_timeline.clips) > 1:
            second_last_clip = adjusted_timeline.clips[-2]
            try:
                source_dur = probe_media_duration(second_last_clip.source_path)
                available_source = source_dur - second_last_clip.end
                needed_source = delta_to_apply * second_last_clip.speed
                if available_source >= needed_source:
                    second_last_clip.end = round(second_last_clip.end + needed_source, 3)
                    second_last_clip.duration = round(second_last_clip.duration + delta_to_apply, 3)
                    applied = True
                    sese_metadata["strategy"] = "extend_nearby"
                    logger.info(f"[SESE] Applied strategy: extend_nearby (+{delta_to_apply:.3f}s)")
            except Exception as e:
                logger.warning(f"[SESE] Failed to probe/extend nearby clip: {e}")

        # 3 & 4. Apply Freeze Zoom / Freeze
        if not applied:
            # We insert a new clip at the end
            enable_end_zoom = getattr(config.render, "enable_end_zoom", True)
            clip_type = ClipType.FREEZE_ZOOM if enable_end_zoom else ClipType.FREEZE
            
            # Extract parent metadata from last clip
            parent_clip = adjusted_timeline.clips[-1]
            
            # Safe extraction timestamp: 0.05s before the end to make sure we don't hit EOF
            extract_start = max(parent_clip.start, parent_clip.end - 0.05)
            
            freeze_clip = TimelineClip(
                segment_id=(parent_clip.segment_id + "_freeze") if parent_clip.segment_id else None,
                source_path=parent_clip.source_path,
                start=round(extract_start, 3),
                end=round(extract_start + 0.05, 3),
                duration=round(delta_to_apply, 3),
                speed=1.0,
                slot_name=parent_clip.slot_name,
                text_role=parent_clip.text_role,
                segment_score=parent_clip.segment_score,
                tags=list(parent_clip.tags),
                crop_box=parent_clip.crop_box,
                crop_mode=parent_clip.crop_mode,
                crop_safety_score=parent_clip.crop_safety_score,
                crop_warnings=list(parent_clip.crop_warnings),
                effective_zoom_motion=parent_clip.effective_zoom_motion,
                crop_cache_hit=parent_clip.crop_cache_hit,
                user_review_status=parent_clip.user_review_status,
                source_media_review_status=parent_clip.source_media_review_status,
                clip_type=clip_type
            )
            
            adjusted_timeline.clips.append(freeze_clip)
            applied = True
            sese_metadata["strategy"] = "freeze_zoom" if enable_end_zoom else "freeze"
            logger.info(f"[SESE] Applied strategy: {sese_metadata['strategy']} (+{delta_to_apply:.3f}s)")

        # Record SESE metadata
        sese_metadata["applied"] = applied
        sese_metadata["added_duration"] = round(delta_to_apply, 3)
        sese_metadata["final_duration"] = round(timeline_duration + delta_to_apply, 3)
        
        # Attach sese_metadata to the adjusted_timeline object so it can be read in the pipeline.
        # Use object.__setattr__ to bypass Pydantic extra="forbid" on Timeline.
        adjusted_timeline.target_duration = sese_metadata["final_duration"]
        object.__setattr__(adjusted_timeline, "sese_metadata", sese_metadata)

        return adjusted_timeline
