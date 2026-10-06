# Third-party notices

This Windows distribution contains an embedded Python runtime, local speech recognition,
offline translation models and their runtime dependencies. The accompanying `licenses/`
directory contains license texts and notices collected from the exact build environment.

Whisper small.en was created by OpenAI and converted to CTranslate2 by SYSTRAN.
The converted model is distributed from https://huggingface.co/Systran/faster-whisper-small.en.
Whisper and faster-whisper are under the MIT License. CTranslate2 is an OpenNMT project
under the MIT License. PyAudioWPatch is used for Windows WASAPI audio input.

The v1.1 offline English-to-Chinese model is a modified version of
`Helsinki-NLP/opus-mt-en-zh`, pinned to revision
`408d9bc410a388e1d9aef112a2daba955b945255` and distributed under Apache 2.0.
Source and model card: https://huggingface.co/Helsinki-NLP/opus-mt-en-zh.
Model authors: Jörg Tiedemann and Santhosh Thottingal.
Reference: “OPUS-MT — Building open translation services for the World”, Proceedings of
the 22nd Annual Conference of the European Association for Machine Translation, 2020,
Lisbon, Portugal. MeetingTranslator modified the weights by fine-tuning on 1,120
AI-generated original generic bilingual examples, then converted the selected
second-epoch checkpoint to CTranslate2 int8. TED transcripts were not used for
this fine-tuning. See `training/README.md`, `docs/mt-training-v1.1.json`, and
`licenses/Marian-MODIFICATIONS.txt`. The Apache 2.0 license is included.

For historical compatibility, source code can still load an existing Argos
`translate-en_zh-1_9` model. Its original README and CC BY 4.0 license are retained
in `licenses/`. Those Argos weights are not included in the v1.1 Windows ZIP.

PyInstaller's license includes an exception allowing distribution of applications built
with its bootloader. Its license and exception are included in the collected notices.
The distribution also uses Tcl/Tk, NumPy, SciPy, SentencePiece, Tokenizers, ONNX Runtime,
PyAV/FFmpeg, HTTPX and their dependencies; see the included license files.

TED videos and transcripts were used locally for evaluation. They are not included in
the executable, archive or repository. TED and the speakers retain their rights.
