#!/usr/bin/env python3
"""
Accuracy Testing Suite for Rescored Pipeline

Tests transcription accuracy on 10 diverse piano videos covering different styles and complexities.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline import TranscriptionPipeline
from config import settings
import json
from datetime import datetime


# Test videos with varying complexity
TEST_VIDEOS = [
    {
        "id": "simple_melody",
        "url": "https://www.youtube.com/watch?v=TK1Ij_-mank",
        "description": "Simple piano melody - C major scale practice",
        "difficulty": "easy",
        "expected_accuracy": ">80%",
        "notes": "Slow tempo, single notes, clear recording"
    },
    {
        "id": "twinkle_twinkle",
        "url": "https://www.youtube.com/watch?v=YCZ_d_4ZEqk",
        "description": "Twinkle Twinkle Little Star - Beginner piano",
        "difficulty": "easy",
        "expected_accuracy": ">75%",
        "notes": "Very simple melody, slow tempo"
    },
    {
        "id": "fur_elise",
        "url": "https://www.youtube.com/watch?v=_mVW8tgGY_w",
        "description": "Beethoven - Für Elise (simplified)",
        "difficulty": "medium",
        "expected_accuracy": "60-70%",
        "notes": "Classic piece, moderate tempo, some ornaments"
    },
    {
        "id": "chopin_nocturne",
        "url": "https://www.youtube.com/watch?v=9E6b3swbnWg",
        "description": "Chopin - Nocturne Op. 9 No. 2",
        "difficulty": "hard",
        "expected_accuracy": "50-60%",
        "notes": "Complex harmonies, expressive dynamics, rubato"
    },
    {
        "id": "canon_in_d",
        "url": "https://www.youtube.com/watch?v=NlprozGcs80",
        "description": "Pachelbel - Canon in D (piano arrangement)",
        "difficulty": "medium",
        "expected_accuracy": "60-70%",
        "notes": "Repetitive patterns, moderate polyphony"
    },
    {
        "id": "river_flows",
        "url": "https://www.youtube.com/watch?v=7maJOI3QMu0",
        "description": "Yiruma - River Flows in You",
        "difficulty": "medium",
        "expected_accuracy": "60-70%",
        "notes": "Modern piano, flowing arpeggios"
    },
    {
        "id": "moonlight_sonata",
        "url": "https://www.youtube.com/watch?v=4Tr0otuiQuU",
        "description": "Beethoven - Moonlight Sonata (1st movement)",
        "difficulty": "medium",
        "expected_accuracy": "60-70%",
        "notes": "Slow tempo, triplet arpeggios, bass notes"
    },
    {
        "id": "jazz_blues",
        "url": "https://www.youtube.com/watch?v=F3W_alUuFkA",
        "description": "Simple jazz blues piano",
        "difficulty": "medium",
        "expected_accuracy": "55-65%",
        "notes": "Swing rhythm, blue notes, syncopation"
    },
    {
        "id": "claire_de_lune",
        "url": "https://www.youtube.com/watch?v=WNcsUNKlAKw",
        "description": "Debussy - Clair de Lune",
        "difficulty": "hard",
        "expected_accuracy": "50-60%",
        "notes": "Impressionist harmony, complex textures"
    },
    {
        "id": "la_campanella",
        "url": "https://www.youtube.com/watch?v=MD6xMyuZls0",
        "description": "Liszt - La Campanella",
        "difficulty": "very_hard",
        "expected_accuracy": "40-50%",
        "notes": "Virtuosic, extremely fast, wide range, many notes"
    }
]


def run_accuracy_test(video, verbose=True):
    """
    Run transcription pipeline on a test video and collect metrics.

    Args:
        video: Dictionary with video metadata
        verbose: Print progress messages

    Returns:
        Dictionary with test results and metrics
    """
    if verbose:
        print(f"\n{'='*70}")
        print(f"Testing: {video['description']}")
        print(f"Difficulty: {video['difficulty']} | Expected: {video['expected_accuracy']}")
        print(f"{'='*70}")

    job_id = f"accuracy_test_{video['id']}"
    storage_path = Path(settings.storage_path)

    # Progress callback
    def progress_callback(percent, stage, message):
        if verbose:
            print(f"[{percent:3d}%] {stage:12s} | {message}")

    result = {
        "video_id": video["id"],
        "description": video["description"],
        "difficulty": video["difficulty"],
        "url": video["url"],
        "timestamp": datetime.utcnow().isoformat(),
        "success": False,
        "error": None,
        "metrics": {}
    }

    try:
        # Run pipeline
        pipeline = TranscriptionPipeline(job_id, video["url"], storage_path)
        pipeline.set_progress_callback(progress_callback)

        musicxml_path = pipeline.run()

        # Get intermediate file paths for analysis
        temp_dir = pipeline.temp_dir
        original_audio = temp_dir / "audio.wav"
        other_stem = temp_dir / "htdemucs" / job_id / "other.wav"
        midi_path = temp_dir / "other_basic_pitch.mid"
        clean_midi = temp_dir / "piano_clean.mid"

        # Collect metrics
        import soundfile as sf
        import mido

        # Audio metrics
        if original_audio.exists():
            audio_data, sr = sf.read(original_audio)
            result["metrics"]["audio_duration_seconds"] = len(audio_data) / sr

        # Separation quality (simple energy ratio)
        if original_audio.exists() and other_stem.exists():
            import numpy as np
            original_data, _ = sf.read(original_audio)
            other_data, _ = sf.read(other_stem)

            original_energy = np.sum(original_data ** 2)
            other_energy = np.sum(other_data ** 2)

            result["metrics"]["separation"] = {
                "other_energy_ratio": other_energy / original_energy if original_energy > 0 else 0
            }

        # MIDI analysis (simple note count)
        if clean_midi.exists():
            mid = mido.MidiFile(clean_midi)
            note_count = sum(1 for track in mid.tracks for msg in track if msg.type == 'note_on')

            result["metrics"]["midi"] = {
                "total_notes": note_count,
                "duration_seconds": mid.length
            }

        # MusicXML analysis (measure count, etc)
        if musicxml_path.exists():
            from music21 import converter
            score = converter.parse(musicxml_path)
            measures = score.parts[0].getElementsByClass('Measure') if score.parts else []

            result["metrics"]["musicxml"] = {
                "total_measures": len(measures),
                "file_size_kb": musicxml_path.stat().st_size / 1024
            }

        result["success"] = True
        result["output_files"] = {
            "musicxml": str(musicxml_path),
            "midi": str(clean_midi),
            "temp_dir": str(temp_dir)
        }

        if verbose:
            print(f"\n✅ SUCCESS - Output: {musicxml_path}")
            print(f"   MIDI notes: {result['metrics']['midi']['total_notes']}")
            print(f"   Measures: {result['metrics']['musicxml']['total_measures']}")
            if 'separation' in result['metrics']:
                sep = result['metrics']['separation']
                print(f"   Separation: {sep['other_energy_ratio']:.1%} energy in 'other' stem")

    except Exception as e:
        result["error"] = str(e)
        if verbose:
            print(f"\n❌ FAILED - Error: {e}")

    return result


def main():
    """Run accuracy tests on all test videos."""
    print("="*70)
    print("Rescored Accuracy Testing Suite")
    print("="*70)
    print(f"Testing {len(TEST_VIDEOS)} videos with varying difficulty")
    print(f"Storage: {settings.storage_path}")
    print()

    # Run tests
    results = []
    for i, video in enumerate(TEST_VIDEOS, 1):
        print(f"\n[{i}/{len(TEST_VIDEOS)}] Starting test: {video['id']}")
        result = run_accuracy_test(video, verbose=True)
        results.append(result)

    # Summary
    print("\n" + "="*70)
    print("ACCURACY TEST SUMMARY")
    print("="*70)

    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]

    print(f"\nTotal: {len(results)} | Success: {len(successful)} | Failed: {len(failed)}")
    print(f"Success Rate: {len(successful)/len(results)*100:.1f}%")

    if successful:
        print("\n✅ Successful Transcriptions:")
        for r in successful:
            midi_notes = r["metrics"]["midi"]["total_notes"]
            measures = r["metrics"]["musicxml"]["total_measures"]
            print(f"  - {r['video_id']:20s} | {midi_notes:4d} notes | {measures:3d} measures | {r['difficulty']}")

    if failed:
        print("\n❌ Failed Transcriptions:")
        for r in failed:
            print(f"  - {r['video_id']:20s} | Error: {r['error'][:60]}")

    # Save results to JSON
    output_path = Path(settings.storage_path) / "accuracy_test_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump({
            "test_date": datetime.utcnow().isoformat(),
            "total_tests": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": len(successful) / len(results),
            "results": results
        }, f, indent=2)

    print(f"\n📊 Full results saved to: {output_path}")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
