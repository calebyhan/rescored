#!/usr/bin/env python3
"""
Quick verification test - only runs the 6 videos that had code bugs (now fixed).

This is faster than the full suite and verifies our bug fixes work.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from test_accuracy import run_accuracy_test
import json
from datetime import datetime

# Only test the 6 videos that had code bugs (should all pass now)
QUICK_TEST_VIDEOS = [
    {
        "id": "chopin_nocturne",
        "url": "https://www.youtube.com/watch?v=9E6b3swbnWg",
        "description": "Chopin - Nocturne Op. 9 No. 2",
        "difficulty": "hard",
        "expected_accuracy": "50-60%",
        "notes": "2048th note duration (Bug #2b)",
        "bug": "2048th note duration (Bug #2b)"
    },
    {
        "id": "canon_in_d",
        "url": "https://www.youtube.com/watch?v=NlprozGcs80",
        "description": "Pachelbel - Canon in D",
        "difficulty": "medium",
        "expected_accuracy": "60-70%",
        "notes": "NoneType velocity (Bug #2a)",
        "bug": "NoneType velocity (Bug #2a)"
    },
    {
        "id": "river_flows",
        "url": "https://www.youtube.com/watch?v=7maJOI3QMu0",
        "description": "Yiruma - River Flows in You",
        "difficulty": "medium",
        "expected_accuracy": "60-70%",
        "notes": "NoneType velocity (Bug #2a)",
        "bug": "NoneType velocity (Bug #2a)"
    },
    {
        "id": "moonlight_sonata",
        "url": "https://www.youtube.com/watch?v=4Tr0otuiQuU",
        "description": "Beethoven - Moonlight Sonata",
        "difficulty": "medium",
        "expected_accuracy": "60-70%",
        "notes": "NoneType velocity (Bug #2a)",
        "bug": "NoneType velocity (Bug #2a)"
    },
    {
        "id": "claire_de_lune",
        "url": "https://www.youtube.com/watch?v=WNcsUNKlAKw",
        "description": "Debussy - Clair de Lune",
        "difficulty": "hard",
        "expected_accuracy": "50-60%",
        "notes": "2048th note duration (Bug #2b)",
        "bug": "2048th note duration (Bug #2b)"
    },
    {
        "id": "la_campanella",
        "url": "https://www.youtube.com/watch?v=MD6xMyuZls0",
        "description": "Liszt - La Campanella",
        "difficulty": "very_hard",
        "expected_accuracy": "40-50%",
        "notes": "NoneType velocity (Bug #2a)",
        "bug": "NoneType velocity (Bug #2a)"
    }
]

def main():
    """Run quick verification tests."""
    print("="*70)
    print("Quick Verification Test - Bug Fixes")
    print("="*70)
    print(f"Testing {len(QUICK_TEST_VIDEOS)} videos that previously failed")
    print("All should now succeed (verifies bug fixes)")
    print()

    results = []
    for i, video in enumerate(QUICK_TEST_VIDEOS, 1):
        print(f"\n[{i}/{len(QUICK_TEST_VIDEOS)}] Testing: {video['id']}")
        print(f"Previous error: {video['bug']}")

        result = run_accuracy_test(video, verbose=True)
        results.append(result)

    # Summary
    print("\n" + "="*70)
    print("QUICK VERIFICATION SUMMARY")
    print("="*70)

    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]

    print(f"\nTotal: {len(results)} | Success: {len(successful)} | Failed: {len(failed)}")
    print(f"Success Rate: {len(successful)/len(results)*100:.1f}%")

    if successful:
        print("\n✅ Bug Fixes Verified - Successful Transcriptions:")
        for r in successful:
            if "midi" in r["metrics"] and "musicxml" in r["metrics"]:
                notes = r["metrics"]["midi"]["total_notes"]
                measures = r["metrics"]["musicxml"]["total_measures"]
                print(f"  - {r['video_id']:20s} | {notes:4d} notes | {measures:3d} measures")

    if failed:
        print("\n❌ Still Failing:")
        for r in failed:
            error_preview = r["error"][:80] if r["error"] else "Unknown"
            print(f"  - {r['video_id']:20s} | {error_preview}")

    # Save results
    from app_config import settings
    output_path = Path(settings.storage_path) / "quick_verify_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump({
            "test_date": datetime.utcnow().isoformat(),
            "test_type": "bug_fix_verification",
            "total_tests": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": len(successful) / len(results),
            "results": results
        }, f, indent=2)

    print(f"\n📊 Results saved to: {output_path}")

    if len(successful) == len(results):
        print("\n🎉 ALL BUG FIXES VERIFIED! Ready for full test suite.")
        return 0
    else:
        print(f"\n⚠️  {len(failed)} test(s) still failing - investigate before full suite")
        return 1


if __name__ == "__main__":
    sys.exit(main())
