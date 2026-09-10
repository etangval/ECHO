import wave
import numpy as np
import pandas as pd
from digitalcreativity import pipeline
from digitalcreativity.audio import render


def test_offline_audio_has_exact_duration_stereo_quiet_tail(tmp_path):
    source = tmp_path/"artificial.csv"
    pd.DataFrame(dict(time_seconds=[0., .8, 1.], category=["a", "b", "a"])).to_csv(source, index=False)
    folder = tmp_path/"run"
    manifest = pipeline.sonify(source, folder, pipeline.protocol(15, steps=20), mode="all")
    report = render(folder, instrument="sine", mp3=False)
    with wave.open(str(folder/"optimized_sine.wav")) as audio:
        assert audio.getnchannels() == 2
        assert audio.getnframes() == round(manifest["protocol"]["output_seconds"]*44100)
        signal = np.frombuffer(audio.readframes(audio.getnframes()), "<i2").reshape(-1, 2)
    assert abs(signal).max() <= round(.751*32767)
    assert not np.array_equal(signal[:, 0], signal[:, 1])
    assert signal[-1].tolist() == [0, 0]
    assert report["no_new_notes_last_seconds"] == 10
    assert report["onset_rounding_max_seconds"] <= .5/44100+1e-12
    assert report["final_100ms_rms_dbfs"] < -65
