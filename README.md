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

## Development

This project uses [Hatch](https://ofek.dev/hatch/) for project management and [hatch-vcs](https://github.com/ofek/hatch-vcs) for getting the version from Git tags when building

However, other tools can be used, such as virtualenv for isolating dependencies, pip to install the project, build to build the project, and twine to publish the project

I recommend using [pipx](https://pypa.github.io/pipx/) to install Hatch and hatch-vcs

Install pipx globally

```sh
> pip install --user pipx
> pipx ensurepath
```

Install Hatch 1.0 (currently in prerelease) and inject the hatch-vcs plugin

```sh
> pipx install "hatch>=1.0.0.dev"
> pipx inject hatch hatch-vcs
```

Run the project using Hatch

```sh
> hatch run playbacque -V
```

Run linters and tests

```sh
> hatch run lint:all
> hatch run test:all
```

If you have Python 3.7 - 3.10 all installed for some reason, run tests on all of them

```sh
> hatch run test-matrix:all
```
