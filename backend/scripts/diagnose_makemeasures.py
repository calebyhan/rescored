#!/usr/bin/env python3
"""
Diagnostic script to analyze what music21's makeMeasures() does to notes.

Purpose: Understand how makeMeasures() transforms note durations and timing.

Usage:
    python diagnose_makemeasures.py <midi_file> [--time-sig 4/4]
"""

import argparse
from pathlib import Path
from typing import List, Dict, Any
from music21 import converter, note, chord, meter


def extract_note_data(element) -> List[Dict[str, Any]]:
    """Extract note data from a note or chord element."""
    notes = []

    if isinstance(element, note.Note):
        notes.append({
            'pitch': element.pitch.midi,
            'pitch_name': element.pitch.nameWithOctave,
            'offset': float(element.offset),
            'duration': float(element.quarterLength),
            'type': 'note'
        })
    elif isinstance(element, chord.Chord):
        for pitch in element.pitches:
            notes.append({
                'pitch': pitch.midi,
                'pitch_name': pitch.nameWithOctave,
                'offset': float(element.offset),
                'duration': float(element.quarterLength),
                'type': 'chord'
            })
    elif isinstance(element, note.Rest):
        notes.append({
            'pitch': None,
            'pitch_name': 'Rest',
            'offset': float(element.offset),
            'duration': float(element.quarterLength),
            'type': 'rest'
        })

    return notes


def dump_score_notes(score, label: str) -> List[Dict[str, Any]]:
    """Dump all notes from score with optional label."""
    notes_list = []

    for element in score.flatten().notesAndRests:
        notes_list.extend(extract_note_data(element))

    return sorted(notes_list, key=lambda x: (x['offset'], x['pitch'] if x['pitch'] is not None else -1))


def analyze_makemeasures_changes(before_notes: List[Dict[str, Any]],
                                 after_notes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze what changed between before and after makeMeasures().

    Returns:
    - note_count_change: Difference in note count
    - duration_changes: Notes whose durations changed
    - timing_changes: Notes whose offsets changed
    - new_rests: Rests that were inserted
    - split_notes: Notes that were split into multiple notes
    """
    report = {
        'before_count': len(before_notes),
        'after_count': len(after_notes),
        'note_count_change': len(after_notes) - len(before_notes),
        'duration_changes': [],
        'timing_changes': [],
        'new_rests': [],
        'split_notes': [],
        'impossible_durations': []
    }

    # Count rests
    before_rests = [n for n in before_notes if n['type'] == 'rest']
    after_rests = [n for n in after_notes if n['type'] == 'rest']

    report['new_rests'] = [r for r in after_rests if r not in before_rests]

    # Find impossible durations (< 64th note = 0.0625 quarter notes)
    MIN_DURATION = 0.0625
    for note_data in after_notes:
        if note_data['duration'] < MIN_DURATION:
            report['impossible_durations'].append({
                'note': note_data['pitch_name'],
                'offset': note_data['offset'],
                'duration': note_data['duration'],
                'type': note_data['type']
            })

    # Try to match before/after notes
    after_matched = [False] * len(after_notes)

    for before_note in before_notes:
        if before_note['type'] == 'rest':
            continue  # Skip rests for now

        # Find matching note(s) in after_notes
        matches = []
        for i, after_note in enumerate(after_notes):
            if after_matched[i]:
                continue
            if after_note['pitch'] == before_note['pitch']:
                # Check if timing is close (within 0.1 quarter notes)
                timing_diff = abs(after_note['offset'] - before_note['offset'])
                if timing_diff < 0.1:
                    matches.append((i, after_note, timing_diff))

        if len(matches) == 0:
            # Note disappeared?
            report['duration_changes'].append({
                'before': before_note,
                'after': None,
                'change': 'disappeared'
            })
        elif len(matches) == 1:
            # One-to-one match
            idx, after_note, _ = matches[0]
            after_matched[idx] = True

            # Check for duration change
            duration_diff = abs(after_note['duration'] - before_note['duration'])
            if duration_diff > 0.001:
                report['duration_changes'].append({
                    'note': before_note['pitch_name'],
                    'before_duration': before_note['duration'],
                    'after_duration': after_note['duration'],
                    'difference': after_note['duration'] - before_note['duration'],
                    'offset': before_note['offset']
                })

            # Check for timing change
            timing_diff = abs(after_note['offset'] - before_note['offset'])
            if timing_diff > 0.001:
                report['timing_changes'].append({
                    'note': before_note['pitch_name'],
                    'before_offset': before_note['offset'],
                    'after_offset': after_note['offset'],
                    'difference': after_note['offset'] - before_note['offset']
                })
        else:
            # Multiple matches - note was split
            for idx, after_note, _ in matches:
                after_matched[idx] = True

            total_after_duration = sum(m[1]['duration'] for m in matches)
            report['split_notes'].append({
                'note': before_note['pitch_name'],
                'before_duration': before_note['duration'],
                'after_count': len(matches),
                'after_total_duration': total_after_duration,
                'after_notes': [m[1] for m in matches]
            })

    return report


def print_forensics_report(report: Dict[str, Any]):
    """Print forensics report in human-readable format."""
    print("\n" + "="*80)
    print("music21 makeMeasures() FORENSICS REPORT")
    print("="*80)

    print(f"\n📊 NOTE COUNT:")
    print(f"  Before makeMeasures(): {report['before_count']}")
    print(f"  After makeMeasures():  {report['after_count']}")
    print(f"  Change:                {report['note_count_change']:+d}")

    if report['new_rests']:
        print(f"\n🎵 NEW RESTS INSERTED: {len(report['new_rests'])}")
        for i, rest in enumerate(report['new_rests'][:10]):
            print(f"  {i+1}. Rest at offset {rest['offset']:.4f}, duration {rest['duration']:.4f}")

    if report['impossible_durations']:
        print(f"\n⚠️  IMPOSSIBLE DURATIONS CREATED: {len(report['impossible_durations'])}")
        print(f"   (notes shorter than 64th note = 0.0625 quarter notes)")
        for i, note_data in enumerate(report['impossible_durations'][:10]):
            print(f"  {i+1}. {note_data['note']} at {note_data['offset']:.4f}, duration {note_data['duration']:.6f}")

    if report['duration_changes']:
        print(f"\n⏱️  DURATION CHANGES: {len(report['duration_changes'])}")
        for i, change in enumerate(report['duration_changes'][:10]):
            if change.get('change') == 'disappeared':
                print(f"  {i+1}. {change['before']['pitch_name']} DISAPPEARED")
                print(f"      Before: offset {change['before']['offset']:.4f}, duration {change['before']['duration']:.4f}")
            else:
                print(f"  {i+1}. {change['note']} at offset {change['offset']:.4f}")
                print(f"      Before: {change['before_duration']:.4f}  →  After: {change['after_duration']:.4f}")
                print(f"      Difference: {change['difference']:+.4f}")

    if report['timing_changes']:
        print(f"\n📍 TIMING CHANGES: {len(report['timing_changes'])}")
        for i, change in enumerate(report['timing_changes'][:10]):
            print(f"  {i+1}. {change['note']}")
            print(f"      Before: {change['before_offset']:.4f}  →  After: {change['after_offset']:.4f}")
            print(f"      Difference: {change['difference']:+.4f}")

    if report['split_notes']:
        print(f"\n✂️  NOTES SPLIT: {len(report['split_notes'])}")
        for i, split in enumerate(report['split_notes'][:5]):
            print(f"  {i+1}. {split['note']} (duration {split['before_duration']:.4f}) split into {split['after_count']} notes:")
            for j, after_note in enumerate(split['after_notes']):
                print(f"      {j+1}. Offset {after_note['offset']:.4f}, duration {after_note['duration']:.4f}")

    print("\n" + "="*80)


def main():
    parser = argparse.ArgumentParser(
        description='Analyze what music21.makeMeasures() does to notes'
    )
    parser.add_argument('midi_file', type=Path, help='Path to MIDI file')
    parser.add_argument('--time-sig', '-t', type=str, default='4/4',
                       help='Time signature to use (default: 4/4)')

    args = parser.parse_args()

    if not args.midi_file.exists():
        print(f"ERROR: MIDI file not found: {args.midi_file}")
        return 1

    print(f"🔬 Analyzing makeMeasures() behavior...")
    print(f"   MIDI file: {args.midi_file}")
    print(f"   Time signature: {args.time_sig}")

    # Parse MIDI
    print(f"\n📝 Loading MIDI file...")
    score = converter.parse(args.midi_file)

    # Dump notes BEFORE makeMeasures
    print(f"📝 Extracting notes BEFORE makeMeasures()...")
    before_notes = dump_score_notes(score, "BEFORE")

    # Apply makeMeasures
    print(f"🔧 Calling makeMeasures()...")
    time_sig_parts = args.time_sig.split('/')
    time_sig = meter.TimeSignature(args.time_sig)

    score_with_measures = score.makeMeasures()

    # Dump notes AFTER makeMeasures
    print(f"📝 Extracting notes AFTER makeMeasures()...")
    after_notes = dump_score_notes(score_with_measures, "AFTER")

    # Analyze changes
    print(f"🔬 Analyzing changes...")
    report = analyze_makemeasures_changes(before_notes, after_notes)

    # Print report
    print_forensics_report(report)

    return 0


if __name__ == '__main__':
    exit(main())
