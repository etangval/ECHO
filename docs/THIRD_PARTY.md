# Third-party materials

The original code in this repository is MIT licensed. The following materials have independent licences.

## Piano samples

**Salamander Grand Piano**, Alexander Holm, Yamaha C5 recording, via the Tone.js audio repository. The upstream [README](https://github.com/Tonejs/audio/blob/869b6f8d9cddb47d966238c012041480b1ce517a/salamander/README) identifies the author and [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) licence.

The renderer downloads only required samples from commit `869b6f8d9cddb47d966238c012041480b1ce517a`; sample files are not bundled in this repository. This endpoint provides one supplied sample layer, not the full multi-layer instrument described by the upstream project. Dynamics here scale amplitude. Samples are altered by pitch resampling, leading-silence trimming, stereo balance and amplitude scaling. Full recorded decays implement the held-pedal approximation; sympathetic resonance, pedal noise and velocity-layer switching are not separately synthesized.

When distributing rendered audio, include the attribution in the generated `PIANO_CREDITS.txt`, the licence link and an indication of the alterations. The upstream commit URL and per-file SHA-256 hashes appear in each local audio manifest.

## Software dependencies

NumPy and pandas use BSD licences; mido uses the MIT licence; Astropy uses a BSD licence; imageio-ffmpeg uses a BSD licence for its Python wrapper. FFmpeg binaries have their own LGPL/GPL build-dependent terms. FFmpeg is not vendored here; review the licence of the binary you install before redistributing it. pytest is used only for development/testing and uses the MIT licence.

Consult the licence files supplied with the installed dependency versions. Installing the toolkit does not transfer ownership of those projects or scientific source datasets. The toolkit uses Python's standard HTTPS client for optional piano-sample downloads and performs no data upload or telemetry.
