"""Utility functions for Rescored backend."""
import re
from urllib.parse import urlparse, parse_qs
import yt_dlp


def validate_youtube_url(url: str) -> tuple[bool, str | None]:
    """
    Validate YouTube URL and extract video ID.

    Args:
        url: YouTube URL to validate

    Returns:
        (is_valid, video_id or error_message)
    """
    # Supported formats:
    # - https://www.youtube.com/watch?v=VIDEO_ID
    # - https://youtu.be/VIDEO_ID
    # - https://m.youtube.com/watch?v=VIDEO_ID

    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return True, match.group(1)

    return False, "Invalid YouTube URL format"


def check_video_availability(video_id: str, max_duration: int = 900) -> dict:
    """
    Check if video is available for download.

    Args:
        video_id: YouTube video ID
        max_duration: Maximum allowed duration in seconds

    Returns:
        Dictionary with 'available' (bool) and 'reason' or 'info'
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'force_ipv4': True,  # Force IPv4 to avoid DNS issues
        'socket_timeout': 30,
        'source_address': '0.0.0.0',  # Bind to all interfaces
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f"https://youtube.com/watch?v={video_id}",
                download=False
            )

            # Check duration
            duration = info.get('duration', 0)
            if duration > max_duration:
                return {
                    'available': False,
                    'reason': f'Video too long (max {max_duration // 60} minutes)'
                }

            # Check if age-restricted
            if info.get('age_limit', 0) > 0:
                return {
                    'available': False,
                    'reason': 'Age-restricted content not supported'
                }

            return {'available': True, 'info': info}

    except yt_dlp.utils.DownloadError as e:
        return {'available': False, 'reason': str(e)}
    except Exception as e:
        return {'available': False, 'reason': f'Error checking video: {str(e)}'}
