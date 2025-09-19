"""
Spanish Tutor Agent - Interactive Spanish Language Learning with PydanticAI

This agent provides conversational Spanish tutoring including:
- Interactive conversations in Spanish
- Grammar correction and explanations
- Vocabulary building and practice
- Cultural context and tips
- Adaptive difficulty levels
- Progress tracking
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from .base_agent import ArchonDependencies, BaseAgent

logger = logging.getLogger(__name__)


@dataclass
class SpanishTutorDependencies(ArchonDependencies):
    """Dependencies for Spanish tutor operations."""

    student_level: Literal["beginner", "intermediate", "advanced"] = "beginner"
    conversation_mode: Literal["casual", "formal", "business", "travel", "cultural"] = "casual"
    focus_area: str | None = None  # grammar, vocabulary, pronunciation, conversation
    previous_context: str | None = None  # Previous conversation context
    session_id: str | None = None  # Session identifier for context persistence
    conversation_flow: str | None = None  # Current conversation flow (greetings, shopping, etc.)
    student_performance: dict[str, Any] | None = None  # Performance tracking data
    progress_callback: Any | None = None
    input_method: Literal["text", "voice"] = "text"  # How the student is communicating
    voice_enabled: bool = False  # Whether voice responses should be optimized for speech


class SpanishResponse(BaseModel):
    """Structured output for Spanish tutor responses."""

    spanish_text: str = Field(description="The response in Spanish")
    english_translation: str = Field(description="English translation of the response")
    grammar_notes: list[str] = Field(description="Grammar explanations and tips")
    vocabulary_highlights: list[dict[str, str]] = Field(
        description="Key vocabulary with definitions: [{'word': 'hola', 'definition': 'hello', 'context': 'greeting', 'pronunciation': 'OH-lah'}]"
    )
    cultural_notes: list[str] = Field(description="Cultural context and insights")
    difficulty_level: str = Field(description="Assessed difficulty level of the interaction")
    corrections: list[dict[str, str]] = Field(
        description="Corrections for student input: [{'error': 'Como esta', 'correction': 'Cómo está', 'explanation': 'Missing accent mark'}]"
    )
    encouragement: str = Field(description="Encouraging feedback for the student")
    next_topic_suggestion: str | None = Field(description="Suggested next topic or question")
    conversation_flow_step: str | None = Field(description="Current step in the conversation flow")
    performance_assessment: dict[str, Any] | None = Field(description="Assessment of student's current performance")
    voice_optimized_response: str | None = Field(description="Version of spanish_text optimized for text-to-speech (shorter, clearer pronunciation)")
    pronunciation_tips: list[str] = Field(description="Tips for pronunciation when using voice input", default_factory=list)


class ConversationFlow(BaseModel):
    """Structured conversation flow for specific scenarios."""

    flow_name: str = Field(description="Name of the conversation flow")
    scenario: str = Field(description="Description of the scenario")
    steps: list[dict[str, Any]] = Field(description="Ordered steps in the conversation")
    difficulty_adaptations: dict[str, dict[str, Any]] = Field(description="Adaptations for different levels")
    vocabulary_focus: list[str] = Field(description="Key vocabulary for this flow")
    grammar_focus: list[str] = Field(description="Grammar points to emphasize")


class StudentSession(BaseModel):
    """Student session data for context persistence."""

    session_id: str
    student_level: str
    conversation_history: list[dict[str, str]] = []
    performance_data: dict[str, Any] = {}
    learned_vocabulary: list[str] = []
    mastered_grammar: list[str] = []
    areas_for_improvement: list[str] = []
    session_start: str
    last_interaction: str


class SpanishTutorAgent(BaseAgent[SpanishTutorDependencies, str]):
    """
    Spanish Tutor Agent for interactive language learning.

    Provides conversational practice, grammar instruction, vocabulary building,
    and cultural insights adapted to the student's level and interests.
    """

    def __init__(self, **kwargs):
        # Extract model from kwargs or use default
        model = kwargs.pop("model", "openai:gpt-4o")
        super().__init__(
            model=model,
            name="SpanishTutor",
            **kwargs
        )

    def _create_agent(self, **kwargs) -> Agent:
        """Create the PydanticAI agent with Spanish tutor capabilities."""
        agent = Agent(
            model=self.model,
            deps_type=SpanishTutorDependencies,
            system_prompt=self.get_system_prompt(),
            **kwargs
        )

        # Register tools inline during agent creation
        @agent.tool
        async def analyze_grammar(ctx: RunContext[SpanishTutorDependencies], spanish_text: str) -> dict[str, Any]:
            """Analyze Spanish text for grammar errors and provide corrections."""
            return self.check_spanish_grammar(spanish_text)

        @agent.tool
        async def get_vocabulary(ctx: RunContext[SpanishTutorDependencies], topic: str) -> list[dict[str, str]]:
            """Get relevant vocabulary for a specific topic at the student's level."""
            return self.suggest_vocabulary(topic, ctx.deps.student_level)

        @agent.tool
        async def start_conversation_flow(ctx: RunContext[SpanishTutorDependencies], flow_name: str) -> dict[str, Any]:
            """Start a structured conversation flow for specific scenarios."""
            return await self.initiate_conversation_flow(flow_name, ctx.deps)

        @agent.tool
        async def get_session_context(ctx: RunContext[SpanishTutorDependencies]) -> dict[str, Any]:
            """Retrieve conversation history and context for the current session."""
            return await self.load_session_context(ctx.deps.session_id) if ctx.deps.session_id else {}

        @agent.tool
        async def update_student_progress(ctx: RunContext[SpanishTutorDependencies],
                                        performance_data: dict[str, Any]) -> dict[str, str]:
            """Update student's learning progress and performance metrics."""
            return await self.track_student_progress(ctx.deps.session_id, performance_data)

        @agent.tool
        async def get_pronunciation_guide(ctx: RunContext[SpanishTutorDependencies], word: str) -> dict[str, str]:
            """Get pronunciation guide and phonetic breakdown for a Spanish word."""
            return self.get_word_pronunciation(word)

        @agent.tool
        async def suggest_next_lesson(ctx: RunContext[SpanishTutorDependencies]) -> dict[str, Any]:
            """Suggest next lesson or topic based on student's progress and performance."""
            return await self.recommend_next_lesson(ctx.deps)

        return agent

    def get_system_prompt(self) -> str:
        """Get the system prompt for the Spanish tutor."""
        return """
You are Profesora María, an enthusiastic and encouraging Spanish tutor with expertise in:
- Mexican, Spanish, and Latin American Spanish dialects
- Grammar instruction tailored to English speakers
- Cultural insights from Spanish-speaking countries
- Interactive conversation practice
- Vocabulary building through context
- Voice-based learning and pronunciation coaching

CORE TEACHING PRINCIPLES:
1. **Encouraging Approach**: Always be positive and supportive. Celebrate progress, no matter how small.
2. **Practical Learning**: Focus on useful, real-world Spanish that students can use immediately.
3. **Cultural Integration**: Weave cultural insights naturally into lessons.
4. **Error Correction**: Gently correct mistakes with clear explanations, not criticism.
5. **Adaptive Difficulty**: Match your language complexity to the student's level.
6. **Voice Awareness**: Adapt responses based on whether student is using voice or text input.

RESPONSE STRUCTURE:
- Respond primarily in Spanish, adapted to the student's level
- When voice_enabled=True, keep responses conversational and speak-friendly (shorter, clearer)
- Provide English translations in parentheses to ensure comprehension
- Highlight 2-4 key vocabulary words with definitions and pronunciation tips
- Include relevant grammar notes when applicable
- Add cultural context when relevant
- Offer gentle corrections for any errors with detailed explanations
- For voice input, include pronunciation feedback and tips
- Track conversation flow progress if using structured scenarios
- Assess student performance and adjust difficulty accordingly
- End with encouragement and a suggestion for continuing the conversation
- Use tools to enhance learning experience (pronunciation guides, progress tracking)
- Format your response as natural conversation, not structured data

VOICE INPUT ADAPTATIONS:
When input_method="voice":
- Acknowledge that you heard them speak ("Te escuché decir...")
- Provide pronunciation feedback if there might be common mistakes
- Be more conversational and immediate in your responses
- Include pronunciation tips in brackets: [proh-noon-see-AH-see-ohn]
- Focus on spoken Spanish patterns and rhythm

LEVEL ADAPTATIONS:
- **Beginner**: Simple present tense, basic vocabulary, short sentences
- **Intermediate**: Mixed tenses, more complex vocabulary, longer conversations
- **Advanced**: Complex grammar, idiomatic expressions, nuanced cultural discussions

CONVERSATION MODES:
- **Casual**: Everyday topics, informal language, relaxed tone
- **Formal**: Professional situations, formal address (usted), business vocabulary
- **Business**: Work-related scenarios, professional communication
- **Travel**: Tourist situations, directions, ordering food, hotels
- **Cultural**: Traditions, holidays, history, customs of Spanish-speaking countries

Always maintain an encouraging, patient tone while providing substantive learning opportunities.
Remember to check the context for voice_enabled and input_method to adapt your teaching style accordingly.
"""

    @staticmethod
    def check_spanish_grammar(spanish_text: str) -> dict[str, Any]:
        """
        Enhanced tool to analyze Spanish grammar and provide detailed corrections.
        """
        corrections = []
        grammar_suggestions = []

        text_lower = spanish_text.lower().strip()

        # Enhanced common mistakes with detailed explanations
        grammar_patterns = {
            "como esta": {
                "correction": "cómo está",
                "explanation": "Question words need accent marks. 'Cómo' (how) vs 'como' (like/as)",
                "rule": "Interrogative pronouns require accent marks"
            },
            "muy bien gracias": {
                "correction": "muy bien, gracias",
                "explanation": "Use commas to separate phrases",
                "rule": "Punctuation in conversational responses"
            },
            "me llamo es": {
                "correction": "me llamo",
                "explanation": "'Me llamo' already means 'I am called', don't add 'es'",
                "rule": "Reflexive verb construction"
            },
            "estar bien": {
                "correction": "estoy bien",
                "explanation": "Conjugate 'estar' to 'estoy' for first person singular",
                "rule": "Verb conjugation - present tense"
            },
            "tener anos": {
                "correction": "tener años",
                "explanation": "'Años' (years) needs the ñ. 'Anos' means something very different!",
                "rule": "Accent marks change meaning completely"
            },
            "de donde": {
                "correction": "de dónde",
                "explanation": "Question phrase 'de dónde' (from where) needs accent on 'dónde'",
                "rule": "Interrogative phrases require accents"
            }
        }

        # Check for patterns
        for pattern, correction_info in grammar_patterns.items():
            if pattern in text_lower:
                corrections.append({
                    "error": pattern,
                    "correction": correction_info["correction"],
                    "explanation": correction_info["explanation"],
                    "grammar_rule": correction_info["rule"]
                })

        # Additional grammar analysis
        if "que" in text_lower and "qué" not in spanish_text:
            grammar_suggestions.append({
                "suggestion": "Consider if 'que' should be 'qué' (with accent) for questions",
                "rule": "Accent marks distinguish question words from relative pronouns"
            })

        if text_lower.endswith("?") and not any(word in text_lower for word in ["cómo", "qué", "cuándo", "dónde", "por qué"]):
            grammar_suggestions.append({
                "suggestion": "Questions often start with question words (cómo, qué, cuándo, etc.)",
                "rule": "Question formation in Spanish"
            })

        return {
            "corrections": corrections,
            "grammar_suggestions": grammar_suggestions,
            "analysis": f"Analyzed text: '{spanish_text}'",
            "complexity_score": len(spanish_text.split()),
            "error_count": len(corrections)
        }

    @staticmethod
    def suggest_vocabulary(topic: str, level: str) -> list[dict[str, str]]:
        """Enhanced tool to suggest relevant vocabulary with pronunciation guides."""

        vocabulary_sets = {
            "greetings": {
                "beginner": [
                    {"word": "hola", "definition": "hello", "context": "informal greeting", "pronunciation": "OH-lah", "tips": "Most common greeting"},
                    {"word": "adiós", "definition": "goodbye", "context": "general farewell", "pronunciation": "ah-DYOHS", "tips": "Formal way to say goodbye"},
                    {"word": "gracias", "definition": "thank you", "context": "expressing gratitude", "pronunciation": "GRAH-see-ahs", "tips": "Essential politeness word"},
                    {"word": "por favor", "definition": "please", "context": "making requests", "pronunciation": "por fah-VOR", "tips": "Always use when asking for something"},
                ],
                "intermediate": [
                    {"word": "buenos días", "definition": "good morning", "context": "formal morning greeting", "pronunciation": "BWAY-nohs DEE-ahs", "tips": "Used until noon"},
                    {"word": "mucho gusto", "definition": "nice to meet you", "context": "introductions", "pronunciation": "MOO-choh GOOS-toh", "tips": "Response to introductions"},
                    {"word": "hasta luego", "definition": "see you later", "context": "casual farewell", "pronunciation": "AHS-tah LWAY-goh", "tips": "Less formal than adiós"},
                    {"word": "¿cómo está?", "definition": "how are you?", "context": "formal inquiry", "pronunciation": "KOH-moh ehs-TAH", "tips": "Formal version with usted"},
                ],
                "advanced": [
                    {"word": "encantado/a", "definition": "delighted to meet you", "context": "formal introduction", "pronunciation": "en-kahn-TAH-doh", "tips": "Agree gender with speaker"},
                    {"word": "que tengas buen día", "definition": "have a good day", "context": "parting wish", "pronunciation": "keh TEHN-gahs BWAYN DEE-ah", "tips": "Subjunctive mood expression"},
                    {"word": "me da mucho gusto conocerle", "definition": "I'm very pleased to meet you", "context": "very formal introduction", "pronunciation": "meh dah MOO-choh GOOS-toh koh-noh-SEHR-leh", "tips": "Very polite, formal situations"},
                ]
            },
            "food": {
                "beginner": [
                    {"word": "agua", "definition": "water", "context": "basic drink", "pronunciation": "AH-gwah", "tips": "Essential word, feminine noun"},
                    {"word": "pan", "definition": "bread", "context": "basic food", "pronunciation": "pahn", "tips": "Masculine noun"},
                    {"word": "pollo", "definition": "chicken", "context": "common protein", "pronunciation": "POH-yoh", "tips": "Double L makes 'y' sound"},
                    {"word": "arroz", "definition": "rice", "context": "staple food", "pronunciation": "ah-ROHS", "tips": "Masculine noun, very common"},
                ],
                "intermediate": [
                    {"word": "desayuno", "definition": "breakfast", "context": "morning meal", "pronunciation": "deh-sah-YOO-noh", "tips": "From 'des-ayunar' (break fast)"},
                    {"word": "almuerzo", "definition": "lunch", "context": "midday meal", "pronunciation": "ahl-MWEHR-soh", "tips": "Main meal in many Spanish countries"},
                    {"word": "cena", "definition": "dinner", "context": "evening meal", "pronunciation": "SEH-nah", "tips": "Often eaten later than US dinner"},
                    {"word": "merienda", "definition": "snack/afternoon tea", "context": "afternoon meal", "pronunciation": "meh-ree-EHN-dah", "tips": "Important meal in Spanish culture"},
                ],
                "advanced": [
                    {"word": "aperitivo", "definition": "appetizer", "context": "pre-meal course", "pronunciation": "ah-peh-ree-TEE-voh", "tips": "Often accompanied by drinks"},
                    {"word": "platillo", "definition": "dish/course", "context": "formal dining term", "pronunciation": "plah-TEE-yoh", "tips": "Diminutive of 'plato'"},
                    {"word": "maridaje", "definition": "wine pairing", "context": "fine dining", "pronunciation": "mah-ree-DAH-heh", "tips": "Sophisticated culinary term"},
                ]
            },
            "shopping": {
                "beginner": [
                    {"word": "tienda", "definition": "store", "context": "shopping location", "pronunciation": "tee-EHN-dah", "tips": "General word for shop"},
                    {"word": "dinero", "definition": "money", "context": "payment", "pronunciation": "dee-NEH-roh", "tips": "Essential for shopping"},
                    {"word": "precio", "definition": "price", "context": "cost inquiry", "pronunciation": "PREH-see-oh", "tips": "Always useful to know"},
                ],
                "intermediate": [
                    {"word": "descuento", "definition": "discount", "context": "savings", "pronunciation": "dehs-KWAYN-toh", "tips": "Look for 'ofertas' (sales)"},
                    {"word": "efectivo", "definition": "cash", "context": "payment method", "pronunciation": "eh-fehk-TEE-voh", "tips": "vs tarjeta (card)"},
                    {"word": "recibo", "definition": "receipt", "context": "proof of purchase", "pronunciation": "reh-SEE-boh", "tips": "Important for returns"},
                ],
                "advanced": [
                    {"word": "reembolso", "definition": "refund", "context": "returns", "pronunciation": "reh-ehm-BOHL-soh", "tips": "Know return policies"},
                    {"word": "garantía", "definition": "warranty", "context": "product protection", "pronunciation": "gah-rahn-TEE-ah", "tips": "Important for electronics"},
                ]
            }
        }

        # Default to greetings if topic not found
        topic_vocab = vocabulary_sets.get(topic.lower(), vocabulary_sets["greetings"])
        level_vocab = topic_vocab.get(level, topic_vocab["beginner"])

        return level_vocab


    async def start_conversation(self, deps: SpanishTutorDependencies) -> str:
        """Start a new Spanish conversation session with enhanced context."""

        # Initialize or load session context
        if deps.session_id:
            session_context = await self.load_session_context(deps.session_id)
            if session_context.get("returning_student"):
                greeting_prompts = {
                    "beginner": "¡Hola de nuevo! Me alegra verte otra vez. Hoy vamos a continuar practicando.",
                    "intermediate": "¡Bienvenido/a otra vez! ¿Cómo te fue con lo que practicamos la última vez?",
                    "advanced": "¡Qué gusto verte de nuevo! Espero que hayas tenido oportunidad de practicar lo que vimos."
                }
            else:
                greeting_prompts = {
                    "beginner": "¡Hola! Soy Profesora María. ¿Cómo te llamas?",
                    "intermediate": "¡Buenos días! Me alegra conocerte. ¿Cómo has estado practicando tu español?",
                    "advanced": "¡Qué gusto conocerte! ¿Qué te gustaría practicar en español hoy?"
                }
        else:
            greeting_prompts = {
                "beginner": "¡Hola! Soy Profesora María. ¿Cómo te llamas?",
                "intermediate": "¡Buenos días! Me alegra conocerte. ¿Cómo has estado practicando tu español?",
                "advanced": "¡Qué gusto conocerte! ¿Qué te gustaría practicar en español hoy?"
            }

        initial_prompt = greeting_prompts.get(deps.student_level, greeting_prompts["beginner"])

        # Add mode-specific context with more detail
        mode_contexts = {
            "business": " Hoy vamos a practicar español para situaciones profesionales y de negocios.",
            "travel": " Hoy vamos a practicar español útil para viajar y turismo.",
            "cultural": " Hoy vamos a explorar la cultura hispana mientras practicamos el idioma.",
            "formal": " Hoy vamos a practicar español formal y protocolo.",
            "casual": " Hoy vamos a tener una conversación relajada y natural."
        }

        if deps.conversation_mode in mode_contexts:
            initial_prompt += mode_contexts[deps.conversation_mode]

        # Add conversation flow if specified
        if deps.conversation_flow:
            flow_context = await self.get_flow_context(deps.conversation_flow)
            initial_prompt += f" {flow_context.get('introduction', '')}"

        return await self.run(initial_prompt, deps)

    async def continue_conversation(
        self,
        student_input: str,
        deps: SpanishTutorDependencies
    ) -> str:
        """Continue an ongoing conversation with enhanced context and assessment."""

        # Analyze student input for performance tracking
        grammar_analysis = self.check_spanish_grammar(student_input)

        # Build comprehensive context
        context = ""
        if deps.previous_context:
            context = f"Contexto previo: {deps.previous_context}\n\n"

        if deps.focus_area:
            context += f"Área de enfoque: {deps.focus_area}\n\n"

        if deps.conversation_flow:
            context += f"Flujo de conversación: {deps.conversation_flow}\n\n"

        # Add performance context for adaptive responses
        if grammar_analysis.get("error_count", 0) > 0:
            context += "El estudiante cometió algunos errores. Proporciona correcciones gentiles.\n\n"
        elif grammar_analysis.get("complexity_score", 0) > 5:
            context += "El estudiante está usando oraciones complejas. Puedes aumentar la dificultad.\n\n"

        # Enhanced prompt with assessment guidance
        prompt = f"""{context}El estudiante dice: '{student_input}'

Analiza su respuesta y:
1. Responde de manera apropiada para nivel {deps.student_level} en modo {deps.conversation_mode}
2. Corrige errores gentilmente si los hay
3. Destaca vocabulary nuevo o grammar points relevantes
4. Ajusta la dificultad según su performance
5. Mantén la conversación natural y engaging"""

        # Update session context if available
        if deps.session_id:
            await self.update_session_interaction(deps.session_id, student_input, grammar_analysis)

        return await self.run(prompt, deps)


    async def initiate_conversation_flow(self, flow_name: str, deps: SpanishTutorDependencies) -> dict[str, Any]:
        """Start a structured conversation flow for specific scenarios."""

        conversation_flows = {
            "restaurant": {
                "scenario": "Ordering food at a restaurant",
                "introduction": "Vamos a practicar pidiendo comida en un restaurante.",
                "steps": [
                    {"step": 1, "prompt": "Buenos días, bienvenido/a a nuestro restaurante. ¿Tiene una reserva?"},
                    {"step": 2, "prompt": "Perfecto, ¿qué le gustaría para beber?"},
                    {"step": 3, "prompt": "¿Y de plato principal?"},
                    {"step": 4, "prompt": "¿Algo de postre?"},
                    {"step": 5, "prompt": "Aquí tiene la cuenta."}
                ],
                "vocabulary": ["mesa", "carta", "cuenta", "mesero", "plato", "bebida"],
                "grammar": ["conditional tense", "polite requests", "me gustaría"]
            },
            "shopping": {
                "scenario": "Shopping for clothes",
                "introduction": "Vamos a practicar comprando ropa en una tienda.",
                "steps": [
                    {"step": 1, "prompt": "Buenos días, ¿en qué puedo ayudarle?"},
                    {"step": 2, "prompt": "¿Qué talla usa?"},
                    {"step": 3, "prompt": "¿Le gusta este color?"},
                    {"step": 4, "prompt": "¿Quiere probárselo?"},
                    {"step": 5, "prompt": "¿Cómo le queda?"}
                ],
                "vocabulary": ["talla", "color", "probador", "precio", "descuento"],
                "grammar": ["demonstratives", "object pronouns", "reflexive verbs"]
            },
            "directions": {
                "scenario": "Asking for and giving directions",
                "introduction": "Vamos a practicar pidiendo y dando direcciones.",
                "steps": [
                    {"step": 1, "prompt": "Disculpe, ¿podría ayudarme?"},
                    {"step": 2, "prompt": "¿Dónde está...?"},
                    {"step": 3, "prompt": "¿Está lejos de aquí?"},
                    {"step": 4, "prompt": "¿Cuánto tiempo se tarda?"},
                    {"step": 5, "prompt": "Muchas gracias por su ayuda."}
                ],
                "vocabulary": ["derecho", "izquierda", "cuadra", "semáforo", "esquina"],
                "grammar": ["prepositions of place", "estar vs ser", "question formation"]
            }
        }

        if flow_name not in conversation_flows:
            return {"error": f"Conversation flow '{flow_name}' not found"}

        flow = conversation_flows[flow_name]
        return {
            "flow_name": flow_name,
            "scenario": flow["scenario"],
            "introduction": flow["introduction"],
            "total_steps": len(flow["steps"]),
            "vocabulary_focus": flow["vocabulary"],
            "grammar_focus": flow["grammar"],
            "current_step": 1,
            "next_prompt": flow["steps"][0]["prompt"]
        }

    async def load_session_context(self, session_id: str) -> dict[str, Any]:
        """Load conversation history and context for a session."""
        try:
            # In a real implementation, this would load from database
            # For now, return a mock context
            return {
                "session_id": session_id,
                "returning_student": True,
                "conversation_count": 3,
                "last_topics": ["greetings", "food", "shopping"],
                "performance_summary": {
                    "grammar_accuracy": 0.75,
                    "vocabulary_retention": 0.80,
                    "conversation_fluency": 0.65
                },
                "areas_to_practice": ["verb conjugation", "accent marks"]
            }
        except Exception as e:
            logger.error(f"Error loading session context: {e}")
            return {}

    async def track_student_progress(self, session_id: str, performance_data: dict[str, Any]) -> dict[str, str]:
        """Track student's learning progress and performance."""
        try:
            # In a real implementation, this would save to database
            logger.info(f"Tracking progress for session {session_id}: {performance_data}")
            return {
                "status": "success",
                "message": "Progress updated successfully"
            }
        except Exception as e:
            logger.error(f"Error tracking progress: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    async def update_session_interaction(self, session_id: str, student_input: str, analysis: dict[str, Any]) -> None:
        """Update session with new interaction data."""
        try:
            interaction_data = {
                "timestamp": datetime.now().isoformat(),
                "student_input": student_input,
                "grammar_errors": analysis.get("error_count", 0),
                "complexity_score": analysis.get("complexity_score", 0)
            }
            logger.info(f"Session {session_id} interaction: {interaction_data}")
        except Exception as e:
            logger.error(f"Error updating session interaction: {e}")

    def get_word_pronunciation(self, word: str) -> dict[str, str]:
        """Get pronunciation guide for a Spanish word."""

        # Common pronunciation patterns for Spanish
        pronunciation_rules = {
            "ll": "y sound (like 'yes')",
            "ñ": "ny sound (like 'canyon')",
            "rr": "rolled R (tongue tap multiple times)",
            "j": "h sound (like English 'hat')",
            "v": "b sound (no difference from 'b')",
            "z": "th sound in Spain, s sound in Latin America"
        }

        # Simple phonetic mapping (would be more sophisticated in production)
        phonetic_map = {
            "hola": "OH-lah",
            "gracias": "GRAH-see-ahs",
            "adiós": "ah-DYOHS",
            "español": "ehs-pah-NYOHL",
            "muy": "mwee",
            "bien": "bee-EHN",
            "cómo": "KOH-moh",
            "está": "ehs-TAH",
            "señor": "seh-NYOHR",
            "señora": "seh-NYOH-rah"
        }

        pronunciation = phonetic_map.get(word.lower(), "Pronunciation guide not available")

        # Check for special patterns
        tips = []
        for pattern, tip in pronunciation_rules.items():
            if pattern in word.lower():
                tips.append(f"'{pattern}' makes {tip}")

        return {
            "word": word,
            "pronunciation": pronunciation,
            "tips": tips,
            "stress_note": "Spanish words typically stress the second-to-last syllable unless marked with an accent"
        }

    async def get_flow_context(self, flow_name: str) -> dict[str, str]:
        """Get context information for a conversation flow."""
        flow_contexts = {
            "restaurant": {"introduction": "Imagina que estás en un restaurante en España."},
            "shopping": {"introduction": "Estás en una tienda de ropa en México."},
            "directions": {"introduction": "Necesitas pedir direcciones en una ciudad nueva."}
        }
        return flow_contexts.get(flow_name, {})

    async def recommend_next_lesson(self, deps: SpanishTutorDependencies) -> dict[str, Any]:
        """Recommend next lesson based on student progress."""

        # This would analyze actual performance data in production
        level_recommendations = {
            "beginner": {
                "next_topics": ["numbers", "family members", "colors", "days of the week"],
                "grammar_focus": ["present tense", "articles", "gender agreement"],
                "conversation_flows": ["greetings", "introductions", "basic shopping"]
            },
            "intermediate": {
                "next_topics": ["past tense", "future plans", "opinions", "travel"],
                "grammar_focus": ["preterite vs imperfect", "subjunctive mood", "comparisons"],
                "conversation_flows": ["restaurant", "directions", "phone calls"]
            },
            "advanced": {
                "next_topics": ["cultural topics", "current events", "professional topics"],
                "grammar_focus": ["advanced subjunctive", "conditional perfect", "passive voice"],
                "conversation_flows": ["job interviews", "formal presentations", "debates"]
            }
        }

        recommendations = level_recommendations.get(deps.student_level, level_recommendations["beginner"])

        return {
            "student_level": deps.student_level,
            "recommended_topics": recommendations["next_topics"][:3],  # Top 3
            "grammar_to_practice": recommendations["grammar_focus"][:2],  # Top 2
            "suggested_flows": recommendations["conversation_flows"][:2],  # Top 2
            "motivation_tip": "¡Estás progresando muy bien! La práctica constante es la clave del éxito."
        }


# Initialize the agent
def create_spanish_tutor_agent() -> SpanishTutorAgent:
    """Factory function to create a configured Spanish tutor agent."""
    return SpanishTutorAgent()
