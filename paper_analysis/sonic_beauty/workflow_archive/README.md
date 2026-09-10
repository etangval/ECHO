# Workspace workflow archive — not the reproduction entry point

These are source copies of the scripts used during excerpt extraction and the
Berg/Webern full-page OMR attempts. They retain the original workspace paths and
are supplied as an audit trail. They require the original score files, exported
LilyPond event logs, directory layout and external programs. They do not run as
a standalone workflow in this package and are not invoked by `run_all.py`.

- `extract_excerpts_workspace.py`: extract pickups and complete bars 1–8 using
  the onset of bar 9, then calculate the descriptors and controls.
- `run_omr_initial_workspace.py`: 2,600-pixel page rasterization and Audiveris batch OMR.
- `run_omr_highres_workspace.py`: 3,600-pixel rerun used during troubleshooting.
- `retry_berg_workspace.py`: subsequent Berg retry.
- `audit_transcriptions_workspace.py`: package the OMR candidates and audit
  measures, page correspondence and note counts using music21.

The OMR workflow requires PyMuPDF, Pillow, music21, Java and Audiveris in addition
to the source PDFs. No OMR executables, score PDFs or candidate transcriptions
are included here. The candidates remain unverified and are excluded from all
accepted coordinates. Earlier failed/intermediate OMR settings are retained as
history and are not recommendations for a validated transcription workflow.

The extraction script generated the numerical note-event inputs already bundled
in `../keyboard/analysis_notes.csv`. The supported, portable reproduction begins
from those inputs. It does not claim to independently revalidate every source
note against the printed score.
