# Installed Tamil voice choices

The main voice dropdown selects a locally installed reference and its exact paired transcript. The existing default female narration is unchanged. Additional references are female news (TAM_F_NEWS_00621), female conversational (TAM_F_CONV_02748), and male narration (TAM_M_BOOK_00072). Female styles use the same dataset female speaker, not three distinct women. All are attributed Rasa CC-BY-4.0 clips from the previously accepted dataset revision. `install_voice_options.py` records source rows, hashes and provenance. No downloads occur during generation.

Refresh the app, select a voice, and click **Listen to selected voice sample** to hear the original reference without synthesis. To compare generated narration, use identical short Tamil text for each selection and click Generate Speech. Advanced custom reference mode overrides the dropdown. Chapter JSON records the actual selected voice and provenance. Human review is required; no generated audio tests were run for this change.

## Performance findings and possible next steps

The completed John 1 request took 878.19 seconds (14m38s), producing 442.11 seconds of audio across 152 chunks. Synthesis took 873.55 seconds; MP3 encoding 2.70 seconds; timeline verification 1.29 seconds; log writing 0.41 seconds. Logging is not the dominant bottleneck.

The existing sampler uses 32 steps. An optional 24- or 16-step mode could reduce sampling work, with possible pronunciation/voice-quality loss. Actual wall-clock improvement needs a short user comparison and is not guaranteed proportional to step count. This update does not alter sampling defaults.

Another possible change is grouping short chunks within each verse while preserving verse boundaries and punctuation pauses. This needs a deliberate segmentation/assembly change to preserve exact pause and timing behavior; it has not been implemented. Lower precision inference is another experimental option, requiring compatibility and quality review. GPU parallel generation on the same 8GB device could increase memory pressure and is not assumed faster. The model already remains loaded between requests; avoid restarting it between chapters.
