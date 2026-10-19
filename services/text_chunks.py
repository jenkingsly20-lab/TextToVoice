import re

def chunk_text(text, mode='Lines'):
    if not isinstance(text, str) or not text.strip():
        raise ValueError('Paste Tamil text before generating.')
    if len(text) > 20000:
        raise ValueError('Use a short chapter of at most 20,000 characters for this trial.')
    if mode == 'Whole text':
        return [text]
    if mode == 'Lines':
        chunks, prefix = [], ''
        for line in text.splitlines(keepends=True):
            if line.strip():
                chunks.append(prefix + line)
                prefix = ''
            elif chunks:
                chunks[-1] += line
            else:
                prefix += line
        return chunks
    if mode == 'Sentences':
        chunks = [s for s in re.split(r'(?<=[.!?।])(?=\s)', text) if s]
        if len(chunks) > 1 and not chunks[-1].strip():
            tail = chunks.pop()
            chunks[-1] += tail
        return chunks
    raise ValueError('Unknown chunking mode.')
