"""
Generate full 8-piece MAESTRO test set.
"""

from pathlib import Path
import json

# Test cases from prepare_maestro.py
MAESTRO_SUBSET = [
    # Easy - Simple classical pieces
    ("2004", "test", "MIDI-Unprocessed_SMF_02_R1_2004_01-05_ORIG_MID--AUDIO_02_R1_2004_03_Track03_wav", "classical", "easy"),
    ("2004", "test", "MIDI-Unprocessed_SMF_02_R1_2004_01-05_ORIG_MID--AUDIO_02_R1_2004_05_Track05_wav", "classical", "easy"),

    # Medium - Chopin, moderate tempo
    ("2004", "test", "MIDI-Unprocessed_XP_14_R1_2004_01-04_ORIG_MID--AUDIO_14_R1_2004_04_Track04_wav", "classical", "medium"),
    ("2006", "test", "MIDI-Unprocessed_07_R1_2006_01-09_ORIG_MID--AUDIO_07_R1_2006_04_Track04_wav", "classical", "medium"),
    ("2008", "test", "MIDI-Unprocessed_11_R1_2008_01-04_ORIG_MID--AUDIO_11_R1_2008_02_Track02_wav", "classical", "medium"),

    # Hard - Fast passages, complex harmony
    ("2009", "test", "MIDI-Unprocessed_16_R1_2009_01-04_ORIG_MID--AUDIO_16_R1_2009_16_R1_2009_02_WAV", "classical", "hard"),
    ("2011", "test", "MIDI-Unprocessed_03_R1_2011_MID--AUDIO_03_R1_2011_03_R1_2011_02_WAV", "classical", "hard"),
    ("2013", "test", "MIDI-Unprocessed_20_R1_2013_MID--AUDIO_20_R1_2013_20_R1_2013_02_WAV", "classical", "hard"),
]


def generate_test_cases(maestro_dir: str = "../../data/maestro-v3.0.0"):
    """Generate test_videos.json with all 8 MAESTRO pieces."""

    test_cases = []

    for year, split, filename_prefix, genre, difficulty in MAESTRO_SUBSET:
        # Construct paths
        audio_path = f"{maestro_dir}/{year}/{filename_prefix}.wav"
        midi_path = f"{maestro_dir}/{year}/{filename_prefix}.midi"

        # Create test case
        test_case = {
            "name": filename_prefix,
            "audio_path": audio_path,
            "ground_truth_midi": midi_path,
            "genre": genre,
            "difficulty": difficulty,
            "duration": None
        }

        test_cases.append(test_case)

    return test_cases


if __name__ == "__main__":
    # Generate test cases
    test_cases = generate_test_cases()

    # Save to JSON
    output_file = Path(__file__).parent / "test_videos.json"

    with open(output_file, 'w') as f:
        json.dump(test_cases, f, indent=2)

    print(f"✅ Generated {len(test_cases)} test cases")
    print(f"📝 Saved to: {output_file}")
    print("\nBreakdown:")
    print(f"  - Easy: {sum(1 for tc in test_cases if tc['difficulty'] == 'easy')}")
    print(f"  - Medium: {sum(1 for tc in test_cases if tc['difficulty'] == 'medium')}")
    print(f"  - Hard: {sum(1 for tc in test_cases if tc['difficulty'] == 'hard')}")
