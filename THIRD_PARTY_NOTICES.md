# Third-party notices

This Windows distribution contains an embedded Python runtime, local speech recognition,
offline translation models and their runtime dependencies. The accompanying `licenses/`
directory contains license texts and notices collected from the exact build environment.

Whisper small.en was created by OpenAI and converted to CTranslate2 by SYSTRAN.
The converted model is distributed from https://huggingface.co/Systran/faster-whisper-small.en.
Whisper and faster-whisper are under the MIT License. CTranslate2 is an OpenNMT project
under the MIT License. PyAudioWPatch is used for Windows WASAPI audio input.

The offline English-to-Chinese model is Argos `translate-en_zh-1_9`, based on OPUS-MT.
Its packaged README states that the original model is licensed under CC BY 4.0.
Model authors: Jörg Tiedemann and Santhosh Thottingal.
Reference: “OPUS-MT — Building open translation services for the World”, Proceedings of
the 22nd Annual Conference of the European Association for Machine Translation, 2020,
Lisbon, Portugal. The original model is bundled without retraining or modification.
Download: https://argos-net.com/v1/translate-en_zh-1_9.argosmodel.
The application changes sentence preparation and inference; it does not change model weights.

PyInstaller's license includes an exception allowing distribution of applications built
with its bootloader. Its license and exception are included in the collected notices.
The distribution also uses Tcl/Tk, NumPy, SciPy, SentencePiece, Tokenizers, ONNX Runtime,
PyAV/FFmpeg, HTTPX and their dependencies; see the included license files.

TED videos and transcripts were used locally for evaluation. They are not included in
the executable, archive or repository. TED and the speakers retain their rights.
