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

## Advanced

When input is from stdin, an internal buffer is automatically used to loop the audio

If input is from a URL (not seekable), pass `--buffer` to force buffering the audio

For PCM encoded input, ensure it is 48000 Hz signed 16 bit stereo audio, and pass `--pcm`

To write PCM encoded audio to stdout, pass `--out`

To specify a specific audio device to output to, pass `--device <id>` (list devices using `--list-devices`)

On Windows, there is a `Microsoft Sound Mapper - Output, MME (0 in, 2 out)` device that redirects to the default output device and also works after disconnecting
