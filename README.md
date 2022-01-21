# playbacque

Loop play audio

## Usage

```sh
> pip install playbacque
> playbacque "audio.wav"
```

Use Ctrl+C to stop playback

Supports most file formats (as this uses soundfile which uses libsndfile)

Notable exceptions include .mp3 and .ogg

As an alternative, one can first convert to a .wav using FFmpeg and pipe into
`playbacque -`, where - means to take audio from stdin

```sh
> ffmpeg -i "audio.mp3" -f wav pipe: | playbacque -
```

Note when passing -, the entire stdin is buffered before playback
