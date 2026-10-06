"""
VisionPilot Local Speech-to-Text Provider.

Provides 100% offline, privacy-first speech recognition leveraging Windows Native
Speech APIs (SAPI / InprocRecognizer) and SpeechRecognition audio processing.
Zero cloud network calls. Truthfully reports CPU inference runtime in accordance with Rule 3.
"""
import io
import wave
import tempfile
import os
from typing import Optional, Tuple, Dict, Any
from enum import Enum
from app.core.logger import logger
from app.core.exceptions import VoiceError
from app.voice.stt_provider import STTProvider, STTProviderMetadata

# Optional import of speech_recognition
try:
    import speech_recognition as sr
    _SR_AVAILABLE = True
except ImportError:
    sr = None
    _SR_AVAILABLE = False


class STTProviderStatus(str, Enum):
    UNAVAILABLE = "UNAVAILABLE"
    INITIALIZING = "INITIALIZING"
    READY = "READY"
    FAILED = "FAILED"


class LocalSTTProvider(STTProvider):
    """Local, offline Windows STT provider using SAPI and SpeechRecognition."""

    def __init__(self) -> None:
        self._initialized = False
        self._recognizer: Optional[Any] = None
        self._status: STTProviderStatus = STTProviderStatus.UNAVAILABLE if not _SR_AVAILABLE else STTProviderStatus.INITIALIZING
        self._metadata = STTProviderMetadata(
            provider_name="Windows Native Speech (SAPI)",
            model_name="Windows Desktop Speech Recognizer (English)",
            runtime="Win32 SAPI COM",
            accelerator="CPU",  # Truthful reporting per Rule 3
            local_processing=True,
            languages=["en-US"],
            is_available=_SR_AVAILABLE
        )

    @property
    def metadata(self) -> STTProviderMetadata:
        return self._metadata

    @property
    def status(self) -> STTProviderStatus:
        return self._status

    def initialize(self) -> bool:
        """Initializes the local speech recognizer."""
        if self._initialized:
            self._status = STTProviderStatus.READY
            return True

        self._status = STTProviderStatus.INITIALIZING
        if not _SR_AVAILABLE:
            logger.warning("speech_recognition library not available.")
            self._metadata.is_available = False
            self._status = STTProviderStatus.UNAVAILABLE
            return False

        try:
            self._recognizer = sr.Recognizer()
            self._recognizer.energy_threshold = 300
            self._recognizer.dynamic_energy_threshold = True
            self._recognizer.pause_threshold = 0.8
            self._initialized = True
            self._metadata.is_available = True
            self._status = STTProviderStatus.READY
            logger.info("Local STT provider initialized successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Local STT Provider: {e}")
            self._metadata.is_available = False
            self._status = STTProviderStatus.FAILED
            return False


    def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> Tuple[str, Optional[float]]:
        """
        Transcribes raw audio bytes into text.
        audio_data can be WAV formatted bytes or raw 16-bit PCM.
        """
        if not self._initialized:
            if not self.initialize():
                raise VoiceError("Speech recognition engine is unavailable.", "Speech recognition could not be initialized.")

        if not audio_data or len(audio_data) < 100:
            raise VoiceError("Audio buffer is empty or too short.", "No speech detected. Please try speaking again.")

        # Ensure valid WAV container
        wav_bytes = audio_data
        if not audio_data.startswith(b"RIFF"):
            # Wrap raw PCM into a standard WAV header (16-bit mono)
            wav_io = io.BytesIO()
            with wave.open(wav_io, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_data)
            wav_bytes = wav_io.getvalue()

        try:
            with io.BytesIO(wav_bytes) as audio_file:
                with sr.AudioFile(audio_file) as source:
                    audio = self._recognizer.record(source)

            # Local Windows Speech Recognition fallback/engine
            # On Windows, Sphinx or local recognition can be used, or SAPI COM via pywin32
            try:
                # Try local recognition via Sphinx or Windows Speech Recognition
                transcript = self._recognizer.recognize_sphinx(audio)
                return transcript.strip(), 0.85
            except (AttributeError, sr.RequestError, sr.UnknownValueError):
                # Fallback to local SAPI file recognition via win32com
                transcript = self._recognize_via_sapi(wav_bytes)
                if transcript:
                    return transcript, 0.90
                raise VoiceError("Speech was unintelligible.", "Could not understand the spoken words. Please speak clearly.")

        except sr.UnknownValueError:
            raise VoiceError("No speech recognized in audio.", "No speech detected. Please speak into your microphone.")
        except Exception as e:
            if isinstance(e, VoiceError):
                raise
            logger.warning(f"Local transcription error: {e}")
            raise VoiceError(f"Audio transcription error: {e}", "Speech recognition encountered an issue. Please try again.")

    def _recognize_via_sapi(self, wav_bytes: bytes) -> Optional[str]:
        """Transcribe WAV using native Windows SAPI InprocRecognizer and COM events."""
        try:
            import win32com.client
            import pythoncom
            import time

            temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            try:
                temp_wav.write(wav_bytes)
                temp_wav.flush()
                temp_wav.close()

                pythoncom.CoInitialize()
                try:
                    recognizer = win32com.client.Dispatch("SAPI.SpInprocRecognizer")
                    reco_context = recognizer.CreateRecoContext()
                    audio_stream = win32com.client.Dispatch("SAPI.SpFileStream")
                    audio_stream.Open(temp_wav.name)
                    recognizer.AudioInputStream = audio_stream
                    grammar = reco_context.CreateGrammar()
                    grammar.DictationSetState(1)

                    recognized_chunks: list[str] = []
                    stream_ended = [False]

                    class RecoSink:
                        def OnRecognition(self, *args):
                            try:
                                result = args[3]
                                text = result.PhraseInfo.GetText()
                                if text:
                                    recognized_chunks.append(text.strip())
                            except Exception as ex:
                                logger.debug(f"SAPI OnRecognition error: {ex}")

                        def OnFalseRecognition(self, *args):
                            logger.debug("SAPI OnFalseRecognition received.")

                        def OnEndStream(self, *args):
                            stream_ended[0] = True

                    win32com.client.WithEvents(reco_context, RecoSink)

                    start_t = time.perf_counter()
                    timeout_s = 5.0
                    while not stream_ended[0] and (time.perf_counter() - start_t < timeout_s):
                        pythoncom.PumpWaitingMessages()
                        time.sleep(0.03)

                    try:
                        audio_stream.Close()
                    except Exception:
                        pass

                    if recognized_chunks:
                        return " ".join(recognized_chunks)
                    return None
                finally:
                    pythoncom.CoUninitialize()
            finally:
                if os.path.exists(temp_wav.name):
                    try:
                        os.unlink(temp_wav.name)
                    except Exception:
                        pass
        except Exception as e:
            logger.debug(f"SAPI recognition attempt: {e}")
        return None

    def cleanup(self) -> None:
        """Releases recognizer resources."""
        self._recognizer = None
        self._initialized = False
        logger.debug("Local STT provider cleaned up.")

