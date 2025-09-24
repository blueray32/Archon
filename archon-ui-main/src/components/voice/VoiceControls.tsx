import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Mic, MicOff, Volume2, VolumeX, Square } from 'lucide-react';

interface VoiceControlsProps {
  onVoiceInput: (text: string) => void;
  onVoiceResponse: (text: string) => void;
  isListening: boolean;
  isSpeaking: boolean;
  disabled?: boolean;
  language?: string;
}

export const VoiceControls: React.FC<VoiceControlsProps> = ({
  onVoiceInput,
  onVoiceResponse,
  isListening,
  isSpeaking,
  disabled = false,
  language = 'es-ES'
}) => {
  const [isSupported, setIsSupported] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // References for speech recognition and synthesis
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const synthesisRef = useRef<SpeechSynthesis | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  // Check for Web Speech API support
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const speechSynthesis = window.speechSynthesis;

    if (SpeechRecognition && speechSynthesis) {
      setIsSupported(true);
      synthesisRef.current = speechSynthesis;

      // Initialize speech recognition
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = language;

      recognition.onstart = () => {
        setIsRecording(true);
        setError(null);
        startAudioLevelMonitoring();
      };

      recognition.onresult = (event) => {
        const transcript = event.results[0]?.transcript;
        if (transcript) {
          console.log('Voice input:', transcript);
          onVoiceInput(transcript);
        }
      };

      recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        setError(`Voice recognition error: ${event.error}`);
        setIsRecording(false);
        stopAudioLevelMonitoring();
      };

      recognition.onend = () => {
        setIsRecording(false);
        stopAudioLevelMonitoring();
      };

      recognitionRef.current = recognition;
    } else {
      setIsSupported(false);
      console.warn('Web Speech API not supported in this browser');
    }

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort();
      }
      stopAudioLevelMonitoring();
    };
  }, [language, onVoiceInput]);

  // Audio level monitoring for visual feedback
  const startAudioLevelMonitoring = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioContextRef.current.createMediaStreamSource(stream);

      analyserRef.current = audioContextRef.current.createAnalyser();
      analyserRef.current.fftSize = 256;
      source.connect(analyserRef.current);

      const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);

      const updateAudioLevel = () => {
        if (analyserRef.current) {
          analyserRef.current.getByteFrequencyData(dataArray);
          const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
          setAudioLevel(average / 255);
        }
        animationFrameRef.current = requestAnimationFrame(updateAudioLevel);
      };

      updateAudioLevel();
    } catch (error) {
      console.error('Failed to start audio monitoring:', error);
    }
  }, []);

  const stopAudioLevelMonitoring = useCallback(() => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    setAudioLevel(0);
  }, []);

  // Start voice recognition
  const startListening = useCallback(() => {
    if (!isSupported || !recognitionRef.current || disabled) return;

    try {
      recognitionRef.current.start();
    } catch (error) {
      console.error('Failed to start speech recognition:', error);
      setError('Failed to start voice recognition');
    }
  }, [isSupported, disabled]);

  // Stop voice recognition
  const stopListening = useCallback(() => {
    if (recognitionRef.current && isRecording) {
      recognitionRef.current.stop();
    }
  }, [isRecording]);

  // Speak text using Text-to-Speech
  const speakText = useCallback((text: string) => {
    if (!synthesisRef.current || !voiceEnabled) return;

    // Cancel any ongoing speech
    synthesisRef.current.cancel();

    const sanitizeForTTS = (raw: string): string => {
      const lines = raw.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
      const cleaned = lines.map(l =>
        l
          .replace(/^\s*(?:[-*•]+|\d+[\.\)]\s*)\s*/, '')
          .replace(/\*\*(.*?)\*\*/g, '$1')
          .replace(/\*(.*?)\*/g, '$1')
          .replace(/\[[^\]]+\]/g, '')
          .replace(/[•▪︎◦·●]/g, '')
          .replace(/\s{2,}/g, ' ')
          .trim()
      ).filter(Boolean);
      return cleaned.join('\n');
    };

    const utterance = new SpeechSynthesisUtterance(sanitizeForTTS(text));

    // Set Spanish voice if available
    const voices = synthesisRef.current.getVoices();
    const spanishVoice = voices.find(voice =>
      voice.lang.startsWith('es') || voice.lang.includes('Spanish')
    );

    if (spanishVoice) {
      utterance.voice = spanishVoice;
    }

    utterance.lang = language;
    utterance.rate = 0.9; // Slightly slower for learning
    utterance.pitch = 1.0;
    utterance.volume = 0.8;

    utterance.onstart = () => {
      console.log('TTS started');
    };

    utterance.onend = () => {
      console.log('TTS ended');
    };

    utterance.onerror = (error) => {
      console.error('TTS error:', error);
    };

    synthesisRef.current.speak(utterance);
  }, [language, voiceEnabled]);

  // Effect to handle speaking responses
  useEffect(() => {
    if (isSpeaking) {
      // This would be triggered when a new response comes in
      // The parent component should call onVoiceResponse with the text
    }
  }, [isSpeaking]);

  // Handle voice response from parent
  useEffect(() => {
    const handleVoiceResponse = (text: string) => {
      speakText(text);
    };

    // This is a workaround - in a real implementation, you'd pass the speakText function up
    // or use a different pattern
    onVoiceResponse = handleVoiceResponse;
  }, [speakText, onVoiceResponse]);

  if (!isSupported) {
    return (
      <div className="flex items-center gap-2 text-gray-500 text-sm">
        <MicOff className="w-4 h-4" />
        <span>Voice not supported in this browser</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      {/* Microphone button */}
      <button
        onClick={isRecording ? stopListening : startListening}
        disabled={disabled}
        className={`
          p-2 rounded-full transition-all duration-200
          ${isRecording
            ? 'bg-red-500 hover:bg-red-600 text-white shadow-lg animate-pulse'
            : 'bg-blue-500 hover:bg-blue-600 text-white'
          }
          ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        `}
        title={isRecording ? 'Stop listening' : 'Start listening'}
      >
        {isRecording ? <Square className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
      </button>

      {/* Audio level indicator */}
      {isRecording && (
        <div className="w-16 h-2 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-green-500 transition-all duration-100"
            style={{ width: `${audioLevel * 100}%` }}
          />
        </div>
      )}

      {/* Voice output toggle */}
      <button
        onClick={() => setVoiceEnabled(!voiceEnabled)}
        className={`
          p-2 rounded-full transition-all duration-200
          ${voiceEnabled
            ? 'bg-green-500 hover:bg-green-600 text-white'
            : 'bg-gray-400 hover:bg-gray-500 text-white'
          }
        `}
        title={voiceEnabled ? 'Voice output enabled' : 'Voice output disabled'}
      >
        {voiceEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
      </button>

      {/* Status indicator */}
      {isRecording && (
        <span className="text-xs text-red-600 font-medium">
          Escuchando...
        </span>
      )}

      {/* Error display */}
      {error && (
        <span className="text-xs text-red-500 max-w-32 truncate" title={error}>
          {error}
        </span>
      )}
    </div>
  );
};

// Export the speak function for external use
export const useSpeechSynthesis = () => {
  const speak = useCallback((text: string, language = 'es-ES') => {
    if (!window.speechSynthesis) return;

    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    const voices = window.speechSynthesis.getVoices();
    const spanishVoice = voices.find(voice =>
      voice.lang.startsWith('es') || voice.lang.includes('Spanish')
    );

    if (spanishVoice) {
      utterance.voice = spanishVoice;
    }

    utterance.lang = language;
    utterance.rate = 0.9;
    utterance.pitch = 1.0;
    utterance.volume = 0.8;

    window.speechSynthesis.speak(utterance);
  }, []);

  const stopSpeaking = useCallback(() => {
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
  }, []);

  return { speak, stopSpeaking };
};
