"""Per-generation wall-clock stages and incremental local performance events."""
import json
import os
import time
from datetime import datetime,timezone

class PerformanceLog:
    def __init__(self, root, generation_id):
        self.id = generation_id
        self.started = time.perf_counter()
        self.stages = {}
        self.chunks = []
        folder = root / '.performance'
        folder.mkdir(parents=True,exist_ok=True)
        self.path = folder / 'generation.jsonl'
        self.log_write_ms = 0.0
        self.detailed = os.getenv('TAMIL_TTS_DETAILED_LOGGING', '0') == '1'
        self.chapter_path = None
        self.rows = []

    def attach_chapter(self, path):
        self.chapter_path = path
        path.write_text(''.join(self.rows), encoding='utf-8')

    def event(self, stage, **fields):
        if not self.detailed and stage not in ('started', 'text_prepared', 'completed', 'failed'):
            return
        started = time.perf_counter()
        row = dict(generation_id=self.id,utc=datetime.now(timezone.utc).isoformat(),stage=stage,**fields)
        line = json.dumps(row,ensure_ascii=False)+'\n'
        self.rows.append(line)
        for path in (self.path, self.chapter_path):
            if path is not None:
                with path.open('a',encoding='utf-8') as stream:
                    stream.write(line)
        self.log_write_ms += (time.perf_counter()-started)*1000

    def record(self, name, started, **fields):
        elapsed = (time.perf_counter()-started)*1000
        self.stages[name] = self.stages.get(name,0)+elapsed
        self.event(name,elapsed_ms=elapsed,**fields)
        return elapsed

    def snapshot(self, duration):
        elapsed = time.perf_counter()-self.started
        return dict(stages_ms=self.stages.copy(),chunks=self.chunks.copy() if self.detailed else [],chunk_count=len(self.chunks),
            detailed_logging=self.detailed,
            total_generation_ms=elapsed*1000,audio_duration_seconds=duration,
            real_time_factor=elapsed/duration if duration else None,log_writing_ms=self.log_write_ms,
            scope='From callback preprocessing through manifest accounting; Gradio queue wait and the final accounting rewrite/log flush are excluded.',
            stage_accounting='planning_wall_ms contains parsing/preprocessing/chunking; original_text_chunking_ms is included in text_chunking_ms. Worker GPU/reference/file timings are nested inside chunk wall time. Do not sum overlapping stages. Python file_writing_ms covers temp WAV/JSON; MP3 disk writing is included in mp3_encoding_ms.')
