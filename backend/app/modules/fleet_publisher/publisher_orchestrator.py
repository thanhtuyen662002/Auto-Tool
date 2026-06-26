from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Any

from app.database import get_connection
from app.modules.fleet_publisher.ai_content_generator import suggest_content_for_video
from app.modules.fleet_publisher.meta_publisher import publish_to_meta
from app.modules.fleet_publisher.tiktok_publisher import publish_to_tiktok
from app.modules.fleet_publisher.youtube_publisher import publish_to_youtube

logger = logging.getLogger(__name__)


class PublisherOrchestrator:
    _instance: PublisherOrchestrator | None = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._worker_lock = threading.Lock()

    def start(self) -> None:
        """Starts the background publisher thread if not already running."""
        with self._worker_lock:
            if self._thread and self._thread.is_alive():
                logger.info("PublisherOrchestrator background thread already running.")
                return

            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                name="PublisherOrchestratorThread",
                daemon=True
            )
            self._thread.start()
            logger.info("PublisherOrchestrator background thread started.")

    def stop(self) -> None:
        """Stops the background publisher thread."""
        with self._worker_lock:
            if not self._thread or not self._thread.is_alive():
                return
            
            logger.info("Stopping PublisherOrchestrator background thread...")
            self._stop_event.set()
            self._thread.join(timeout=5)
            logger.info("PublisherOrchestrator background thread stopped.")

    def _run_loop(self) -> None:
        """Main loop that runs in the background thread."""
        logger.info("PublisherOrchestrator thread loop started.")
        # Check every 60 seconds (or 5 minutes, 60s is better for testing and timely scheduling)
        while not self._stop_event.wait(60):
            try:
                self.process_pending_queue()
            except Exception as e:
                logger.error("Lỗi trong vòng lặp PublisherOrchestrator: %s", str(e), exc_info=True)

    def process_pending_queue(self) -> None:
        """Queries the SQLite database for pending videos that are scheduled for now

        or in the past, and publishes them.
        """
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with get_connection() as conn:
            # Fetch pending items where scheduled_time <= current time
            rows = conn.execute(
                """
                SELECT q.*, c.channel_name, c.platform, c.auth_data
                FROM publishing_queue q
                JOIN distribution_channels c ON q.channel_id = c.id
                WHERE q.status = 'pending' AND q.scheduled_time <= ?
                ORDER BY q.scheduled_time ASC
                """,
                (now_str,),
            ).fetchall()

        if not rows:
            return

        logger.info("Phát hiện %d tác vụ đăng bài đến giờ xuất bản.", len(rows))

        for row in rows:
            if self._stop_event.is_set():
                break

            item_id = row["id"]
            channel_id = row["channel_id"]
            platform = row["platform"]
            channel_name = row["channel_name"]
            video_path = row["video_path"]
            title = row["title"]
            caption = row["caption"]
            hashtags = row["hashtags"]
            product_link = row["product_link"]
            
            try:
                auth_data = json.loads(row["auth_data"])
            except Exception:
                auth_data = {}

            # Update status to 'publishing'
            self._update_queue_status(item_id, "publishing")
            logger.info(
                "Đang đăng tải video [%s] lên kênh %s (%s)...",
                title,
                channel_name,
                platform.upper()
            )

            # Implement 'Notify & Continue' error handling policy
            try:
                if platform == "youtube":
                    publish_to_youtube(
                        video_path=video_path,
                        title=title,
                        caption=caption,
                        hashtags=hashtags,
                        product_link=product_link,
                        auth_data=auth_data,
                    )
                elif platform == "meta":
                    publish_to_meta(
                        video_path=video_path,
                        title=title,
                        caption=caption,
                        hashtags=hashtags,
                        product_link=product_link,
                        auth_data=auth_data,
                    )
                elif platform == "tiktok":
                    publish_to_tiktok(
                        video_path=video_path,
                        title=title,
                        caption=caption,
                        hashtags=hashtags,
                        product_link=product_link,
                        auth_data=auth_data,
                    )
                else:
                    raise ValueError(f"Nền tảng '{platform}' không được hỗ trợ.")

                # On success, update status to 'success'
                self._update_queue_status(item_id, "success")
                logger.info("Đăng tải thành công video ID: %s lên kênh %s", item_id, channel_name)

            except Exception as publish_err:
                error_msg = str(publish_err)
                logger.error(
                    "Đăng tải thất bại video ID %s lên kênh %s: %s",
                    item_id,
                    channel_name,
                    error_msg,
                    exc_info=True
                )
                # On error, update status to 'failed' and save error message, then CONTINUE to next items
                self._update_queue_status(item_id, "failed", error_msg)

    def _update_queue_status(self, item_id: str, status: str, error_message: str | None = None) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE publishing_queue 
                SET status = ?, error_message = ?
                WHERE id = ?
                """,
                (status, error_message, item_id),
            )

    def generate_schedule_for_folder(
        self,
        folder_path: str,
        channel_ids: list[str],
        tags: list[str] | None = None,
    ) -> list[str]:
        """Scans a folder for MP4 videos and schedules them automatically across the

        specified channels into their future golden time slots.
        """
        if not os.path.isdir(folder_path):
            raise ValueError(f"Đường dẫn thư mục không hợp lệ: {folder_path}")

        # Find all MP4 videos
        videos = [
            os.path.join(folder_path, f)
            for f in os.listdir(folder_path)
            if f.lower().endswith(".mp4")
        ]
        
        if not videos:
            logger.warning("Không tìm thấy tệp video .mp4 nào trong thư mục: %s", folder_path)
            return []

        # Sort videos to maintain sequential posting (FIFO)
        videos.sort()
        logger.info("Tìm thấy %d video để lập lịch tự động cho %d kênh.", len(videos), len(channel_ids))

        created_ids = []

        with get_connection() as conn:
            # Fetch channel details and their time slots
            channels_data = []
            for cid in channel_ids:
                chan = conn.execute("SELECT * FROM distribution_channels WHERE id = ?", (cid,)).fetchone()
                if not chan:
                    continue
                slots = conn.execute(
                    "SELECT posting_time FROM channel_time_slots WHERE channel_id = ? AND active = 1 ORDER BY posting_time ASC",
                    (cid,),
                ).fetchall()
                
                channels_data.append({
                    "id": cid,
                    "platform": chan["platform"],
                    "channel_name": chan["channel_name"],
                    "daily_limit": chan["daily_limit"],
                    "time_slots": [s["posting_time"] for s in slots]
                })

        if not channels_data:
            raise ValueError("Không tìm thấy thông tin kênh hoặc cấu hình khung giờ cho các kênh được chọn.")

        now = datetime.now()

        for cid_data in channels_data:
            cid = cid_data["id"]
            slots = cid_data["time_slots"]
            daily_limit = cid_data["daily_limit"]

            if not slots:
                # Fallback: if no slots configured, use default golden times
                slots = ["11:30", "18:00", "20:30"]

            # Query the database for the last scheduled video for this channel
            # to know where to append new schedule items
            with get_connection() as conn:
                last_row = conn.execute(
                    """
                    SELECT scheduled_time FROM publishing_queue
                    WHERE channel_id = ? AND status IN ('pending', 'publishing', 'success')
                    ORDER BY scheduled_time DESC LIMIT 1
                    """,
                    (cid,),
                ).fetchone()

            if last_row:
                last_time = datetime.strptime(last_row["scheduled_time"], "%Y-%m-%d %H:%M:%S")
                # Ensure we start scheduling after the last scheduled time
                start_from = max(now + timedelta(minutes=15), last_time)
            else:
                start_from = now + timedelta(minutes=15)

            current_schedule_time = start_from

            for video_path in videos:
                # Generate AI Title, Caption, Hashtags, and Product Link mapping
                title, caption, hashtags, product_link = suggest_content_for_video(video_path, tags)

                # Calculate the next posting slot
                scheduled_dt = self._calculate_next_slot(current_schedule_time, slots, daily_limit, cid)
                scheduled_time_str = scheduled_dt.strftime("%Y-%m-%d %H:%M:%S")
                
                # Advance current schedule pointer to avoid double booking
                current_schedule_time = scheduled_dt + timedelta(minutes=1)

                # Insert into publishing queue
                queue_id = str(uuid.uuid4())
                with get_connection() as conn:
                    conn.execute(
                        """
                        INSERT INTO publishing_queue 
                        (id, channel_id, video_path, title, caption, hashtags, product_link, scheduled_time, status, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            queue_id,
                            cid,
                            video_path,
                            title,
                            caption,
                            hashtags,
                            product_link,
                            scheduled_time_str,
                            "pending",
                            now.strftime("%Y-%m-%d %H:%M:%S")
                        ),
                    )
                created_ids.append(queue_id)
                logger.info(
                    "Đã lập lịch video [%s] -> Kênh [%s] lúc %s",
                    title,
                    cid_data["channel_name"],
                    scheduled_time_str
                )

        return created_ids

    def _calculate_next_slot(
        self,
        start_dt: datetime,
        time_slots: list[str],
        daily_limit: int,
        channel_id: str,
    ) -> datetime:
        """Finds the next available time slot for a channel, respecting its daily limit

        and specific time slots.
        """
        # Parse time slots as timedelta from midnight
        slot_times = []
        for slot in time_slots:
            h, m = map(int, slot.split(":"))
            slot_times.append(timedelta(hours=h, minutes=m))

        slot_times.sort()

        test_day = start_dt.date()
        
        while True:
            # Check how many videos are already scheduled for test_day
            day_start = datetime.combine(test_day, datetime.min.time()).strftime("%Y-%m-%d %H:%M:%S")
            day_end = datetime.combine(test_day, datetime.max.time()).strftime("%Y-%m-%d %H:%M:%S")
            
            with get_connection() as conn:
                count = conn.execute(
                    """
                    SELECT COUNT(*) FROM publishing_queue
                    WHERE channel_id = ? AND scheduled_time >= ? AND scheduled_time <= ?
                    AND status IN ('pending', 'publishing', 'success')
                    """,
                    (channel_id, day_start, day_end),
                ).fetchone()[0]

            if count < daily_limit:
                # We can schedule on this day. Find the next slot on this day that is in the future
                for slot_td in slot_times:
                    slot_dt = datetime.combine(test_day, datetime.min.time()) + slot_td
                    if slot_dt > start_dt:
                        # Double check if this exact slot time is already taken (avoid collisions)
                        slot_str = slot_dt.strftime("%Y-%m-%d %H:%M:%S")
                        with get_connection() as conn:
                            exists = conn.execute(
                                "SELECT 1 FROM publishing_queue WHERE channel_id = ? AND scheduled_time = ? AND status != 'failed'",
                                (channel_id, slot_str),
                            ).fetchone()
                        if not exists:
                            return slot_dt

            # If daily limit exceeded or no future slots available on this day, advance to the next day
            test_day += timedelta(days=1)
            # Reset start_dt to midnight of the new day so we can pick its first slot
            start_dt = datetime.combine(test_day, datetime.min.time())
