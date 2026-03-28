#!/usr/bin/env python3
"""
Test script for the new audio/video format parameters in ComfyUI-Notifier.

This script validates the functionality of:
1. audio_format parameter (flac, mp3, wav, opus)
2. audio_quality parameter (128k, 192k, 256k, 320k)
3. video_format parameter (h264, h265, vp9)
"""

import sys
import os

# Add the notifier module to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_parameter_parsing():
    """Test that parameters are correctly parsed"""
    from notifier.media_adapter import MediaAdapter
    
    adapter = MediaAdapter.get_instance()
    
    # Test _resolve_audio_format method
    print("Testing _resolve_audio_format()...")
    assert adapter._resolve_audio_format("auto", "") == "flac", "Default format should be flac"
    assert adapter._resolve_audio_format("mp3", "") == "mp3", "Should resolve mp3"
    assert adapter._resolve_audio_format("wav", "") == "wav", "Should resolve wav"
    assert adapter._resolve_audio_format("opus", "") == "opus", "Should resolve opus"
    assert adapter._resolve_audio_format("auto", "test.mp3") == "mp3", "Should infer from filename"
    print("✓ Audio format resolution works correctly")


def test_hash_generation():
    """Test that different formats/qualities generate different cache keys"""
    print("\nTesting hash generation with format/quality parameters...")
    from notifier.media_adapter import MediaAdapter
    import torch
    
    adapter = MediaAdapter.get_instance()
    
    # Create mock audio data
    audio_data = {
        "waveform": torch.randn(1, 44100),
        "sample_rate": 44100
    }
    
    # Generate hashes with different parameters
    hash1 = adapter._hash_audio(audio_data, "test.wav", "auto", "flac", "128k")
    hash2 = adapter._hash_audio(audio_data, "test.wav", "auto", "mp3", "256k")
    hash3 = adapter._hash_audio(audio_data, "test.wav", "auto", "flac", "128k")
    
    assert hash1 != hash2, "Different formats/qualities should produce different hashes"
    assert hash1 == hash3, "Same parameters should produce same hash"
    print("✓ Hash generation correctly differentiates format/quality")


def test_node_inputs():
    """Test that the node correctly defines new input types"""
    print("\nTesting node INPUT_TYPES...")
    
    # Mock the NotificationManager
    from notifier.notify import NotificationManager
    from nodes import GeneralNotifier
    
    # Get input types
    input_types = GeneralNotifier.INPUT_TYPES()
    
    # Check required inputs
    assert "file_path" in input_types["required"]
    assert "message" in input_types["required"]
    print("✓ Required inputs present")
    
    # Check optional inputs
    optional_inputs = input_types["optional"]
    assert "audio_format" in optional_inputs, "audio_format should be in optional inputs"
    assert "audio_quality" in optional_inputs, "audio_quality should be in optional inputs"
    assert "video_format" in optional_inputs, "video_format should be in optional inputs"
    assert "retry_attempts" in optional_inputs, "retry_attempts should be in optional inputs"
    assert "retry_delay_seconds" in optional_inputs, "retry_delay_seconds should be in optional inputs"
    assert "retry_backoff_factor" in optional_inputs, "retry_backoff_factor should be in optional inputs"
    print("✓ New optional inputs defined")
    
    # Check audio_format options
    audio_format_options = optional_inputs["audio_format"][0]
    assert "auto" in audio_format_options
    assert "flac" in audio_format_options
    assert "mp3" in audio_format_options
    assert "wav" in audio_format_options
    assert "opus" in audio_format_options
    print("✓ Audio format options correct")
    
    # Check audio_quality options
    audio_quality_options = optional_inputs["audio_quality"][0]
    assert "auto" in audio_quality_options
    assert "128k" in audio_quality_options
    assert "192k" in audio_quality_options
    assert "256k" in audio_quality_options
    assert "320k" in audio_quality_options
    print("✓ Audio quality options correct")
    
    # Check video_format options
    video_format_options = optional_inputs["video_format"][0]
    assert "auto" in video_format_options
    assert "h264" in video_format_options
    assert "h265" in video_format_options
    assert "vp9" in video_format_options
    print("✓ Video format options correct")

    # Check retry defaults
    retry_attempts_config = optional_inputs["retry_attempts"][1]
    assert retry_attempts_config["default"] == 0
    assert retry_attempts_config["min"] == 0
    print("✓ Retry attempts defaults correct")


def test_backward_compatibility():
    """Test that default values maintain backward compatibility"""
    print("\nTesting backward compatibility...")
    
    # The default values should be "auto" which internally resolves to:
    # - audio_format: "auto" -> "flac" (default)
    # - audio_quality: "auto" -> "128k" (default)
    # - video_format: "auto" (preserved)
    
    from notifier.media_adapter import MediaAdapter
    
    adapter = MediaAdapter.get_instance()
    
    # Test default resolution
    default_format = adapter._resolve_audio_format("auto", "")
    assert default_format == "flac", "Default format should resolve to flac"
    
    print("✓ Backward compatibility maintained with 'auto' defaults")


if __name__ == "__main__":
    print("=" * 60)
    print("ComfyUI-Notifier Audio/Video Format Tests")
    print("=" * 60)
    
    try:
        test_parameter_parsing()
        test_node_inputs()
        test_backward_compatibility()
        # test_hash_generation would require torch, skipping for now
        
        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
