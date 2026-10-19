"""Existing IndicF5 orchestration with verse provenance and MP3 chapter export."""
import json
import tempfile
import time
import uuid
from datetime import datetime,timezone
from pathlib import Path
from threading import Lock
from config import OUTPUTS,MP3_BITRATE_KBPS
from engines.registry import Registry
from services.audio import combine,write_wav,encode_mp3,inspect_mp3_timeline
from services.chapter_plan import build_chapter_plan,verse_pcm_boundaries
from services.performance import PerformanceLog
from services.text_chunks import chunk_text

registry = Registry()
generation_lock = Lock()

def generate(text, engine_id='mock', mode='Lines', pause_ms=400, voice=None, progress=None, output_root=None,
             reference_audio=None, reference_text='', reference_consent=False, device='Auto',
             semicolon_pause=True, number_mode='Tamil number words', input_format='Plain text', mp3_bitrate_kbps=None):
    started = time.perf_counter()
    root = Path(output_root or OUTPUTS)
    generation_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex
    perf = PerformanceLog(root,generation_id)
    perf.started = started
    perf.event('started',engine_id=engine_id)
    try:
        bitrate = MP3_BITRATE_KBPS if mp3_bitrate_kbps is None else int(mp3_bitrate_kbps)
        if bitrate not in (32,40,48,56,64,80,96,112,128,160,192,224,256,320):
            raise ValueError('Choose a standard MP3 bitrate; default is 192 kbps.')
        measured = time.perf_counter()
        original_chunks = chunk_text(text,mode)
        perf.record('original_text_chunking_ms',measured)
        measured = time.perf_counter()
        plan = build_chapter_plan(text,mode,pause_ms,semicolon_pause,number_mode,input_format)
        perf.record('planning_wall_ms',measured)
        perf.stages.update(plan['stage_timings'])
        perf.stages['text_chunking_ms'] += perf.stages['original_text_chunking_ms']
        stem = f'{plan["book_id"]}_{plan["chapter"]:02d}' if plan['book_id'] and plan['chapter'] else 'narration'
        folder = root/stem/generation_id
        folder.mkdir(parents=True,exist_ok=False)
        perf.attach_chapter(folder/(stem+'.jsonl'))
        perf.event('text_prepared',**plan['stage_timings'],chunk_count=len(plan['spoken_chunks']),
            verse_count=len(plan['verse_sources']),book_id=plan['book_id'],chapter=plan['chapter'])
        measured = time.perf_counter()
        provenance,reference_cache_hit = None,None
        if engine_id=='indicf5':
            if not reference_audio and not reference_text:
                from services.default_voice import selected_reference
                defaults = selected_reference(voice)
                reference_audio,reference_text = defaults['reference_audio'],defaults['reference_text']
                reference_consent,voice = defaults['reference_consent'],defaults['voice']
                provenance = defaults['voice_provenance']
                reference_cache_hit = defaults['preprocessing_cache_hit']
            if not reference_consent:
                raise ValueError('Confirm permission to use the reference voice.')
            if not reference_audio or not reference_text.strip():
                raise ValueError('Provide a permitted reference recording and its exact transcript.')
        perf.record('default_reference_preparation_ms',measured,cache_hit=reference_cache_hit)
        options = dict(voice=voice,chunk_mode=mode,pause_ms=pause_ms,reference_audio=reference_audio,
            reference_text=reference_text,reference_consent=reference_consent,device=device,
            punctuation_pauses=semicolon_pause,number_mode=number_mode,input_format=input_format,
            verified_verse_numbered_input=plan['verse_layout_verified'],mp3_bitrate_kbps=bitrate)
        if provenance: options['voice_provenance']=provenance
        measured = time.perf_counter()
        with generation_lock:
            perf.record('model_lock_wait_ms',measured)
            measured = time.perf_counter()
            engine = registry.select(engine_id)
            perf.record('engine_load_or_switch_ms',measured)
            audio,metrics,rate = [],[],None
            for i,chunk in enumerate(plan['spoken_chunks']):
                if progress: progress(i/len(plan['spoken_chunks']),desc=f'Generating chunk {i+1}/{len(plan["spoken_chunks"])}')
                perf.event('chunk_started',chunk_index=i,verse_number=plan['chunk_verse_numbers'][i])
                measured = time.perf_counter()
                result = engine.synthesize(chunk,options)
                elapsed_ms = (time.perf_counter()-measured)*1000
                if rate is not None and rate!=result.sample_rate:
                    raise ValueError('Engine changed sample rate between chunks.')
                rate = result.sample_rate
                audio.append(result.pcm)
                metric = dict(getattr(engine,'last_metrics',{}))
                metrics.append(metric)
                chunk_record = dict(chunk_index=i,verse_number=plan['chunk_verse_numbers'][i],
                    wall_ms=elapsed_ms,audio_duration_seconds=len(result.pcm)/rate,
                    generated_samples=len(result.pcm),worker=metric)
                perf.chunks.append(chunk_record)
                perf.event('chunk_completed',**chunk_record)
            perf.stages['synthesis_chunks_wall_ms'] = sum(c['wall_ms'] for c in perf.chunks)
            measured = time.perf_counter()
            pcm,boundaries = combine(audio,rate,pause_ms,plan['pauses_ms'])
            pcm_verses = verse_pcm_boundaries(plan,boundaries,len(pcm),rate)
            perf.record('audio_assembly_and_silence_ms',measured,pcm_samples=len(pcm))
            mp3,manifest = folder/(stem+'.mp3'),folder/(stem+'.json')
            if progress: progress(.95,desc='Assembling chapter MP3 and verifying playback timing')
            with tempfile.TemporaryDirectory(prefix='tamil_chapter_') as temporary:
                wav = Path(temporary)/'chapter.wav'
                measured = time.perf_counter()
                write_wav(wav,pcm,rate)
                perf.record('file_writing_ms',measured,kind='temporary_pcm_wav')
                measured = time.perf_counter()
                encoded,warning = encode_mp3(wav,mp3,bitrate)
                perf.record('mp3_encoding_ms',measured,bitrate_kbps=bitrate,output_sample_rate=48000)
                if not encoded:
                    raise ValueError(warning or 'MP3 encoding failed.')
            measured = time.perf_counter()
            playback = inspect_mp3_timeline(mp3,len(pcm),rate)
            perf.record('mp3_timeline_verification_ms',measured,verified=playback['verified'])
            duration_ms = playback.get('decoded_duration_ms',round(len(pcm)*1000/rate))
            duration = duration_ms/1000
            available = bool(playback['verified'] and pcm_verses and engine.capabilities.speech)
            verses = [dict(verse_number=v['verse_number'],start_ms=v['start_ms'],end_ms=v['end_ms'],
                           speech_end_ms=v['speech_end_ms']) for v in pcm_verses] if available else []
            warnings = list(plan['warnings'])
            if not engine.capabilities.speech: warnings.append('TEST ONLY — NOT SPEECH')
            if not plan['book_id'] or not plan['chapter']:
                warnings.append('No unambiguous chapter reference heading: book_id/chapter are null; filename is narration.mp3.')
            if not pcm_verses:
                warnings.append('Verse highlighting unavailable: supply a recognized chapter heading and one numbered verse per line, or explicitly select verse-numbered input. Chunk boundaries are not assumed to be verses.')
            if not playback['verified']: warnings.append(playback.get('limitation','MP3 timeline could not be verified.'))
            metadata = dict(schema_version='2.0',id=generation_id,created_utc=datetime.now(timezone.utc).isoformat(),
                book_id=plan['book_id'],chapter=plan['chapter'],audio_filename=mp3.name,metadata_filename=manifest.name,
                performance_log_filename=perf.chapter_path.name,output_directory=str(folder.resolve()),
                chapter_content_scope='Provided text only; completeness of a whole canonical chapter is not inferred.',
                total_duration_ms=duration_ms,duration_seconds=duration,verses=verses,
                verse_timing=dict(available=available,basis='Actual generated PCM segment sample positions, rescaled onto verified gapless MP3 playback; not text-length or chunk-as-verse estimates.',
                    end_is_exclusive=True,interverse_pause_belongs_to='preceding verse',
                    intro_end_ms=pcm_verses[0]['start_ms'] if pcm_verses else None,
                    precision='Whole generated verse segments including model silence; not word/phoneme alignment.',
                    playback=playback),
                original_text=text,engine_id=engine.id,engine_name=engine.display_name,engine_version=result.version,
                is_speech=engine.capabilities.speech,settings=options,chunks=original_chunks,
                chunk_sample_boundaries=boundaries,chunk_verse_numbers=plan['chunk_verse_numbers'],
                verse_pcm_segments=pcm_verses,spoken_chunks=plan['spoken_chunks'],speech_text_changes=plan['changes'],
                normalized_tts_text=plan['normalized_tts_text'],normalized_number_text=plan['normalized_number_text'],
                punctuation_events=plan['punctuation_events'],pauses_ms=plan['pauses_ms'],sample_rate=rate,
                playback_sample_rate=playback['playback_sample_rate'],device=result.device,
                mp3_bytes=mp3.stat().st_size,mp3_bitrate_kbps=bitrate,warnings=warnings,
                chunk_inference_metrics=metrics if perf.detailed else [],reference_preprocessing_cache_hit=reference_cache_hit,
                timing_note='Flutter playback must honor MP3 encoder delay and padding; verify your specific player before enabling production highlighting.')
            if engine.id=='indicf5':
                metadata.update(vocos_revision='0feb3fdd929bcd6649e0e7c5a688cf7dd012ef21',
                    source_revision='13f7c4d627cc10111aea8fe9c0039462cacacdc7')
            def account():
                metadata['performance'] = perf.snapshot(duration)
                metadata['elapsed_seconds'] = metadata['performance']['total_generation_ms']/1000
                metadata['realtime_factor'] = metadata['performance']['real_time_factor']
            account()
            measured = time.perf_counter()
            manifest.write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
            perf.record('file_writing_ms',measured,kind='chapter_manifest')
            account()
            manifest.write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
            perf.event('completed',**perf.snapshot(duration),audio_filename=mp3.name,metadata_filename=manifest.name)
            # Keep the legacy four-item return shape; audio/player now points to MP3.
            return str(mp3),str(mp3),str(manifest),metadata
    except Exception as exc:
        perf.event('failed',error=str(exc),elapsed_ms=(time.perf_counter()-started)*1000)
        raise
