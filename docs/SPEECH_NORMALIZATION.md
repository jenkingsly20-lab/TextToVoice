# Tamil numbers, verse labels and punctuation

The original text is retained exactly in the textbox and `metadata.json` → `original_text`. Only the separate speech plan is transformed. No model retraining or ASR is involved.

## Normal use

Tamil number words are the default. `123` becomes `நூற்று இருபத்து மூன்று`. Ordinary text beginning with a number keeps that number in spoken form; it is never assumed to be a verse label.

For verse-numbered input, explicitly select **Verse-numbered Bible text** beside the main input. Supply one verse per line, each beginning with a positive number followed by a space and its text. A period/closing parenthesis after the label is allowed. Numbers must increase within one chapter; repeated/reversed labels, chapter headings and unnumbered continuation lines are rejected rather than guessed. Only validated leading labels are omitted. Numbers inside the verse body still become Tamil words. Use **Plain text** for other layouts.

Example input (a Bible verse plus a separate number-reading control sentence):

```text
1 கர்த்தர் என் மேய்ப்பராயிருக்கிறார்; நான் தாழ்ச்சியடையேன்.
2 அவர் 123 பேரை அழைத்தார், அவர்கள் வந்தார்கள்.
```

With verse mode, `1` and `2` are omitted; `123` becomes Tamil words; all other words remain. With plain mode, `1` and `2` are spoken too.

## Pauses

Common punctuation creates separate inference chunks and explicit PCM silence between them. Punctuation symbols are not fed to the model as words. Comma: 180 ms; colon: 250 ms; semicolon: 350 ms; period/full stop: 450 ms; question: 500 ms; exclamation: 450 ms; ellipsis: 600 ms. Adjacent punctuation uses the longest pause, not stacked silences. Line/sentence chunk boundaries also respect the configured inter-chunk pause (default 400 ms). No extra silence is appended after the final chunk. The model can produce its own silence, so these are inserted PCM pauses, not guarantees of total perceived pause or question intonation.

## Audit and limits

Advanced Settings → **Preview speech text** shows the spoken chunks and pause markers. Downloaded metadata includes `normalized_tts_text` (exact model-bound chunks separated by newlines), `normalized_number_text`, `spoken_chunks`, `speech_text_changes`, `punctuation_events` and `pauses_ms`. Number/label changes include exact original offsets and replacements; punctuation events use offsets within their normalized source chunk. Original text and original chunks remain separate.

Number conversion uses pinned [AI4Bharat indic-numtowords](https://github.com/AI4Bharat/indic-numtowords) 1.1.0 (MIT). Standard Arabic/Tamil decimal digits, valid comma-grouped integers, signs and decimal fractions are supported. Decimal digits after the point are spoken individually. Leading-zero identifiers are spoken digit by digit. Inputs over 15 digits are rejected. Attached numeric words such as `3ஆம்` or IDs are preserved with a visible warning; the app does not guess suffix morphology. Date/fraction/range semantics are not inferred; review unusual expressions. Keep numbers unchanged and per-digit modes remain available for explicit comparison.

Defaults can be overridden in Advanced Settings, but verse labels are never removed without the explicit verse-numbered input format. Disabling punctuation pauses is a comparison/debug option; normal operation enables them.

## Checks

29 tests passed; `pip check` found no broken requirements. Tests cover the exact 123 conversion, Tamil digits, decimals and grouped counts, original-text integrity, verse-mode refusal of unsafe layouts, retaining leading counts in plain text, auditable source spans, and exact inserted PCM sample gaps. Live CUDA checks use the supplied Bible samples as explicitly numbered lines and a separate numeric control sentence through the Gradio queue, WAV playback delivery and MP3 download. Human listening remains necessary to judge omissions, pronunciation and naturalness; automatic checks cannot certify spoken correctness.

Live outputs: `outputs/20261018T030238_ddfb020b58a3459ab706ac5c584ada9e/` contains the numbered Bible test (11.069 seconds; 86,949-byte MP3). `outputs/20261018T030254_4c43192451bc43ecb38083af5557cdd2/` contains the numeric control (8.617 seconds; 64,893-byte MP3). Both ran on CUDA with the installed default Tamil voice. Each metadata file preserves original and normalized text. Generated PCM gaps were separately checked for the exact requested silence lengths. Output folder dates are UTC.
