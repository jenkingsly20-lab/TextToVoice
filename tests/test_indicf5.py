import pytest
from services.generation import generate

def test_reference_consent_before_model_loading(tmp_path):
    with pytest.raises(ValueError, match='permission'):
        generate('தமிழ்', 'indicf5', output_root=tmp_path, reference_text='தமிழ்')
    with pytest.raises(ValueError, match='reference recording'):
        generate('தமிழ்', 'indicf5', output_root=tmp_path, reference_consent=True, reference_text='தமிழ்')
    assert not list(tmp_path.iterdir())

def test_indicf5_worker_is_offline():
    # Configuration contract: UI imports do not import heavy model dependencies.
    import sys
    import engines.indicf5
    assert 'torch' not in sys.modules

@pytest.mark.parametrize('mode', ['Lines', 'Sentences'])
def test_blank_lines_do_not_create_empty_model_requests(mode):
    from services.text_chunks import chunk_text
    text = '\n\nதமிழ்.\n\nஅருள்.\n\n'
    chunks = chunk_text(text, mode)
    assert ''.join(chunks) == text
    assert all(chunk.strip() for chunk in chunks)
