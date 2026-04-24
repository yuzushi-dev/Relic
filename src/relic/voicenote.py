"""Cron entrypoint: relic:voicenote

Invoked as: python -m relic.voicenote
Schedule:   @manual

On-demand voice note transcription: transcribes an audio file and
appends the transcript to inbox.jsonl for subsequent extraction.
"""
from relic.relic_voicenote_transcriber import main

if __name__ == "__main__":
    main()
