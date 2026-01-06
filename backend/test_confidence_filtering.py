"""
Test script for Phase 1.1: Enhanced Confidence Filtering

This script verifies that ByteDance frame-level confidence scores are properly
extracted and used in ensemble voting.

Expected improvements:
- ByteDance notes with low confidence (< 0.3) should be downweighted
- Ensemble should filter out false positives more effectively
- Overall F1 score should improve by 1-2%
"""

import numpy as np
from pathlib import Path
from backend.bytedance_wrapper import ByteDanceTranscriber
from backend.ensemble_transcriber import Note, EnsembleTranscriber


def test_confidence_extraction():
    """Test that ByteDance confidence extraction works correctly."""
    print("\n=== Testing ByteDance Confidence Extraction ===\n")

    # Create mock data for testing
    import pretty_midi

    # Create simple test MIDI
    pm = pretty_midi.PrettyMIDI()
    instrument = pretty_midi.Instrument(program=0)

    # Add a few test notes
    test_notes = [
        (60, 0.0, 0.5, 80),  # Middle C, 0-0.5s
        (64, 0.5, 1.0, 70),  # E, 0.5-1.0s
        (67, 1.0, 1.5, 60),  # G, 1.0-1.5s
    ]

    for pitch, start, end, velocity in test_notes:
        note = pretty_midi.Note(
            velocity=velocity,
            pitch=pitch,
            start=start,
            end=end
        )
        instrument.notes.append(note)

    pm.instruments.append(instrument)

    # Create mock onset/offset rolls (frames, 88)
    # 100 FPS for 2 seconds = 200 frames
    n_frames = 200
    onset_roll = np.zeros((n_frames, 88))
    offset_roll = np.zeros((n_frames, 88))

    # Add confidence scores for test notes
    # Note 1: High confidence (0.9)
    onset_roll[0:5, 60-21] = 0.9  # Middle C onset
    offset_roll[48:53, 60-21] = 0.9  # Middle C offset

    # Note 2: Medium confidence (0.6)
    onset_roll[48:53, 64-21] = 0.6  # E onset
    offset_roll[98:103, 64-21] = 0.6  # E offset

    # Note 3: Low confidence (0.3)
    onset_roll[98:103, 67-21] = 0.3  # G onset
    offset_roll[148:153, 67-21] = 0.3  # G offset

    # Test extraction
    transcriber = ByteDanceTranscriber.__new__(ByteDanceTranscriber)
    note_confidences = transcriber._extract_note_confidences_from_rolls(
        pm, onset_roll, offset_roll
    )

    print(f"Extracted {len(note_confidences)} notes with confidence scores:\n")

    for i, note_conf in enumerate(note_confidences):
        print(f"Note {i+1}: Pitch={note_conf['pitch']}, "
              f"Onset={note_conf['onset']:.1f}s, "
              f"Offset={note_conf['offset']:.1f}s")
        print(f"  Onset conf: {note_conf['onset_confidence']:.3f}, "
              f"Offset conf: {note_conf['offset_confidence']:.3f}")
        print(f"  Combined: {note_conf['confidence']:.3f} (geometric mean)\n")

    # Verify confidence values
    assert len(note_confidences) == 3, "Should extract 3 notes"

    # Note 1: High confidence
    assert note_confidences[0]['confidence'] > 0.85, \
        f"High confidence note should have confidence > 0.85, got {note_confidences[0]['confidence']}"

    # Note 2: Medium confidence
    assert 0.55 < note_confidences[1]['confidence'] < 0.65, \
        f"Medium confidence note should be ~0.6, got {note_confidences[1]['confidence']}"

    # Note 3: Low confidence
    assert note_confidences[2]['confidence'] < 0.35, \
        f"Low confidence note should have confidence < 0.35, got {note_confidences[2]['confidence']}"

    print("✓ Confidence extraction test passed!\n")


def test_weighted_voting_with_confidence():
    """Test that weighted voting properly uses confidence scores."""
    print("\n=== Testing Weighted Voting with Confidence ===\n")

    # Create mock notes from two models
    # YourMT3+ notes (confidence = 1.0, weight = 0.4)
    yourmt3_notes = [
        Note(pitch=60, onset=0.0, offset=0.5, velocity=80, confidence=1.0),
        Note(pitch=64, onset=0.5, offset=1.0, velocity=70, confidence=1.0),
        Note(pitch=67, onset=1.0, offset=1.5, velocity=60, confidence=1.0),
    ]

    # ByteDance notes (varying confidence, weight = 0.6)
    bytedance_notes = [
        Note(pitch=60, onset=0.0, offset=0.5, velocity=82, confidence=0.9),  # High confidence
        Note(pitch=64, onset=0.5, offset=1.0, velocity=68, confidence=0.6),  # Medium confidence
        Note(pitch=67, onset=1.0, offset=1.5, velocity=62, confidence=0.2),  # Low confidence - should be filtered
    ]

    # Create mock ensemble transcriber
    from backend.yourmt3_wrapper import YourMT3Transcriber
    from backend.bytedance_wrapper import ByteDanceTranscriber

    ensemble = EnsembleTranscriber(
        yourmt3_transcriber=None,
        bytedance_transcriber=None,
        voting_strategy='weighted',
        onset_tolerance_ms=50,
        confidence_threshold=0.6,
        use_bytedance_confidence=True
    )

    # Test weighted voting
    merged_notes = ensemble._vote_weighted(
        [yourmt3_notes, bytedance_notes],
        ['YourMT3+', 'ByteDance']
    )

    print(f"Input: {len(yourmt3_notes)} YourMT3+ notes + {len(bytedance_notes)} ByteDance notes")
    print(f"Output: {len(merged_notes)} merged notes\n")

    for i, note in enumerate(merged_notes):
        print(f"Note {i+1}: Pitch={note.pitch}, "
              f"Onset={note.onset:.2f}s, "
              f"Confidence={note.confidence:.3f}")

    # Verify results
    # Note 1: YourMT3+ (0.4) + ByteDance high conf (0.6 × 0.9 = 0.54) = 0.94 → KEEP
    assert merged_notes[0].pitch == 60
    assert merged_notes[0].confidence > 0.9, \
        f"Note 1 should have high confidence, got {merged_notes[0].confidence}"

    # Note 2: YourMT3+ (0.4) + ByteDance med conf (0.6 × 0.6 = 0.36) = 0.76 → KEEP
    assert merged_notes[1].pitch == 64
    assert 0.7 < merged_notes[1].confidence < 0.8, \
        f"Note 2 should have medium-high confidence, got {merged_notes[1].confidence}"

    # Note 3: YourMT3+ (0.4) + ByteDance low conf (0.6 × 0.2 = 0.12) = 0.52 → FILTERED (< 0.6 threshold)
    # Should only have 2 notes in output
    assert len(merged_notes) == 2, \
        f"Low confidence note should be filtered, got {len(merged_notes)} notes instead of 2"

    print(f"\n✓ Weighted voting test passed!")
    print(f"  - High confidence notes: KEPT (0.94)")
    print(f"  - Medium confidence notes: KEPT (0.76)")
    print(f"  - Low confidence notes: FILTERED (0.52 < 0.6 threshold)\n")


def test_confidence_impact_summary():
    """Show the impact of confidence filtering."""
    print("\n=== Confidence Filtering Impact Summary ===\n")

    print("Before (fixed weights):")
    print("  YourMT3+: 0.4 (all notes)")
    print("  ByteDance: 0.6 (all notes)")
    print("  → False positives from ByteDance get full 0.6 weight\n")

    print("After (confidence-weighted):")
    print("  YourMT3+: 0.4 × 1.0 = 0.4 (no confidence available)")
    print("  ByteDance: 0.6 × confidence (from onset_roll/offset_roll)")
    print("    - High confidence (0.9): 0.6 × 0.9 = 0.54")
    print("    - Medium confidence (0.6): 0.6 × 0.6 = 0.36")
    print("    - Low confidence (0.3): 0.6 × 0.3 = 0.18")
    print("  → Low confidence notes get downweighted and filtered!\n")

    print("Expected improvement:")
    print("  - False positive reduction: 10-20%")
    print("  - F1 score improvement: +1-2%")
    print("  - Precision improvement: +2-3%\n")


if __name__ == "__main__":
    print("=" * 60)
    print("Phase 1.1: Enhanced Confidence Filtering - Test Suite")
    print("=" * 60)

    try:
        test_confidence_extraction()
        test_weighted_voting_with_confidence()
        test_confidence_impact_summary()

        print("=" * 60)
        print("✓ ALL TESTS PASSED!")
        print("=" * 60)
        print("\nEnhanced confidence filtering is working correctly.")
        print("Ready to test on real audio files.\n")

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}\n")
        raise
    except Exception as e:
        print(f"\n✗ ERROR: {e}\n")
        raise
