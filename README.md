# playbacque

Loop play audio

## Usage

```sh
> pip install playbacque
> playbacque "audio.wav"
```

Requires [FFmpeg](https://www.ffmpeg.org/) on PATH

Use Ctrl+C to stop playback

Supports most file formats (as this uses FFmpeg)

Supports taking audio from stdin

```sh
> ffmpeg -i "audio.mp3" -f wav pipe: | playbacque -
```
