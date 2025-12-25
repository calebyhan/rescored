"""Unit tests for audio processing pipeline - simplified version."""
import pytest
from pathlib import Path


class TestPipelineImports:
    """Test that pipeline functions can be imported and are callable."""

    def test_download_audio_callable(self):
        """Test download_audio is callable."""
        from pipeline import download_audio
        assert callable(download_audio)

    def test_separate_sources_callable(self):
        """Test separate_sources is callable."""
        from pipeline import separate_sources
        assert callable(separate_sources)

    def test_transcribe_audio_callable(self):
        """Test transcribe_audio is callable."""
        from pipeline import transcribe_audio
        assert callable(transcribe_audio)

    def test_quantize_midi_callable(self):
        """Test quantize_midi is callable."""
        from pipeline import quantize_midi
        assert callable(quantize_midi)

    def test_remove_duplicate_notes_callable(self):
        """Test remove_duplicate_notes is callable."""
        from pipeline import remove_duplicate_notes
        assert callable(remove_duplicate_notes)

    def test_remove_short_notes_callable(self):
        """Test remove_short_notes is callable."""
        from pipeline import remove_short_notes
        assert callable(remove_short_notes)

    def test_generate_musicxml_callable(self):
        """Test generate_musicxml is callable."""
        from pipeline import generate_musicxml
        assert callable(generate_musicxml)

    def test_detect_key_signature_callable(self):
        """Test detect_key_signature is callable."""
        from pipeline import detect_key_signature
        assert callable(detect_key_signature)

    def test_detect_time_signature_callable(self):
        """Test detect_time_signature is callable."""
        from pipeline import detect_time_signature
        assert callable(detect_time_signature)

    def test_detect_tempo_callable(self):
        """Test detect_tempo is callable."""
        from pipeline import detect_tempo
        assert callable(detect_tempo)

    def test_run_transcription_pipeline_callable(self):
        """Test run_transcription_pipeline is callable."""
        from pipeline import run_transcription_pipeline
        assert callable(run_transcription_pipeline)


class TestTranscriptionPipelineClass:
    """Test TranscriptionPipeline class."""

    def test_pipeline_class_exists(self):
        """Test TranscriptionPipeline class can be instantiated."""
        from pipeline import TranscriptionPipeline
        
        pipeline = TranscriptionPipeline("test_job", "http://example.com", Path("/tmp"))
        assert pipeline.job_id == "test_job"
        assert pipeline.youtube_url == "http://example.com"
        assert isinstance(pipeline.storage_path, Path)

    def test_pipeline_has_progress_callback(self):
        """Test TranscriptionPipeline has progress_callback."""
        from pipeline import TranscriptionPipeline
        
        pipeline = TranscriptionPipeline("test_job", "http://example.com", Path("/tmp"))
        assert hasattr(pipeline, 'set_progress_callback')
        assert callable(pipeline.set_progress_callback)

    def test_pipeline_has_required_methods(self):
        """Test TranscriptionPipeline has all required methods."""
        from pipeline import TranscriptionPipeline
        
        pipeline = TranscriptionPipeline("test_job", "http://example.com", Path("/tmp"))
        
        required_methods = [
            'download_audio',
            'separate_sources',
            'transcribe_to_midi',
            'clean_midi',
            'generate_musicxml',
            'cleanup'
        ]
        
        for method in required_methods:
            assert hasattr(pipeline, method)
            assert callable(getattr(pipeline, method))
