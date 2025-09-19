import React, { useEffect, useState, useRef, useCallback } from 'react';
import { Send, User, WifiOff, RefreshCw, BookOpen, Search, Mic, Volume2, VolumeX, MicOff, SlidersHorizontal, X } from 'lucide-react';
import * as Popover from '@radix-ui/react-popover';
import * as Tooltip from '@radix-ui/react-tooltip';
import { ArchonLoadingSpinner, EdgeLitEffect } from '../animations/Animations';
import { agentChatService, ChatMessage } from '../../services/agentChatService';
import { knowledgeBaseService } from '../../services/knowledgeBaseService';
import { AgentSwitcher } from '../../agents/AgentSwitcher';
import { useAgentState } from '../../agents/AgentContext';
import { getAgentTypeFor } from '../../agents/registry';

/**
 * Props for the VoiceEnabledChatPanel component
 */
interface VoiceEnabledChatPanelProps {
  'data-id'?: string;
  onClose?: () => void;
}

/**
 * VoiceEnabledChatPanel - Enhanced chat interface with voice capabilities
 *
 * Adds speech-to-text input and text-to-speech output to the Spanish tutor chat
 */
export const VoiceEnabledChatPanel: React.FC<VoiceEnabledChatPanelProps> = props => {
  const { selectedAgentId, selectedAgent } = useAgentState();
  // Existing chat state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [width, setWidth] = useState(416);
  const [isTyping, setIsTyping] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [streamingMessage, setStreamingMessage] = useState<string>('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'online' | 'offline' | 'connecting'>('connecting');
  const [isReconnecting, setIsReconnecting] = useState(false);

  // Voice-specific state
  const [isVoiceEnabled, setIsVoiceEnabled] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [voiceSupported, setVoiceSupported] = useState(false);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const [availableVoices, setAvailableVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [selectedVoiceName, setSelectedVoiceName] = useState<string | null>(null);
  // Speech recognition language control
  type RecognitionMode = 'auto' | 'es-MX' | 'es-ES' | 'en-US';
  const [recognitionMode, setRecognitionMode] = useState<RecognitionMode>('auto');
  // Continuous dictation (beta) and silence timeout
  const [continuousDictation, setContinuousDictation] = useState<boolean>(() => {
    const saved = localStorage.getItem('archonASRContinuous');
    return saved === 'true';
  });
  const [silenceTimeoutMs, setSilenceTimeoutMs] = useState<number>(() => {
    const saved = localStorage.getItem('archonASRSilenceMs');
    const val = saved ? parseInt(saved, 10) : 900;
    return Number.isFinite(val) ? Math.min(3000, Math.max(300, val)) : 900;
  });
  useEffect(() => {
    localStorage.setItem('archonASRContinuous', String(continuousDictation));
  }, [continuousDictation]);
  useEffect(() => {
    localStorage.setItem('archonASRSilenceMs', String(silenceTimeoutMs));
  }, [silenceTimeoutMs]);
  // Confidence threshold for auto fallback (0..1)
  const [confidenceThreshold, setConfidenceThreshold] = useState<number>(() => {
    const saved = localStorage.getItem('archonASRConfidenceThreshold');
    const val = saved ? parseFloat(saved) : 0.55;
    return Number.isFinite(val) ? Math.min(1, Math.max(0, val)) : 0.55;
  });
  useEffect(() => {
    localStorage.setItem('archonASRConfidenceThreshold', String(confidenceThreshold));
  }, [confidenceThreshold]);
  // Track recent voice sends to annotate messages with recognized language
  const recentVoiceSendsRef = useRef<{ content: string; lang: string; ts: number }[]>([]);

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const dragHandleRef = useRef<HTMLDivElement>(null);
  const chatPanelRef = useRef<HTMLDivElement>(null);
  const sessionIdRef = useRef<string | null>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const triedFallbackRef = useRef<boolean>(false);
  const fallbackPendingRef = useRef<string | null>(null);
  const recognizedAccumRef = useRef<string>('');
  const commitTimerRef = useRef<number | null>(null);
  // Track the last spoken message to avoid duplicates
  const lastSpokenIdRef = useRef<string | null>(null);
  const ensuredPydanticKBRef = useRef<boolean>(false);

  // Check for Web Speech API support
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const speechSynthesis = window.speechSynthesis;

    console.log('Checking voice support:', { SpeechRecognition: !!SpeechRecognition, speechSynthesis: !!speechSynthesis });

    if (SpeechRecognition && speechSynthesis) {
      setVoiceSupported(true);

      // Initialize speech recognition
      const recognition = new SpeechRecognition();
      recognition.continuous = continuousDictation;
      recognition.interimResults = true; // Enable interim results for better UX
      recognition.lang = (() => {
        // Decide initial language: if browser prefers Spanish, start with es-MX; else en-US
        const prefs = (navigator.languages || [navigator.language]).map(l => l.toLowerCase());
        return prefs.some(l => l.startsWith('es')) ? 'es-MX' : 'en-US';
      })();
      recognition.maxAlternatives = 5;

      recognition.onstart = () => {
        console.log('Speech recognition started');
        setIsListening(true);
        setVoiceError(null);
      };

      const LOW_CONFIDENCE_THRESHOLD = confidenceThreshold;
      const altLangFor = (lang: string) => (lang && lang.toLowerCase().startsWith('en') ? 'es-MX' : 'en-US');
      const scheduleCommit = () => {
        if (!continuousDictation) return;
        if (commitTimerRef.current) window.clearTimeout(commitTimerRef.current);
        commitTimerRef.current = window.setTimeout(() => {
          const finalText = recognizedAccumRef.current.trim();
          if (finalText) {
            const usedLang = recognitionRef.current?.lang || getRecognitionLang();
            recentVoiceSendsRef.current.unshift({ content: finalText, lang: usedLang, ts: Date.now() });
            recentVoiceSendsRef.current = recentVoiceSendsRef.current.slice(0, 6);
            console.log('ASR silence commit:', { finalText, usedLang });
            handleSendMessage(finalText);
            recognizedAccumRef.current = '';
            setInputValue('');
          }
        }, silenceTimeoutMs) as unknown as number;
      };

      recognition.onresult = (event) => {
        console.log('Speech recognition result event:', event);

        // Build running final + interim transcript
        let interimText = '';
        try {
          // Iterate from the reported resultIndex to end for better accumulation
          const startIndex = (event as any).resultIndex ?? Math.max(0, event.results.length - 1);
          for (let i = startIndex; i < event.results.length; i++) {
            const res = event.results[i];
            if (res.isFinal) {
              const seg = (res[0]?.transcript || '').trim();
              const conf = typeof res[0]?.confidence === 'number' ? res[0].confidence : 1;
              if (seg) {
                recognizedAccumRef.current = `${recognizedAccumRef.current} ${seg}`.trim();
              }
              // Low-confidence auto-retry decision uses the latest final segment confidence
              if (
                recognitionMode === 'auto' &&
                !triedFallbackRef.current &&
                conf < LOW_CONFIDENCE_THRESHOLD &&
                recognitionRef.current
              ) {
                const currentLang = recognitionRef.current.lang || 'en-US';
                const fallbackLang = altLangFor(currentLang);
                console.warn('Low-confidence ASR segment. Scheduling fallback:', {
                  segPreview: seg.slice(0, 40) + '...',
                  confidence: conf,
                  from: currentLang,
                  to: fallbackLang
                });
                triedFallbackRef.current = true;
                fallbackPendingRef.current = fallbackLang;
                try { recognitionRef.current.stop(); } catch (e) { /* no-op */ }
                break;
              }
            } else {
              interimText = res[0]?.transcript || '';
            }
          }
        } catch (e) {
          console.warn('ASR accumulation failed; falling back to last result only', e);
          const lastResult = event.results[event.results.length - 1];
          if (lastResult) {
            if (lastResult.isFinal) {
              const seg = (lastResult[0]?.transcript || '').trim();
              if (seg) recognizedAccumRef.current = `${recognizedAccumRef.current} ${seg}`.trim();
            } else {
              interimText = lastResult[0]?.transcript || '';
            }
          }
        }

        const composed = `${recognizedAccumRef.current}${interimText ? ' ' + interimText : ''}`.trim();
        if (composed) {
          console.log('ASR composed input:', composed);
          setInputValue(composed);
        }
        // In continuous mode, schedule a commit after silence
        if (continuousDictation) {
          scheduleCommit();
        }
      };

      recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error, event);
        let errorMessage = `Voice error: ${event.error}`;

        // Provide more helpful error messages
        switch (event.error) {
          case 'not-allowed':
            errorMessage = 'Microphone access denied. Please allow microphone permissions.';
            break;
          case 'no-speech':
            errorMessage = 'No speech detected. Try speaking louder.';
            break;
          case 'network':
            errorMessage = 'Network error. Check your internet connection.';
            break;
          case 'audio-capture':
            errorMessage = 'Microphone not found or audio capture failed.';
            break;
        }

        setVoiceError(errorMessage);
        setIsListening(false);
      };

      recognition.onend = () => {
        console.log('Speech recognition ended');
        setIsListening(false);
        // If a fallback is pending, restart with the alternate language
        if (fallbackPendingRef.current) {
          const lang = fallbackPendingRef.current;
          fallbackPendingRef.current = null;
          try {
            recognition.lang = lang;
            console.log('Restarting recognition for fallback with lang:', lang);
            recognition.start();
          } catch (e) {
            console.error('Failed to restart recognition for fallback:', e);
            triedFallbackRef.current = false;
          }
        } else {
          if (!continuousDictation) {
            // Single-shot mode: send accumulated transcript once, if any
            const finalText = recognizedAccumRef.current.trim();
            if (finalText) {
              const usedLang = recognitionRef.current?.lang || getRecognitionLang();
              recentVoiceSendsRef.current.unshift({ content: finalText, lang: usedLang, ts: Date.now() });
              recentVoiceSendsRef.current = recentVoiceSendsRef.current.slice(0, 6);
              console.log('Final voice input (accumulated):', finalText);
              handleSendMessage(finalText);
            }
            // Reset for next session
            recognizedAccumRef.current = '';
            triedFallbackRef.current = false;
            fallbackPendingRef.current = null;
          } else if (isVoiceEnabled) {
            // Continuous mode: auto-restart to keep listening
            try {
              recognition.lang = getRecognitionLang();
              recognition.continuous = true;
              console.log('Continuous mode: restarting recognition');
              recognition.start();
            } catch (e) {
              console.warn('Continuous restart failed:', e);
            }
          }
        }
      };

      recognitionRef.current = recognition;
    } else {
      setVoiceSupported(false);
      console.warn('Web Speech API not supported in this browser');
      setVoiceError('Voice features not supported in this browser. Use Chrome, Edge, or Safari.');
    }

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort();
      }
    };
  }, []);

  // Load voices and determine default selection (preferring es-MX female if available)
  useEffect(() => {
    if (!window.speechSynthesis) return;

    const chooseDefaultVoice = (voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | undefined => {
      const lower = (s: string | undefined) => (s || '').toLowerCase();
      const isSpanish = (v: SpeechSynthesisVoice) => lower(v.lang).startsWith('es');
      const isMex = (v: SpeechSynthesisVoice) => lower(v.lang).includes('mx') || lower(v.name).includes('méxico') || lower(v.name).includes('mexico');
      const isGoogle = (v: SpeechSynthesisVoice) => lower(v.name).includes('google');
      const femaleHints = ['female', 'woman', 'maria', 'maría', 'sofia', 'camila', 'luciana', 'paulina', 'isabella', 'isabel', 'elena', 'carmen', 'sabina', 'laura', 'helena', 'victoria', 'samantha'];
      const preferredNames = ['google español', 'google us español', 'google español de estados unidos', 'google español de méxico', 'google español de mexico', 'google español de españa', 'microsoft sabina', 'microsoft laura', 'microsoft helena', 'sofia', 'camila', 'luciana', 'paulina', 'isabella', 'isabel', 'elena', 'maria', 'maría', 'carmen', 'victoria', 'samantha'];
      const isLikelyFemale = (v: SpeechSynthesisVoice) => femaleHints.some(h => lower(v.name).includes(h));
      const nameMatchesPreferred = (v: SpeechSynthesisVoice) => preferredNames.some(n => lower(v.name).includes(n));

      const spanish = voices.filter(isSpanish);

      return (
        spanish.find(v => isMex(v) && isGoogle(v) && (nameMatchesPreferred(v) || isLikelyFemale(v))) ||
        spanish.find(v => isMex(v) && (nameMatchesPreferred(v) || isLikelyFemale(v))) ||
        spanish.find(v => isGoogle(v) && (nameMatchesPreferred(v) || isLikelyFemale(v))) ||
        spanish.find(v => nameMatchesPreferred(v) || isLikelyFemale(v)) ||
        spanish.find(v => isGoogle(v)) ||
        spanish[0] ||
        voices.find(v => isGoogle(v) && isLikelyFemale(v)) ||
        voices[0]
      );
    };

    const updateVoices = () => {
      const voices = window.speechSynthesis.getVoices();
      setAvailableVoices(voices);

      const saved = localStorage.getItem('archonVoiceName');
      if (saved && voices.some(v => v.name === saved)) {
        setSelectedVoiceName(saved);
        return;
      }
      const pick = chooseDefaultVoice(voices);
      if (pick) setSelectedVoiceName(pick.name);
    };

    updateVoices();
    window.speechSynthesis.onvoiceschanged = updateVoices;
    return () => {
      window.speechSynthesis.onvoiceschanged = null;
    };
  }, []);

  // Voice input handler
  const handleVoiceInput = useCallback((transcript: string) => {
    console.log('Processing voice input:', transcript);
    setInputValue(transcript);
    // Automatically send voice messages after a short delay
    setTimeout(() => {
      console.log('Auto-sending voice message:', transcript);
      handleSendMessage(transcript);
    }, 100);
  }, [sessionId]); // Add sessionId as dependency

  // Speak text using Text-to-Speech
  const speakText = useCallback((text: string) => {
    if (!window.speechSynthesis || !isVoiceEnabled) {
      console.log('TTS not available:', { speechSynthesis: !!window.speechSynthesis, isVoiceEnabled });
      return;
    }

    console.log('Starting TTS for text:', text);

    // Cancel any ongoing speech
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);

    // Function to set voice after voices are loaded
    const setVoiceAndSpeak = () => {
      const voices = window.speechSynthesis.getVoices();
      console.log('Available voices:', voices.map(v => ({ name: v.name, lang: v.lang })));

      // Prefer user-selected voice if available
      let selectedVoice = selectedVoiceName ? voices.find(v => v.name === selectedVoiceName) : undefined;
      // Prefer high-quality, natural female Spanish voices
      const preferredNames = [
        // Google
        'google español', 'google us español', 'google español de estados unidos', 'google español de méxico', 'google español de mexico', 'google español de españa',
        // Microsoft / Windows
        'microsoft sabina', 'microsoft laura', 'microsoft helena',
        // Common female Spanish voices
        'sofia', 'camila', 'luciana', 'paulina', 'isabella', 'isabel', 'elena', 'maria', 'maría', 'carmen', 'moira', 'victoria', 'samantha'
      ];
      const femaleHints = ['female', 'woman', 'maria', 'maría', 'sofia', 'camila', 'luciana', 'paulina', 'isabella', 'isabel', 'elena', 'carmen', 'sabina', 'laura', 'helena', 'victoria', 'samantha'];

      const isSpanish = (v: SpeechSynthesisVoice) => v.lang?.toLowerCase().startsWith('es');
      const isGoogle = (v: SpeechSynthesisVoice) => v.name?.toLowerCase().includes('google');
      const isLikelyFemale = (v: SpeechSynthesisVoice) => femaleHints.some(h => v.name?.toLowerCase().includes(h));
      const nameMatchesPreferred = (v: SpeechSynthesisVoice) => preferredNames.some(n => v.name?.toLowerCase().includes(n));

      const spanishVoices = voices.filter(isSpanish);

      // Selection priority:
      // 1) Google Spanish voices with preferred naming
      // 2) Other Spanish voices with preferred female naming
      // 3) Any Google Spanish voice
      // 4) Any Spanish voice
      // 5) Any Google voice with female hint
      // 6) Fallback to first available
      selectedVoice = selectedVoice ||
        spanishVoices.find(v => isGoogle(v) && nameMatchesPreferred(v)) ||
        spanishVoices.find(v => nameMatchesPreferred(v) || isLikelyFemale(v)) ||
        spanishVoices.find(v => isGoogle(v)) ||
        spanishVoices[0] ||
        voices.find(v => isGoogle(v) && isLikelyFemale(v)) ||
        voices[0];

      if (selectedVoice) {
        utterance.voice = selectedVoice;
        console.log('Selected voice:', selectedVoice.name, selectedVoice.lang);
        // Match language to selected voice to avoid mismatch
        utterance.lang = selectedVoice.lang || 'es-ES';
      } else {
        console.log('No voice selected, using system default');
        utterance.lang = 'es-ES';
      }

      // Slightly slower than default but natural
      utterance.rate = 0.95;
      // Slightly higher pitch for a friendly female tone
      utterance.pitch = 1.05;
      utterance.volume = 1.0; // Full volume

      utterance.onstart = () => {
        console.log('TTS started speaking');
        setIsSpeaking(true);
      };

      utterance.onend = () => {
        console.log('TTS finished speaking');
        setIsSpeaking(false);
      };

      utterance.onerror = (event) => {
        console.error('TTS error:', event.error);
        setIsSpeaking(false);
      };

      console.log('Speaking with TTS...');
      window.speechSynthesis.speak(utterance);
    };

    // Check if voices are already loaded
    const voices = window.speechSynthesis.getVoices();
    if (voices.length > 0) {
      setVoiceAndSpeak();
    } else {
      // Wait for voices to load
      console.log('Waiting for voices to load...');
      window.speechSynthesis.onvoiceschanged = () => {
        console.log('Voices loaded, setting up TTS');
        setVoiceAndSpeak();
        window.speechSynthesis.onvoiceschanged = null; // Remove listener
      };
    }
  }, [isVoiceEnabled, selectedVoiceName]);

  // Helper: compute recognition language based on mode and context
  const getRecognitionLang = useCallback((): string => {
    if (recognitionMode !== 'auto') return recognitionMode;
    // Auto: prefer Spanish if environment or selected voice suggests Spanish, else English
    const prefs = (navigator.languages || [navigator.language]).map(l => l.toLowerCase());
    const voiceIsSpanish = (() => {
      const voices = window.speechSynthesis ? window.speechSynthesis.getVoices() : [];
      const selected = selectedVoiceName ? voices.find(v => v.name === selectedVoiceName) : undefined;
      const lang = (selected?.lang || '').toLowerCase();
      return lang.startsWith('es');
    })();
    if (voiceIsSpanish || prefs.some(l => l.startsWith('es'))) return 'es-MX';
    return 'en-US';
  }, [recognitionMode, selectedVoiceName]);

  // Start voice recognition
  const startListening = useCallback(async () => {
    if (!voiceSupported || !recognitionRef.current || !isVoiceEnabled) {
      console.log('Cannot start listening:', { voiceSupported, hasRecognition: !!recognitionRef.current, isVoiceEnabled });
      return;
    }

    try {
      // Check microphone permissions first
      if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        console.log('Requesting microphone permissions...');
        await navigator.mediaDevices.getUserMedia({ audio: true });
        console.log('Microphone permissions granted');
      }

      // Ensure language is set per current mode and reset fallback tracking
      const lang = getRecognitionLang();
      recognitionRef.current.lang = lang;
      recognitionRef.current.continuous = continuousDictation;
      triedFallbackRef.current = false;
      fallbackPendingRef.current = null;
      recognizedAccumRef.current = '';
      if (commitTimerRef.current) {
        window.clearTimeout(commitTimerRef.current);
        commitTimerRef.current = null;
      }
      console.log('Starting speech recognition with lang:', lang);
      setVoiceError(null);
      recognitionRef.current.start();
    } catch (error) {
      console.error('Failed to start speech recognition:', error);
      if (error instanceof Error) {
        if (error.name === 'NotAllowedError') {
          setVoiceError('Microphone access denied. Please allow microphone permissions and try again.');
        } else if (error.name === 'NotFoundError') {
          setVoiceError('No microphone found. Please connect a microphone and try again.');
        } else {
          setVoiceError(`Failed to start voice recognition: ${error.message}`);
        }
      } else {
        setVoiceError('Failed to start voice recognition. Please try again.');
      }
    }
  }, [voiceSupported, isVoiceEnabled, getRecognitionLang, confidenceThreshold, continuousDictation, silenceTimeoutMs]);

  // Stop voice recognition
  const stopListening = useCallback(() => {
    if (recognitionRef.current && isListening) {
      recognitionRef.current.stop();
      // Commit any pending text immediately
      const finalText = recognizedAccumRef.current.trim();
      if (finalText) {
        const usedLang = recognitionRef.current?.lang || getRecognitionLang();
        recentVoiceSendsRef.current.unshift({ content: finalText, lang: usedLang, ts: Date.now() });
        recentVoiceSendsRef.current = recentVoiceSendsRef.current.slice(0, 6);
        console.log('Manual stop: committing voice input', finalText);
        handleSendMessage(finalText);
        recognizedAccumRef.current = '';
        setInputValue('');
      }
      if (commitTimerRef.current) {
        window.clearTimeout(commitTimerRef.current);
        commitTimerRef.current = null;
      }
    }
  }, [isListening]);

  // Initialize chat session (same as original)
  const initializeChat = React.useCallback(async () => {
    try {
      setConnectionStatus('connecting');

      await new Promise(resolve => requestAnimationFrame(resolve));

      try {
        const agentType = getAgentTypeFor(selectedAgentId);
        console.log(`[CHAT PANEL] Creating session with agentType: "${agentType}" for agentId: ${selectedAgentId}`);
        const { session_id } = await agentChatService.createSession(agentType);
        console.log(`[CHAT PANEL] Session created with ID: ${session_id}`);
        setSessionId(session_id);
        sessionIdRef.current = session_id;

        // Ensure Pydantic docs are available when using Pydantic AI (best-effort)
        if (selectedAgentId === 'pydantic-ai' && !ensuredPydanticKBRef.current) {
          ensuredPydanticKBRef.current = true;
          try {
            const items = await knowledgeBaseService.getKnowledgeItems({ search: 'Pydantic Documentation - Llms-Full.Txt', per_page: 5 });
            const found = items.items?.some(i => i.title?.toLowerCase().includes('pydantic') && i.title.toLowerCase().includes('llms-full'));
            if (!found) {
              await knowledgeBaseService.crawlUrl({
                url: 'https://ai.pydantic.dev/llms-full.txt',
                knowledge_type: 'technical',
                tags: ['pydantic', 'llmstxt'],
                max_depth: 0,
              });
            }
          } catch (e) {
            console.warn('Pydantic KB ensure failed (non-fatal):', e);
          }
        }

        try {
          const history = await agentChatService.getChatHistory(session_id);
          console.log(`[CHAT PANEL] Loaded chat history:`, history);
          setMessages(history || []);
        } catch (error) {
          console.error('Failed to load chat history:', error);
          setMessages([]);
        }

        try {
          await agentChatService.streamMessages(
            session_id,
            (message: ChatMessage) => {
              // Only update state here; speaking happens in useEffect below
              setMessages(prev => {
                if (prev.some(msg => msg.id === message.id)) {
                  return prev;
                }
                return [...prev, message];
              });

              setConnectionError(null);
              setConnectionStatus('online');
            },
            (error: Error) => {
              console.error('Message streaming error:', error);
              setConnectionStatus('offline');
              setConnectionError('Chat service is offline. Messages will not be received.');
            }
          );
        } catch (error) {
          console.error('Failed to start message streaming:', error);
        }

        setIsInitialized(true);
        setConnectionStatus('online');
        setConnectionError(null);

      } catch (error) {
        console.error('Failed to create session:', error);
        setConnectionError('Unable to start chat session. Please try again.');
        setConnectionStatus('offline');
      }
    } catch (error) {
      console.error('Chat initialization failed:', error);
      setConnectionError('Chat initialization failed. Please refresh the page.');
      setConnectionStatus('offline');
    }
  }, [isVoiceEnabled, speakText, selectedAgentId]);

  // Speak when new agent messages arrive, using current isVoiceEnabled
  useEffect(() => {
    if (!isVoiceEnabled || !messages?.length) return;

    const last = messages[messages.length - 1];
    const sender = String((last as any)?.sender || (last as any)?.role || '').toLowerCase();
    // Stricter detection: treat only known assistant-like senders as agent
    const agentAliases = ['agent', 'assistant', 'archon'];
    const isAgentMsg = agentAliases.includes(sender);

    const msgId = (last as any).id ?? `${(last as any).timestamp ?? Date.now()}-${messages.length}`;
    if (isAgentMsg && (last as any).content && lastSpokenIdRef.current !== msgId) {
      console.log('[TTS] Speaking agent message:', {
        id: msgId,
        sender,
        text: String((last as any).content).slice(0, 80) + '...'
      });
      speakText(String((last as any).content));
      lastSpokenIdRef.current = msgId;
    }
  }, [messages, isVoiceEnabled, speakText]);

  // Warm up speech synthesis when voice is enabled to satisfy autoplay policies
  useEffect(() => {
    if (!isVoiceEnabled || !window.speechSynthesis) return;
    const u = new SpeechSynthesisUtterance(' ');
    u.volume = 0;
    try {
      window.speechSynthesis.speak(u);
    } catch (e) {
      // Intentionally no-op: warm-up failures should not crash UI
      console.warn('TTS warm-up failed:', e);
    }
  }, [isVoiceEnabled]);

  // Handle sending messages (enhanced for voice)
  const handleSendMessage = async (messageText?: string) => {
    const textToSend = messageText || inputValue.trim();
    if (!textToSend || !sessionId) return;

    try {
      // Add context including voice information; tailor for selected agent
      const base = {
        input_method: messageText ? 'voice' : 'text',
        voice_enabled: isVoiceEnabled
      } as Record<string, any>;
      const context = (() => {
        if (selectedAgentId === 'profesora-maria') {
          return {
            ...base,
            student_level: 'intermediate',
            conversation_mode: 'casual',
          };
        }
        if (selectedAgentId === 'pydantic-ai') {
          return {
            ...base,
            domain: 'pydantic-ai',
            knowledge_source: 'llmstxt',
            dataset_hint: 'Pydantic Documentation - Llms-Full.Txt',
            // Hint RAG to focus on Pydantic sources
            source_filter: 'pydantic|ai.pydantic.dev|llms-full',
          };
        }
        return base;
      })();

      await agentChatService.sendMessage(sessionId, {
        message: textToSend,
        context,
        agentId: selectedAgentId,
      });

      if (!messageText) {
        setInputValue('');
      }

    } catch (error) {
      console.error('Failed to send message:', error);
      setConnectionError('Failed to send message. Please try again.');
    }
  };

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping, streamingMessage]);

  // Initialize on mount
  useEffect(() => {
    if (!isInitialized) {
      initializeChat();
    }
  }, [initializeChat, isInitialized]);

  // Re-initialize when agent changes
  const prevAgentIdRef = useRef<string | null>(null);
  useEffect(() => {
    if (prevAgentIdRef.current && prevAgentIdRef.current !== selectedAgentId) {
      if (sessionIdRef.current) {
        agentChatService.stopStreaming(sessionIdRef.current);
      }
      setMessages([]);
      setSessionId(null);
      setIsInitialized(false);
      setConnectionStatus('connecting');
      initializeChat();
    }
    prevAgentIdRef.current = selectedAgentId;
  }, [selectedAgentId, initializeChat]);

  const formatTime = (date: Date | string) => {
    const d = typeof date === 'string' ? new Date(date) : date;
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div
      ref={chatPanelRef}
      className="fixed inset-y-0 right-0 z-40 flex flex-col h-full backdrop-blur-sm bg-white/70 dark:bg-black/50 border-l border-gray-200 dark:border-gray-700 shadow-2xl"
      style={{ width: `${width}px` }}
      {...props}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700 bg-white/80 dark:bg-black/40">
        <div className="flex items-center gap-3">
          <img src="/logo-neon.png" alt="Archon" className="w-6 h-6" />
          <AgentSwitcher label="Agent" />
          {isVoiceEnabled && (
            <span className="text-xs bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 px-2 py-1 rounded-full">
              Voice
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {props.onClose && (
            <button
              onClick={props.onClose}
              className="p-2 rounded-full bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
              title="Close chat"
            >
              <X className="w-4 h-4" />
            </button>
          )}
          {/* Voice toggle */}
          {voiceSupported && (
            <button
              onClick={() => {
                const newVoiceState = !isVoiceEnabled;
                console.log('Voice toggle clicked. Changing from', isVoiceEnabled, 'to', newVoiceState);
                setIsVoiceEnabled(newVoiceState);
              }}
              className={`p-2 rounded-full transition-colors ${
                isVoiceEnabled
                  ? 'bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400'
                  : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
              }`}
              title={isVoiceEnabled ? 'Disable voice' : 'Enable voice'}
            >
              {isVoiceEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
            </button>
          )}
          {/* Settings popover */}
          {voiceSupported && isVoiceEnabled && (
            <Popover.Root>
              <Popover.Trigger asChild>
                <button
                  className="ml-2 p-2 rounded-full bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
                  title="Voice settings"
                >
                  <SlidersHorizontal className="w-4 h-4" />
                </button>
              </Popover.Trigger>
              <Popover.Portal>
                <Popover.Content
                  side="bottom"
                  align="end"
                  sideOffset={8}
                  className="z-50 w-72 rounded-lg border border-gray-200 dark:border-gray-700 bg-white/95 dark:bg-zinc-900/95 shadow-xl p-3 backdrop-blur"
                >
                  <div className="space-y-3 text-sm">
                    <div>
                      <div className="text-xs font-medium text-gray-700 dark:text-gray-200 mb-1">Spanish voice</div>
                      <select
                        value={selectedVoiceName || ''}
                        onChange={(e) => {
                          const name = e.target.value || null;
                          setSelectedVoiceName(name);
                          if (name) localStorage.setItem('archonVoiceName', name);
                          else localStorage.removeItem('archonVoiceName');
                        }}
                        className="w-full text-xs px-2 py-1 rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-zinc-800 text-gray-800 dark:text-gray-100"
                      >
                        {availableVoices
                          .filter(v => (v.lang || '').toLowerCase().startsWith('es'))
                          .sort((a, b) => a.name.localeCompare(b.name))
                          .map(v => (
                            <option key={v.name} value={v.name}>
                              {v.name} ({v.lang})
                            </option>
                          ))}
                      </select>
                    </div>
                <div>
                  <div className="text-xs font-medium text-gray-700 dark:text-gray-200 mb-1">Speech input</div>
                  <select
                    value={recognitionMode}
                    onChange={(e) => setRecognitionMode(e.target.value as RecognitionMode)}
                    className="w-full text-xs px-2 py-1 rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-zinc-800 text-gray-800 dark:text-gray-100"
                  >
                    <option value="auto">Auto (ES if preferred)</option>
                    <option value="es-MX">Español (México)</option>
                    <option value="es-ES">Español (España)</option>
                    <option value="en-US">English (US)</option>
                  </select>
                </div>
                <div>
                  <label className="flex items-center gap-2 text-xs text-gray-700 dark:text-gray-200">
                    <input
                      type="checkbox"
                      checked={continuousDictation}
                      onChange={(e) => setContinuousDictation(e.target.checked)}
                    />
                    Continuous dictation (beta)
                  </label>
                </div>
                {continuousDictation && (
                  <div>
                    <div className="flex items-center justify-between text-xs font-medium text-gray-700 dark:text-gray-200 mb-1">
                      <span>Silence timeout</span>
                      <span className="opacity-70">{silenceTimeoutMs} ms</span>
                    </div>
                    <input
                      type="range"
                      min={300}
                      max={3000}
                      step={50}
                      value={silenceTimeoutMs}
                      onChange={(e) => setSilenceTimeoutMs(parseInt(e.target.value, 10))}
                      className="w-full"
                    />
                  </div>
                )}
                    <div>
                      <div className="flex items-center justify-between text-xs font-medium text-gray-700 dark:text-gray-200 mb-1">
                        <span>ASR confidence</span>
                        <span className="opacity-70">{confidenceThreshold.toFixed(2)}</span>
                      </div>
                      <input
                        type="range"
                        min={0}
                        max={1}
                        step={0.01}
                        value={confidenceThreshold}
                        onChange={(e) => setConfidenceThreshold(parseFloat(e.target.value))}
                        className="w-full"
                      />
                    </div>
                  </div>
                  <Popover.Arrow className="fill-white dark:fill-zinc-900" />
                </Popover.Content>
              </Popover.Portal>
            </Popover.Root>
          )}
        </div>
      </div>

      {/* Connection status */}
      {connectionError && (
        <div className="p-2 bg-red-100 dark:bg-red-900/30 border-b border-red-200 dark:border-red-800">
          <p className="text-red-700 dark:text-red-400 text-sm">{connectionError}</p>
        </div>
      )}

      {/* Voice error */}
      {voiceError && (
        <div className="p-2 bg-yellow-100 dark:bg-yellow-900/30 border-b border-yellow-200 dark:border-yellow-800">
          <p className="text-yellow-700 dark:text-yellow-400 text-sm">{voiceError}</p>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message, index) => (
          <div key={message.id || index} className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] rounded-lg p-3 ${
              message.sender === 'user'
                ? 'bg-blue-500 text-white ml-auto'
                : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white mr-auto'
            }`}>
              <div className="flex items-center mb-1">
                {message.sender === 'agent' && (
                  <img src="/logo-neon.png" alt="Archon" className="w-4 h-4 mr-1" />
                )}
                <span className="text-xs opacity-70">
                  {formatTime(message.timestamp)}
                </span>
                {/* Show recognized language for recent voice user messages */}
                {message.sender === 'user' && (() => {
                  const ts = typeof message.timestamp === 'string' ? new Date(message.timestamp).getTime() : (message.timestamp as Date).getTime();
                  const match = recentVoiceSendsRef.current.find(entry => entry.content === message.content && Math.abs(ts - entry.ts) < 30000);
                  return match ? (
                    <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-blue-600/20 text-blue-200 border border-blue-500/40" title="Speech input language">
                      ASR: {match.lang}
                    </span>
                  ) : null;
                })()}
              </div>
              <p className="text-sm whitespace-pre-wrap">{message.content}</p>
            </div>
          </div>
        ))}

        {/* Typing indicator */}
        {isTyping && (
          <div className="flex justify-start">
            <div className="bg-gray-100 dark:bg-gray-800 rounded-lg p-3 mr-auto">
              <ArchonLoadingSpinner />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="p-4 border-t border-gray-200 dark:border-gray-700 bg-white/80 dark:bg-black/40">
        <div className="flex items-center gap-2">
          {/* Voice button */}
          {isVoiceEnabled && (
            <Tooltip.Provider delayDuration={200}>
              <Tooltip.Root>
                <Tooltip.Trigger asChild>
                  <button
                    onClick={() => {
                      console.log('Voice button clicked. Currently listening:', isListening);
                      if (isListening) {
                        console.log('Stopping voice recognition...');
                        stopListening();
                      } else {
                        console.log('Starting voice recognition...');
                        startListening();
                      }
                    }}
                    disabled={connectionStatus !== 'online'}
                    className={`p-2 rounded-full transition-all duration-200 ${
                      isListening
                        ? 'bg-red-500 text-white animate-pulse'
                        : 'bg-blue-500 text-white hover:bg-blue-600'
                    } disabled:opacity-50 disabled:cursor-not-allowed`}
                  >
                    {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                  </button>
                </Tooltip.Trigger>
                <Tooltip.Content side="top" align="center" sideOffset={6} className="rounded bg-gray-900 text-white px-2 py-1 text-xs shadow">
                  {(() => {
                    const preferred = getRecognitionLang();
                    const modeLabel = recognitionMode === 'auto' ? `Auto → ${preferred}` : preferred;
                    return `Mic: ${modeLabel}${isListening ? ' (listening)' : ''}`;
                  })()}
                  <Tooltip.Arrow className="fill-gray-900" />
                </Tooltip.Content>
              </Tooltip.Root>
            </Tooltip.Provider>
          )}

          {/* Text input */}
          <div className="flex-1 relative">
            <input
              type="text"
              value={inputValue}
              onChange={e => setInputValue(e.target.value)}
                placeholder={
                  connectionStatus === 'offline' ? 'Chat is offline...' :
                  connectionStatus === 'connecting' ? 'Connecting...' :
                  isVoiceEnabled ? `Speak or type to ${selectedAgent?.label || 'Agent'}...` :
                  `Message ${selectedAgent?.label || 'Agent'}...`
                }
              disabled={connectionStatus !== 'online'}
              className="w-full p-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
              onKeyDown={e => {
                if (e.key === 'Enter') handleSendMessage();
              }}
            />
          </div>

          {/* Send button */}
          <button
            onClick={() => handleSendMessage()}
            disabled={connectionStatus !== 'online' || isTyping || !inputValue.trim()}
            className="p-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            title="Send message"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>

        {/* Voice status */}
        {isVoiceEnabled && (
          <div className="mt-2 flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
            <span>
              {isListening ? 'Escuchando...' : isSpeaking ? 'Hablando...' : 'Presiona el micrófono para hablar'}
            </span>
            {voiceSupported && (
              <span className="text-green-600 dark:text-green-400">Voice ready</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
