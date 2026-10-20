import config  # Configure privacy and local caches before importing Gradio.
import json
from pathlib import Path
import gradio as gr
from engines.registry import RESEARCHED
from services.generation import generate, registry, generation_lock
from services.chapter_generation import QUALITY_PRESETS, DEFAULT_QUALITY
from services.gpu import diagnostics
from services.ratings import save_rating, FIELDS
from services.default_voice import default_voice_status, voice_choices, voice_sample
from services.speech_normalization import NUMBER_MODES, INPUT_FORMATS, preview_speech

def reference_status(path):
    if not path:
        return 'இன்னும் audio வரவில்லை. Microphone-ல் பதிவு செய்ததும் Stop அழுத்தி, பதிவு upload ஆகும் வரை காத்திருங்கள்; அல்லது audio file upload செய்யுங்கள்.'
    audio = Path(path)
    if not audio.is_file() or audio.stat().st_size == 0:
        return 'Audio file சரியாகச் சேமிக்கப்படவில்லை. மீண்டும் பதிவு செய்யுங்கள் அல்லது file upload செய்யுங்கள்.'
    import tempfile
    from services.audio import prepare_reference
    import wave
    try:
        with tempfile.TemporaryDirectory(prefix='reference_check_') as folder:
            decoded = prepare_reference(audio, Path(folder) / 'reference.wav')
            with wave.open(decoded) as recording:
                seconds = recording.getnframes() / recording.getframerate()
    except ValueError as exc:
        return 'இந்தப் பதிவைப் பயன்படுத்த முடியவில்லை: ' + str(exc) + '\nகீழே உள்ள பழைய பதிவை நீக்கு button-ஐ அழுத்தி 5–10 வினாடிகள் புதிதாகப் பதிவு செய்யுங்கள்.'
    return f'✓ குரல் பதிவு கிடைத்தது — {seconds:.1f} வினாடிகள். கீழே அதன் transcript மற்றும் அனுமதி checkbox-ஐ நிரப்புங்கள்.'

def reset_reference():
    return None, '', False, reference_status(None), 'பழைய பதிவு நீக்கப்பட்டது. இப்போது 5–10 வினாடிகள் புதிதாகப் பதிவு செய்து Stop அழுத்துங்கள்.'

def read_upload(path):
    if not path:
        return gr.skip()
    if Path(path).stat().st_size > 100000:
        raise gr.Error('Use a UTF-8 text file smaller than 100 KB.')
    try:
        return Path(path).read_bytes().decode('utf-8')
    except UnicodeError:
        raise gr.Error('The file must use UTF-8 encoding.')

def run_generation(text, engine, mode, pause, voice, ref=None, transcript='', consent=False, device='Auto', progress=gr.Progress(),
                   semicolon_pause=False, number_mode='Tamil number words', input_format='Plain text', quality=DEFAULT_QUALITY):
    if engine == 'indicf5' and (ref or transcript or consent):
        missing = []
        if not ref:
            missing.append('1. குரல் பதிவு இன்னும் app-க்கு வந்து சேரவில்லை. Microphone recording-ஐ Stop செய்து, upload முடியும் வரை காத்திருங்கள். பதிவு கிடைத்ததும் கீழே ✓ காட்டும். இல்லையெனில் audio file upload செய்யுங்கள்.')
        if not transcript or not transcript.strip():
            missing.append('2. அந்தப் பதிவில் நீங்கள் சொன்ன வார்த்தைகளை Reference transcript பகுதியில் அப்படியே எழுதுங்கள்.')
        if not consent:
            missing.append('3. உங்கள் குரல் அல்லது அனுமதி பெற்ற குரல் என்றால், குரலைப் பயன்படுத்த அனுமதி உள்ளது என்ற checkbox-ஐ tick செய்யுங்கள்.')
        if missing:
            return (*[gr.skip() for _ in range(6)], 'IndicF5-க்கு தமிழ் text மட்டும் போதாது. கீழே உள்ளவற்றை முடித்துவிட்டு Generate Speech அழுத்துங்கள்:\n\n' + '\n\n'.join(missing))
    try:
        audio, mp3, meta, record = generate(text, engine, mode, pause, voice, progress,
            reference_audio=ref, reference_text=transcript, reference_consent=consent, device=device,
            semicolon_pause=semicolon_pause, number_mode=number_mode, input_format=input_format, quality=quality)
        status = 'TEST ONLY — NOT SPEECH. Tone validates audio plumbing; pronunciation remains untested.'
        if record['is_speech']:
            status = 'Completed — தமிழ் audio தயார். Play அழுத்திக் கேளுங்கள்; MP3 download செய்யலாம்.'
        status += '\nAutomatically saved MP3, JSON and JSONL to: ' + str(Path(mp3).parent.resolve())
        if record['warnings']:
            status += '\n' + '\n'.join(record['warnings'])
        return audio, mp3, None, meta, record, record, status
    except Exception as exc:
        message = str(exc)
        if 'out of memory' in message.lower():
            message = 'GPU memory is exhausted. Try shorter line chunks, unload other GPU apps, or select CPU if supported.'
        return (*[gr.skip() for _ in range(6)], 'Error — Speech உருவாக்க முடியவில்லை:\n' + message)

def run_selected_generation(text, engine, mode, pause, voice, custom, ref, transcript, consent, device,
                            semicolon_pause=False, number_mode='Tamil number words', input_format='Plain text',
                            quality=DEFAULT_QUALITY, progress=gr.Progress()):
    if not custom:
        ref, transcript, consent = None, '', False
    elif engine == 'indicf5' and not (ref or transcript or consent):
        return (*[gr.skip() for _ in range(6)], 'Advanced custom voice is selected. Provide its recording, exact transcript and permission, or turn off custom voice to use the default.')
    return run_generation(text, engine, mode, pause, voice, ref, transcript, consent, device, progress,
                          semicolon_pause=semicolon_pause, number_mode=number_mode, input_format=input_format, quality=quality)

def warm_up():
    """Load IndicF5 in the background at launch so the first chapter skips the ~30 s model load."""
    try:
        if registry.engines['indicf5'].is_available():
            with generation_lock:
                registry.select('indicf5')
    except Exception as exc:
        print('IndicF5 warm-up failed; it will load on first use:', exc)

def assess(a, b, preference, notes, *scores):
    try:
        return save_rating(a, b, preference, notes, *scores)
    except ValueError as exc:
        raise gr.Error(str(exc))

def build_ui():
    with gr.Blocks(title='Tamil Bible Voice Lab', analytics_enabled=False,
                   theme=gr.themes.Soft(primary_hue='teal'),
                   css='.tamil textarea {font-size:21px!important;line-height:1.9!important} .gradio-container {max-width:1200px!important}') as ui:
        gr.Markdown('# Tamil Bible Voice Lab\n### தமிழ் குரல் ஆய்வகம்\nLocal listening and comparison · Windows · MP3 + chapter JSON')
        real_ready = registry.engines['indicf5'].is_available()
        gr.Markdown(('**IndicF5 installed — Tamil speech on local GPU.**' if real_ready else '**Setup status: test mode. Real Tamil speech is pending model setup.**') + ' Your text is preserved exactly and processed locally.')
        a, b = gr.State(None), gr.State(None)
        with gr.Tab('Listen / கேளுங்கள்'):
            text = gr.Textbox(label='Tamil text / தமிழ் உரை', lines=8, elem_classes=['tamil'], placeholder='உங்கள் தமிழ் உரையை இங்கே உள்ளிடுங்கள்…')
            gr.Markdown('தமிழ் உரையை உள்ளிட்டு **Generate Speech** அழுத்துங்கள். Default Tamil voice தானாகப் பயன்படுத்தப்படும்; recording அல்லது transcript தேவையில்லை.')
            input_format = gr.Dropdown(INPUT_FORMATS, value='Plain text', label='Input format / உரை வகை')
            voice = gr.Dropdown(voice_choices(), value='default', label='Tamil voice / தமிழ் குரல்')
            gr.Markdown('Female choices are speaking-style references from the same Rasa female speaker. Custom voice in Advanced Settings overrides this selection.')
            sample = gr.Audio(label='Listen to reference sample (not generated speech)', type='filepath', interactive=False)
            sample_button = gr.Button('Listen to selected voice sample')
            sample_button.click(voice_sample, voice, sample, queue=False, api_name=False)
            voice.change(lambda: None, outputs=sample, queue=False, api_name=False)
            gr.Markdown('உரையிலுள்ள 123 → நூற்று இருபத்து மூன்று. நிறுத்தக்குறிகள் இடைவெளிகளாக மாறும்; மூல உரை மாறாது. வசன எண்களைத் தவிர்க்க மட்டும் **Verse-numbered Bible text** தேர்வு செய்யுங்கள்: ஒவ்வொரு வரியிலும் ஒரு வசன எண் + இடைவெளி + வசன உரை வேண்டும்.')
            with gr.Row():
                go = gr.Button('Generate Speech', variant='primary')
                cancel = gr.Button('Cancel pending generation')
            status = gr.Textbox(label='Status', value=default_voice_status() if real_ready else 'Test engine only — not speech.', interactive=False)
            player = gr.Audio(label='Tamil narration / தமிழ் குரல்', type='filepath', format='mp3', interactive=False)
            with gr.Row():
                mp3 = gr.File(label='Download chapter MP3')
                meta = gr.File(label='Download chapter JSON (verse timing + performance)')
            wav = gr.State(None)
            with gr.Accordion('Advanced Settings / கூடுதல் அமைப்புகள்', open=False):
                upload = gr.File(label='Optional UTF-8 .txt', file_types=['.txt'], type='filepath')
                upload.change(read_upload, upload, text, api_name=False)
                with gr.Row():
                    engine = gr.Dropdown(registry.choices(), value='indicf5' if real_ready else 'mock', label='Installed engine')
                custom = gr.Checkbox(value=False, label='Use my own reference voice instead of the configured Tamil default')
                gr.Markdown('Only for custom voice experiments: supply a permitted 1–15 second clip and its exact transcript. Leave the custom voice checkbox off for normal text-only generation.')
                ref = gr.Audio(label='Custom reference recording (optional)', sources=['upload', 'microphone'], type='filepath')
                ref_status = gr.Textbox(label='Custom recording status', interactive=False)
                ref.change(reference_status, ref, ref_status, queue=False, show_progress='hidden', api_name=False)
                transcript = gr.Textbox(label='Custom reference transcript (optional)', lines=2)
                consent = gr.Checkbox(label='I have explicit permission to use this custom voice.', value=False)
                reset = gr.Button('Clear custom recording')
                device = gr.Radio(['Auto', 'CPU'], value='Auto', label='Inference device')
                with gr.Row():
                    mode = gr.Radio(['Whole text', 'Lines', 'Sentences'], value='Lines', label='Chunking')
                    pause = gr.Slider(250, 700, value=400, step=50, label='Pause between chunks (ms)')
                semicolon = gr.Checkbox(value=False, label='Also split at commas (slower, older behaviour; full stops always get a pause) / காற்புள்ளியிலும் பிரித்தல்')
                quality = gr.Dropdown(list(QUALITY_PRESETS), value=DEFAULT_QUALITY, label='Speed / quality')
                gr.Markdown('Fast is several times quicker. If it sounds worse than before, choose **Original** to compare.')
                numbers = gr.Dropdown(NUMBER_MODES, value=NUMBER_MODES[0], label='Number reading / எண்களை வாசிக்கும் முறை')
                gr.Markdown('Tamil number words என்பது default. Plain text-ல் தொடக்க எண்களும் வாசிக்கப்படும். Verse-numbered mode-ல் உறுதிசெய்யப்பட்ட வரித்தொடக்க வசன எண்கள் மட்டும் தவிர்க்கப்படும்; உரையிலுள்ள எண்கள் தமிழில் வாசிக்கப்படும்.')
                spoken_preview = gr.Textbox(label='Model-க்கு அனுப்பப்படும் உரை — preview', interactive=False, lines=4)
                preview_button = gr.Button('Preview speech text')
                preview_button.click(preview_speech, [text, semicolon, numbers, input_format, mode, pause], spoken_preview, queue=False, api_name=False)
                details = gr.JSON(label='Engine, timing, device and provenance')
                gr.Markdown('Default voice: AI4Bharat Rasa, Tamil female book narration, TAM_F_BOOK_00014. [Source](https://huggingface.co/datasets/ai4bharat/Rasa) · [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). See assets/voices/default_tamil/ATTRIBUTION.md for credit and changes.')
            reset.click(reset_reference, outputs=[ref, transcript, consent, ref_status, status], queue=False, api_name=False)
            started = go.click(lambda: 'Generating — தமிழ் குரல் உருவாக்கப்படுகிறது…', outputs=status, queue=False, api_name=False)
            event = started.then(run_selected_generation, [text, engine, mode, pause, voice, custom, ref, transcript, consent, device, semicolon, numbers, input_format, quality],
                             [player, mp3, wav, meta, details, a, status], concurrency_limit=1, api_name=False)
            cancel.click(fn=None, cancels=[event])
            gr.Markdown('Cancellation removes queued work; an active synchronous engine call may finish. Completed files remain local.')
        with gr.Tab('Compare / ஒப்பிடுங்கள்'):
            gr.Markdown('**One real speech model is installed.** Retain output A as B, generate another take, and compare with identical input text. Comparison with a second real model awaits installation. Test tones cannot receive speech ratings.' if real_ready else '**Only a test engine is installed.** Test tones cannot receive speech ratings.')
            keep = gr.Button('Retain current output as B')
            player_b = gr.Audio(label='Retained output B', format='mp3', interactive=False)
            details_b = gr.JSON(label='B metadata')
            def retain(record, audio):
                if not record:
                    raise gr.Error('Generate output A first.')
                return record, audio, record
            keep.click(retain, [a, player], [b, player_b, details_b], api_name=False)
            preference = gr.Radio(['A', 'B', 'Tie', 'Single output'], value='Single output', label='Overall preference')
            scores = [gr.Slider(1, 5, value=3, step=1, label=label.replace('_', ' ').title() + ' (1 poor, 5 best)') for label in FIELDS]
            notes = gr.Textbox(label='Listening notes', lines=3)
            save = gr.Button('Export human assessment')
            with gr.Row():
                rating_json = gr.File(label='Assessment JSON')
                rating_csv = gr.File(label='Assessment CSV')
            save.click(assess, [a, b, preference, notes, *scores], [rating_json, rating_csv], api_name=False)
        with gr.Tab('Setup & diagnostics'):
            gr.Markdown(RESEARCHED.replace('**IndicF5 — Not installed.** Tamil supported; gated weights require your Hugging Face acceptance and an authorized reference recording plus transcript. Native Windows and 8 GB feasibility remain unverified.', '**IndicF5 — Installed and verified on native Windows / RTX 4060.** Uses an authorized 1–15 second reference clip plus exact transcript. Short offline Tamil generation passed; human pronunciation review is pending.') if real_ready else RESEARCHED)
            gpu = gr.JSON(label='Local GPU / CUDA diagnostics')
            refresh = gr.Button('Refresh diagnostics')
            refresh.click(diagnostics, outputs=gpu, api_name=False)
            gr.Markdown('Run `.\\.venv\\Scripts\\python.exe -c "from services.gpu import diagnostics; print(diagnostics())"` and `nvidia-smi`. See docs for the optional CUDA environment. No driver changes are made by this app.')
            ui.load(diagnostics, outputs=gpu, api_name=False)
    return ui

if __name__ == '__main__':
    config.OUTPUTS.mkdir(parents=True, exist_ok=True)
    import threading
    threading.Thread(target=warm_up, daemon=True).start()
    build_ui().queue(default_concurrency_limit=1).launch(server_name='127.0.0.1', server_port=7860,
        share=False, inbrowser=True, show_error=True, allowed_paths=[str(config.OUTPUTS)])
