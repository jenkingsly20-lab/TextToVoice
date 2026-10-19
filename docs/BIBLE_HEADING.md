# Bible heading pronunciation

Only a complete recognized reference on the first nonempty line is expanded. The original heading and scripture remain untouched. A known Tamil Bible book name is required; numerical prefixes are accepted only for numbered books. Inline references and later lines continue through the existing verse processing unchanged.

Manual checks after refreshing localhost:7860:

1. Paste `1 யோவான் 2:1-4` on the first line and scripture on subsequent lines. Its heading preview should read `முதலாம் யோவான், இரண்டாம் அதிகாரம், ஒன்று முதல் நான்கு வரையிலான வசனங்கள்.`
2. Try `யோவான் 3:16` → `யோவான், மூன்றாம் அதிகாரம், பதினாறாம் வசனம்.`
3. Try `ரோமர் 8:1-4` → `ரோமர், எட்டாம் அதிகாரம், ஒன்று முதல் நான்கு வரையிலான வசனங்கள்.`
4. Try `சங்கீதம் 23` → `இருபத்துமூன்றாம் சங்கீதம்.`
5. Try `2 கொரிந்தியர் 5:17` and confirm the book starts with `இரண்டாம் கொரிந்தியர்`.

Use the existing Advanced Settings → Preview speech text to inspect the model input. Existing punctuation processing turns the heading's commas into pauses. The heading/body boundary receives at least 450 ms of inserted PCM silence (or the configured inter-chunk pause if larger). Generate Speech and check that the heading is heard once, followed by the verses. Original text remains in metadata; the heading replacement is logged as `Bible reference heading` with original source offsets.

For numbered verses under the heading, use the existing Verse-numbered Bible text input format. Only the verse body is passed through its existing validation and number conversion. For ordinary prose use Plain text. No UI, default voice, MP3 encoder or verse-normalization rules were changed.

Per user request, this update received syntax checks only; no automated suite, GPU inference or audio generation was run. Functional listening checks are left to the user.
