#!/usr/bin/env python3
"""
Test script for voice-enabled Spanish tutor in Archon
Run with: cd /Users/ciarancox/Archon && uv run python test_voice_integration.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Add Archon to Python path
archon_path = Path(__file__).parent / "python" / "src"
sys.path.insert(0, str(archon_path))

async def test_voice_agent():
    """Test the voice-aware Spanish tutor agent"""
    print("🧪 Testing Voice-Enabled Spanish Tutor Agent")
    print("=" * 50)

    try:
        from agents.spanish_tutor_agent import SpanishTutorAgent, SpanishTutorDependencies

        # Create agent
        agent = SpanishTutorAgent()
        print("✅ Spanish tutor agent created")

        # Test voice context dependencies
        voice_deps = SpanishTutorDependencies(
            student_level="beginner",
            conversation_mode="casual",
            input_method="voice",
            voice_enabled=True,
            session_id="test-voice-session"
        )

        # Test voice input scenario
        voice_message = "Hola, me llamo Juan y quiero aprender español"
        print(f"\n🎤 Testing voice input: '{voice_message}'")

        response = await agent.run(voice_message, voice_deps)
        print(f"🗣️ Agent response: {response}")

        # Test text input for comparison
        text_deps = SpanishTutorDependencies(
            student_level="beginner",
            conversation_mode="casual",
            input_method="text",
            voice_enabled=False,
            session_id="test-text-session"
        )

        text_message = "Hello, my name is Juan and I want to learn Spanish"
        print(f"\n💬 Testing text input: '{text_message}'")

        response = await agent.run(text_message, text_deps)
        print(f"📝 Agent response: {response}")

        print("\n✅ Voice integration test completed!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

async def test_frontend_requirements():
    """Test that frontend requirements are met"""
    print("\n🌐 Testing Frontend Requirements")
    print("=" * 35)

    # Check if voice components exist
    voice_components = [
        "archon-ui-main/src/components/voice/VoiceControls.tsx",
        "archon-ui-main/src/components/agent-chat/VoiceEnabledChatPanel.tsx",
        "archon-ui-main/src/types/speech.d.ts"
    ]

    for component in voice_components:
        if os.path.exists(component):
            print(f"✅ {component}")
        else:
            print(f"❌ {component} - Missing")

    # Check if MainLayout is updated
    main_layout_path = "archon-ui-main/src/components/layout/MainLayout.tsx"
    if os.path.exists(main_layout_path):
        with open(main_layout_path, 'r') as f:
            content = f.read()
            if "VoiceEnabledChatPanel" in content:
                print(f"✅ {main_layout_path} - Updated for voice")
            else:
                print(f"⚠️ {main_layout_path} - Not updated for voice")
    else:
        print(f"❌ {main_layout_path} - Missing")

def test_browser_compatibility():
    """Test browser API compatibility info"""
    print("\n🌍 Browser Compatibility Notes")
    print("=" * 33)

    print("📋 Web Speech API Requirements:")
    print("✅ Chrome/Edge: Full support")
    print("✅ Safari: Partial support (STT only)")
    print("✅ Firefox: Limited support")
    print("⚠️ Requires HTTPS in production")
    print("⚠️ Requires microphone permissions")

    print("\n🎯 Voice Features Available:")
    print("• Speech-to-Text (Speech Recognition)")
    print("• Text-to-Speech (Speech Synthesis)")
    print("• Spanish language detection")
    print("• Audio level monitoring")
    print("• Push-to-talk functionality")

async def main():
    """Run all tests"""
    print("🎙️ ARCHON SPANISH TUTOR - VOICE INTEGRATION TEST")
    print("=" * 55)

    # Test backend agent
    await test_voice_agent()

    # Test frontend components
    await test_frontend_requirements()

    # Browser compatibility info
    test_browser_compatibility()

    print("\n🎉 Testing Complete!")
    print("\n🚀 To use voice features:")
    print("1. Start Archon: cd /path/to/Archon && make dev")
    print("2. Open browser: http://localhost:3737")
    print("3. Click the chat button in bottom-right")
    print("4. Click the volume icon to enable voice")
    print("5. Click the microphone to start talking")
    print("6. Say: 'Hola, quiero aprender español'")

if __name__ == "__main__":
    asyncio.run(main())