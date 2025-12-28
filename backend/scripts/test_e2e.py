#!/usr/bin/env python3
"""
End-to-end test script for the transcription pipeline.

Usage (from backend directory):
    python scripts/test_e2e.py <youtube_url>

Example:
    python scripts/test_e2e.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline import TranscriptionPipeline
from app_config import settings
import time


def progress_callback(percent: int, stage: str, message: str):
    """Print progress updates."""
    print(f"[{percent:3d}%] {stage:12s} | {message}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_e2e.py <youtube_url>")
        print("\nExample simple piano videos to test:")
        print("1. Twinkle Twinkle: https://www.youtube.com/watch?v=WyTb3DTu88c")
        print("2. Simple melody: https://www.youtube.com/watch?v=fJ9rUzIMcZQ")
        sys.exit(1)

    youtube_url = sys.argv[1]
    job_id = "test_e2e"
    storage_path = Path(settings.storage_path)

    print("=" * 60)
    print("Rescored End-to-End Pipeline Test")
    print("=" * 60)
    print(f"YouTube URL: {youtube_url}")
    print(f"Job ID: {job_id}")
    print(f"Storage: {storage_path}")
    print("=" * 60)
    print()

    # Create pipeline
    pipeline = TranscriptionPipeline(job_id, youtube_url, storage_path)
    pipeline.set_progress_callback(progress_callback)

    # Run pipeline
    try:
        start_time = time.time()
        musicxml_path = pipeline.run()
        elapsed_time = time.time() - start_time

        print()
        print("=" * 60)
        print("SUCCESS!")
        print("=" * 60)
        print(f"Total time: {elapsed_time:.1f} seconds")
        print(f"MusicXML file: {musicxml_path}")
        print(f"File size: {musicxml_path.stat().st_size / 1024:.1f} KB")
        print()

        # Show temp directory contents
        print("Intermediate files:")
        temp_dir = storage_path / "temp" / job_id
        for file in sorted(temp_dir.rglob("*")):
            if file.is_file():
                size_kb = file.stat().st_size / 1024
                rel_path = file.relative_to(temp_dir)
                print(f"  {rel_path} ({size_kb:.1f} KB)")
        print()

        # Preview MusicXML
        print("MusicXML preview (first 50 lines):")
        print("-" * 60)
        with open(musicxml_path, 'r') as f:
            for i, line in enumerate(f):
                if i >= 50:
                    print("... (truncated)")
                    break
                print(line.rstrip())
        print("-" * 60)
        print()

        print("Next steps:")
        print(f"1. Open in MuseScore: musescore {musicxml_path}")
        print(f"2. Inspect MIDI: timidity {temp_dir}/piano_clean.mid")
        print(f"3. Review temp files: ls -lh {temp_dir}")

    except Exception as e:
        print()
        print("=" * 60)
        print("FAILED!")
        print("=" * 60)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
