import wave
import numpy as np
import pytest
from digitalcreativity.study_synthesis import render_study_wav


def test_archived_instrument_repeatability_and_validation(tmp_path):
    e = dict(onset_seconds=np.array([1., .25, .6]), pitch=np.array([60, 60, 67]),
             velocity=np.array([50, 70, 60]), pan_cc10=np.array([20, 20, 110]),
             repeat_memory=np.array([1., 0., 0.]))
    first = render_study_wav(e, tmp_path/'one.wav', 12.)
    second = render_study_wav(e, tmp_path/'two.wav', 12.)
    assert first['sha256'] == second['sha256']
    with wave.open(str(tmp_path/'one.wav')) as f:
        assert f.getnframes() == 12*44100 and f.getnchannels() == 2
        pcm = np.frombuffer(f.readframes(f.getnframes()), '<i2').reshape(-1, 2)
    assert not np.array_equal(pcm[:,0], pcm[:,1])
    assert pcm[-1].tolist() == [0,0]
    assert np.abs(pcm).max() <= .751*32767
    with pytest.raises(ValueError, match='already exists'):
        render_study_wav(e, tmp_path/'one.wav', 12.)
    e['onset_seconds'][0] = 2.
    with pytest.raises(ValueError, match='ten-second'):
        render_study_wav(e, tmp_path/'bad.wav', 12.)
