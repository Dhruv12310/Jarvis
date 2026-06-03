"""Voice (Phase 3): a local push-to-talk front-end over JarvisService.

STT (faster-whisper) and TTS (Piper) run entirely on the Brain - mic audio and transcripts never
leave the machine. Both sit behind small seams (`SpeechToText`, `TextToSpeech`) so the model/toolkit
is swappable. The heavy libraries are imported lazily inside the concrete implementations, so the
loop wiring is unit-tested with fakes (no models, no audio device). `loop.py` records -> transcribes
-> calls the same `service.ask` the CLI/GUI call -> speaks the answer.
"""
