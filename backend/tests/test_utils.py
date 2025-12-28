"""Unit tests for utility functions."""
import pytest
from app_utils import validate_youtube_url, check_video_availability
from unittest.mock import patch, MagicMock
import yt_dlp


class TestValidateYouTubeURL:
    """Test YouTube URL validation."""

    def test_valid_watch_url(self):
        """Test standard youtube.com/watch URL."""
        is_valid, video_id = validate_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert is_valid is True
        assert video_id == "dQw4w9WgXcQ"

    def test_valid_short_url(self):
        """Test youtu.be short URL."""
        is_valid, video_id = validate_youtube_url("https://youtu.be/dQw4w9WgXcQ")
        assert is_valid is True
        assert video_id == "dQw4w9WgXcQ"

    def test_valid_mobile_url(self):
        """Test mobile YouTube URL."""
        is_valid, video_id = validate_youtube_url("https://m.youtube.com/watch?v=dQw4w9WgXcQ")
        assert is_valid is True
        assert video_id == "dQw4w9WgXcQ"

    def test_valid_embed_url(self):
        """Test embedded YouTube URL."""
        is_valid, video_id = validate_youtube_url("https://www.youtube.com/embed/dQw4w9WgXcQ")
        assert is_valid is True
        assert video_id == "dQw4w9WgXcQ"

    def test_valid_with_extra_params(self):
        """Test URL with additional query parameters."""
        is_valid, video_id = validate_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30s")
        assert is_valid is True
        assert video_id == "dQw4w9WgXcQ"

    def test_invalid_domain(self):
        """Test URL from wrong domain."""
        is_valid, error = validate_youtube_url("https://vimeo.com/12345")
        assert is_valid is False
        assert error == "Invalid YouTube URL format"

    def test_invalid_format(self):
        """Test malformed URL."""
        is_valid, error = validate_youtube_url("not-a-url")
        assert is_valid is False
        assert error == "Invalid YouTube URL format"

    def test_invalid_video_id_length(self):
        """Test URL with incorrect video ID length."""
        is_valid, error = validate_youtube_url("https://www.youtube.com/watch?v=short")
        assert is_valid is False
        assert error == "Invalid YouTube URL format"

    def test_empty_url(self):
        """Test empty URL."""
        is_valid, error = validate_youtube_url("")
        assert is_valid is False
        assert error == "Invalid YouTube URL format"


class TestCheckVideoAvailability:
    """Test video availability checking."""

    @patch('yt_dlp.YoutubeDL')
    def test_available_video(self, mock_ydl_class, mock_yt_dlp_info):
        """Test checking available video."""
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = mock_yt_dlp_info
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        result = check_video_availability("dQw4w9WgXcQ")

        assert result['available'] is True
        assert 'info' in result

    @patch('yt_dlp.YoutubeDL')
    def test_video_too_long(self, mock_ydl_class):
        """Test video exceeding duration limit."""
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = {
            'duration': 1200,  # 20 minutes
            'age_limit': 0
        }
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        result = check_video_availability("dQw4w9WgXcQ", max_duration=900)

        assert result['available'] is False
        assert 'max 15 minutes' in result['reason']

    @patch('yt_dlp.YoutubeDL')
    def test_age_restricted_video(self, mock_ydl_class):
        """Test age-restricted video."""
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = {
            'duration': 180,
            'age_limit': 18
        }
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        result = check_video_availability("dQw4w9WgXcQ")

        assert result['available'] is False
        assert 'Age-restricted' in result['reason']

    @patch('yt_dlp.YoutubeDL')
    def test_download_error(self, mock_ydl_class):
        """Test yt-dlp download error."""
        mock_ydl = MagicMock()
        mock_ydl.extract_info.side_effect = yt_dlp.utils.DownloadError("Video unavailable")
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        result = check_video_availability("invalid_id")

        assert result['available'] is False
        assert 'Video unavailable' in result['reason']

    @patch('yt_dlp.YoutubeDL')
    def test_generic_error(self, mock_ydl_class):
        """Test generic error handling."""
        mock_ydl = MagicMock()
        mock_ydl.extract_info.side_effect = Exception("Unknown error")
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        result = check_video_availability("dQw4w9WgXcQ")

        assert result['available'] is False
        assert 'Error checking video' in result['reason']

    @patch('yt_dlp.YoutubeDL')
    def test_video_at_max_duration(self, mock_ydl_class):
        """Test video exactly at duration limit."""
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = {
            'duration': 900,  # Exactly 15 minutes
            'age_limit': 0
        }
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        result = check_video_availability("dQw4w9WgXcQ", max_duration=900)

        assert result['available'] is True
