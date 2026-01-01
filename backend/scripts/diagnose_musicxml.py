#!/usr/bin/env python3
"""
Diagnostic script to compare MIDI with generated MusicXML.

Purpose: Identify where note data is lost or corrupted during MIDI → MusicXML conversion.

Usage:
    python diagnose_musicxml.py <midi_file> <musicxml_file> [--output report.json]
"""

import argparse
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple
from music21 import converter, note, chord


def extract_notes_from_midi(midi_path: Path) -> List[Dict[str, Any]]:
    """
    Extract all notes from MIDI file.

    Returns list of note dictionaries with:
    - pitch: MIDI note number (0-127)
    - start: Start time in quarter notes
    - duration: Duration in quarter notes
    - velocity: MIDI velocity (0-127)
    """
    score = converter.parse(midi_path)
    notes_list = []

    for element in score.flatten().notesAndRests:
        if isinstance(element, note.Note):
            notes_list.append({
                'pitch': element.pitch.midi,
                'pitch_name': element.pitch.nameWithOctave,
                'start': float(element.offset),
                'duration': float(element.quarterLength),
                'velocity': element.volume.velocity if element.volume.velocity else 64,
                'is_rest': False
            })
        elif isinstance(element, chord.Chord):
            # Expand chords into individual notes
            for pitch in element.pitches:
                notes_list.append({
                    'pitch': pitch.midi,
                    'pitch_name': pitch.nameWithOctave,
                    'start': float(element.offset),
                    'duration': float(element.quarterLength),
                    'velocity': element.volume.velocity if element.volume.velocity else 64,
                    'is_rest': False
                })
        elif isinstance(element, note.Rest):
            notes_list.append({
                'pitch': None,
                'pitch_name': 'Rest',
                'start': float(element.offset),
                'duration': float(element.quarterLength),
                'velocity': 0,
                'is_rest': True
            })

    return sorted(notes_list, key=lambda x: (x['start'], x['pitch'] if x['pitch'] is not None else -1))


def extract_notes_from_musicxml(musicxml_path: Path) -> List[Dict[str, Any]]:
    """
    Extract all notes from MusicXML file.

    Returns same format as extract_notes_from_midi().
    """
    score = converter.parse(musicxml_path)
    notes_list = []

    for element in score.flatten().notesAndRests:
        if isinstance(element, note.Note):
            notes_list.append({
                'pitch': element.pitch.midi,
                'pitch_name': element.pitch.nameWithOctave,
                'start': float(element.offset),
                'duration': float(element.quarterLength),
                'velocity': element.volume.velocity if element.volume.velocity else 64,
                'is_rest': False
            })
        elif isinstance(element, chord.Chord):
            # Expand chords into individual notes
            for pitch in element.pitches:
                notes_list.append({
                    'pitch': pitch.midi,
                    'pitch_name': pitch.nameWithOctave,
                    'start': float(element.offset),
                    'duration': float(element.quarterLength),
                    'velocity': element.volume.velocity if element.volume.velocity else 64,
                    'is_rest': False
                })
        elif isinstance(element, note.Rest):
            notes_list.append({
                'pitch': None,
                'pitch_name': 'Rest',
                'start': float(element.offset),
                'duration': float(element.quarterLength),
                'velocity': 0,
                'is_rest': True
            })

    return sorted(notes_list, key=lambda x: (x['start'], x['pitch'] if x['pitch'] is not None else -1))


def find_note_match(target_note: Dict[str, Any], candidates: List[Dict[str, Any]],
                   tolerance: float = 0.05) -> Tuple[int, float]:
    """
    Find best matching note in candidates list.

    Returns: (index, match_score) where match_score = 0.0 (perfect) to 1.0 (no match)
    """
    best_idx = -1
    best_score = float('inf')

    for idx, candidate in enumerate(candidates):
        # Skip if rest/note mismatch
        if target_note['is_rest'] != candidate['is_rest']:
            continue

        # For rests, only check timing
        if target_note['is_rest']:
            timing_diff = abs(target_note['start'] - candidate['start'])
            duration_diff = abs(target_note['duration'] - candidate['duration'])
            score = timing_diff + duration_diff
        else:
            # For notes, check pitch + timing + duration
            if target_note['pitch'] != candidate['pitch']:
                continue  # Pitch must match exactly

            timing_diff = abs(target_note['start'] - candidate['start'])
            duration_diff = abs(target_note['duration'] - candidate['duration'])
            score = timing_diff + duration_diff

        if score < best_score:
            best_score = score
            best_idx = idx

    return best_idx, best_score


def compare_note_lists(midi_notes: List[Dict[str, Any]],
                      xml_notes: List[Dict[str, Any]],
                      tolerance: float = 0.05) -> Dict[str, Any]:
    """
    Compare MIDI notes with MusicXML notes.

    Returns diagnostic report with:
    - total_midi_notes
    - total_musicxml_notes
    - missing_notes (in MIDI but not MusicXML)
    - extra_notes (in MusicXML but not MIDI)
    - duration_mismatches
    - timing_mismatches
    """
    report = {
        'total_midi_notes': len(midi_notes),
        'total_musicxml_notes': len(xml_notes),
        'missing_notes': [],
        'extra_notes': [],
        'duration_mismatches': [],
        'timing_mismatches': [],
        'perfect_matches': 0,
        'tolerance': tolerance
    }

    # Track which XML notes have been matched
    xml_matched = [False] * len(xml_notes)

    # For each MIDI note, find matching XML note
    for midi_note in midi_notes:
        # Only search unmatched XML notes
        unmatched_xml = [xml_notes[i] for i, matched in enumerate(xml_matched) if not matched]
        unmatched_indices = [i for i, matched in enumerate(xml_matched) if not matched]

        if not unmatched_xml:
            report['missing_notes'].append(midi_note)
            continue

        rel_idx, match_score = find_note_match(midi_note, unmatched_xml, tolerance)

        if rel_idx == -1 or match_score > tolerance * 2:
            # No good match found
            report['missing_notes'].append(midi_note)
        else:
            # Found a match
            actual_idx = unmatched_indices[rel_idx]
            xml_matched[actual_idx] = True
            xml_note = xml_notes[actual_idx]

            if match_score < 0.001:
                report['perfect_matches'] += 1
            else:
                # Check what's different
                if not midi_note['is_rest']:
                    duration_diff = abs(midi_note['duration'] - xml_note['duration'])
                    if duration_diff > tolerance:
                        report['duration_mismatches'].append({
                            'note': midi_note['pitch_name'],
                            'midi_duration': midi_note['duration'],
                            'xml_duration': xml_note['duration'],
                            'difference': duration_diff,
                            'midi_start': midi_note['start'],
                            'xml_start': xml_note['start']
                        })

                    timing_diff = abs(midi_note['start'] - xml_note['start'])
                    if timing_diff > tolerance:
                        report['timing_mismatches'].append({
                            'note': midi_note['pitch_name'],
                            'midi_start': midi_note['start'],
                            'xml_start': xml_note['start'],
                            'difference': timing_diff
                        })

    # Any unmatched XML notes are "extra"
    for idx, matched in enumerate(xml_matched):
        if not matched:
            report['extra_notes'].append(xml_notes[idx])

    return report


def print_report(report: Dict[str, Any]):
    """Print diagnostic report in human-readable format."""
    print("\n" + "="*80)
    print("MIDI → MusicXML DIAGNOSTIC REPORT")
    print("="*80)

    print(f"\n📊 SUMMARY:")
    print(f"  Total MIDI notes:     {report['total_midi_notes']}")
    print(f"  Total MusicXML notes: {report['total_musicxml_notes']}")
    print(f"  Perfect matches:      {report['perfect_matches']}")
    print(f"  Missing notes:        {len(report['missing_notes'])} (in MIDI but not MusicXML)")
    print(f"  Extra notes:          {len(report['extra_notes'])} (in MusicXML but not MIDI)")
    print(f"  Duration mismatches:  {len(report['duration_mismatches'])}")
    print(f"  Timing mismatches:    {len(report['timing_mismatches'])}")

    # Calculate accuracy
    if report['total_midi_notes'] > 0:
        accuracy = (report['perfect_matches'] / report['total_midi_notes']) * 100
        print(f"\n  ✅ Match accuracy: {accuracy:.1f}%")

    # Show missing notes
    if report['missing_notes']:
        print(f"\n❌ MISSING NOTES (first 10):")
        for i, note in enumerate(report['missing_notes'][:10]):
            if note['is_rest']:
                print(f"  {i+1}. Rest at {note['start']:.2f}, duration {note['duration']:.4f}")
            else:
                print(f"  {i+1}. {note['pitch_name']} (MIDI {note['pitch']}) at {note['start']:.2f}, duration {note['duration']:.4f}")

    # Show extra notes
    if report['extra_notes']:
        print(f"\n➕ EXTRA NOTES (first 10):")
        for i, note in enumerate(report['extra_notes'][:10]):
            if note['is_rest']:
                print(f"  {i+1}. Rest at {note['start']:.2f}, duration {note['duration']:.4f}")
            else:
                print(f"  {i+1}. {note['pitch_name']} (MIDI {note['pitch']}) at {note['start']:.2f}, duration {note['duration']:.4f}")

    # Show duration mismatches
    if report['duration_mismatches']:
        print(f"\n⏱️  DURATION MISMATCHES (first 10):")
        for i, mismatch in enumerate(report['duration_mismatches'][:10]):
            print(f"  {i+1}. {mismatch['note']} at {mismatch['midi_start']:.2f}:")
            print(f"      MIDI: {mismatch['midi_duration']:.4f}  →  MusicXML: {mismatch['xml_duration']:.4f}")
            print(f"      Difference: {mismatch['difference']:.4f} quarter notes")

    # Show timing mismatches
    if report['timing_mismatches']:
        print(f"\n📍 TIMING MISMATCHES (first 10):")
        for i, mismatch in enumerate(report['timing_mismatches'][:10]):
            print(f"  {i+1}. {mismatch['note']}:")
            print(f"      MIDI: {mismatch['midi_start']:.4f}  →  MusicXML: {mismatch['xml_start']:.4f}")
            print(f"      Difference: {mismatch['difference']:.4f} quarter notes")

    print("\n" + "="*80)


def main():
    parser = argparse.ArgumentParser(
        description='Compare MIDI with MusicXML to diagnose conversion issues'
    )
    parser.add_argument('midi_file', type=Path, help='Path to MIDI file')
    parser.add_argument('musicxml_file', type=Path, help='Path to MusicXML file')
    parser.add_argument('--output', '-o', type=Path, help='Output JSON report file')
    parser.add_argument('--tolerance', '-t', type=float, default=0.05,
                       help='Timing/duration tolerance in quarter notes (default: 0.05)')

    args = parser.parse_args()

    # Validate input files
    if not args.midi_file.exists():
        print(f"ERROR: MIDI file not found: {args.midi_file}")
        return 1

    if not args.musicxml_file.exists():
        print(f"ERROR: MusicXML file not found: {args.musicxml_file}")
        return 1

    print(f"🔍 Analyzing MIDI → MusicXML conversion...")
    print(f"   MIDI: {args.midi_file}")
    print(f"   MusicXML: {args.musicxml_file}")
    print(f"   Tolerance: {args.tolerance} quarter notes")

    # Extract notes
    print("\n📝 Extracting notes from MIDI...")
    midi_notes = extract_notes_from_midi(args.midi_file)

    print(f"📝 Extracting notes from MusicXML...")
    xml_notes = extract_notes_from_musicxml(args.musicxml_file)

    # Compare
    print(f"🔬 Comparing notes...")
    report = compare_note_lists(midi_notes, xml_notes, args.tolerance)

    # Print report
    print_report(report)

    # Save JSON if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\n💾 Full report saved to: {args.output}")

    return 0


if __name__ == '__main__':
    exit(main())
