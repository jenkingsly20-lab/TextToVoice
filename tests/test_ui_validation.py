from app import run_generation

def test_missing_custom_reference_reports_actionable_status():
    result = run_generation('தமிழ்', 'indicf5', 'Lines', 400, 'Reference recording', transcript='தமிழ்')
    assert len(result) == 7
    assert 'Microphone' in result[-1]
    assert 'checkbox' in result[-1]
    assert all(item == {'__type__': 'update'} for item in result[:6])

def test_consent_does_not_bypass_reference_requirement():
    result = run_generation('தமிழ்', 'indicf5', 'Lines', 400, 'Reference recording', consent=True)
    assert 'Microphone' in result[-1]
    assert 'checkbox' not in result[-1]

def test_reference_received_indicator(tmp_path):
    from app import reference_status
    assert 'இன்னும் audio வரவில்லை' in reference_status(None)
    audio = tmp_path / 'recording.wav'
    assert 'சேமிக்கப்படவில்லை' in reference_status(str(audio))
    import wave
    with wave.open(str(audio), 'wb') as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(24000)
        recording.writeframes(b'\x00\x00' * 48000)
    assert '✓' in reference_status(str(audio))

def test_reset_reference_removes_stale_audio_and_consent():
    from app import reset_reference
    audio, transcript, consent, indicator, status = reset_reference()
    assert audio is None
    assert transcript == ''
    assert consent is False
    assert 'பழைய பதிவு நீக்கப்பட்டது' in status

def test_normal_workflow_ignores_stale_custom_inputs(monkeypatch):
    import app
    captured = {}
    def fake_generate(*args, **kwargs):
        captured['args'] = args
        return ('ok',)
    monkeypatch.setattr(app, 'run_generation', fake_generate)
    app.run_selected_generation('தமிழ்', 'indicf5', 'Lines', 400, 'Default Tamil', False,
                                'stale_recording.m4a', 'old transcript', True, 'Auto')
    assert captured['args'][5:8] == (None, '', False)

def test_explicit_custom_mode_requires_its_own_reference():
    from app import run_selected_generation
    result = run_selected_generation('தமிழ்', 'indicf5', 'Lines', 400, '', True, None, '', False, 'Auto')
    assert 'Advanced custom voice' in result[-1]
