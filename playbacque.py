"""Loop play audio"""

import argparse
import sys
import errno
if sys.version_info >= (3, 8):
    import importlib.metadata as importlib_metadata
else:
    import importlib_metadata

from typing import Optional, Any, Iterable, List, Dict, Iterator, NoReturn
if sys.version_info >= (3, 8):
    from typing import Literal, Final
else:
    from typing_extensions import Literal, Final

import sounddevice  # type: ignore[import]
import soundit  # type: ignore[import]

# FFmpeg arguments for PCM audio
_PCM_ARGS: Final = ["-f", "s16le", "-ar", 48000, "-ac", 2]

# sounddevice arguments for PCM audio
_PCM_SETTINGS: Final = dict(samplerate=48000, channels=2, dtype="int16")

# - Streaming audio

def loop_stream_ffmpeg(
    filename: str,
    *,
    buffer: Optional[bool] = None,
    input_args: Optional[List[Any]] = None,
    input_kwargs: Optional[Dict[str, Any]] = None,
) -> Iterator[bytes]:
    """Forever yields audio chunks from the file using FFmpeg

    Deprecated input_kwargs: pass input_args instead

    - filename is the file to loop (can be - or pipe: to use stdin)
    - buffer => file in ("pipe:", "-"): whether to buffer in memory to loop
    - input_args => []: specify extra input arguments (useful for PCM files)
    - input_kwargs => {}: specify extra input arguments (useful for PCM files)

    The yielded chunks are hard coded to be 48000 Hz signed 16-bit little
    endian stereo.

    If buffer is True or file is - or pipe:, loop_stream will be used to loop
    the audio. Otherwise, -stream_loop -1 will be used.

    """
    if filename == "-":
        filename = "pipe:"
    if buffer is None:
        buffer = filename == "pipe:"
    if input_args is None:
        input_args = []
    if input_kwargs is not None:
        import warnings
        warnings.warn(
            "pass input_args instead",
            DeprecationWarning,
            stacklevel=2,
        )
        input_args = [*input_args, *[
            arg
            for option, value in input_kwargs.items()
            for arg in [f"-{option}", value]
        ]]

    if not buffer:
        # -1 means to loop forever
        input_args = [*input_args, "-stream_loop", -1]

    # Create stream from FFmpeg subprocess
    stream = soundit.chunked_ffmpeg_process(
        soundit.create_ffmpeg_process(*map(str, [
            *input_args,
            "-i", filename,
            *_PCM_ARGS,
            "pipe:",
            "-loglevel", "error",  # Quieter output
            "-nostdin",
        ]))
    )

    if buffer:
        # Loop forever using an in memory buffer if necessary
        stream = soundit.loop_stream(stream)

    yield from stream

# - Looping audio stream

def loop_stream(
    data_iterable: Iterable[bytes],
    *,
    copy: Optional[bool] = True,
    when_empty: Optional[Literal["ignore", "error"]] = "error",
) -> Iterator[bytes]:
    """Consumes a stream of buffers and loops them forever

    Deprecated: use soundit.loop_stream instead

    - data_iterable: the iterable of buffers
    - copy => True: whether or not to copy the buffers
    - when_empty => "error": what to do when data is empty (ignore or error)

    The buffers are reused upon looping. If the buffers are known to be unused
    after being yielded, you can set copy to False to save some time copying.

    When sum(len(b) for b in buffers) == 0, a RuntimeError will be raised.
    Otherwise, this function can end up in an infinite loop, or it can cause
    other functions to never yield (such as equal_chunk_stream). This behaviour
    is almost never useful, though if necessary, pass when_empty="ignore" to
    suppress the error.

    """
    import warnings
    warnings.warn(
        "use soundit.loop_stream instead",
        DeprecationWarning,
        stacklevel=2,
    )
    return soundit.loop_stream(data_iterable, copy=copy, when_empty=when_empty)

# - Chunking audio stream

def equal_chunk_stream(
    data_iterable: Iterable[bytes],
    buffer_len: int,
) -> Iterator[bytes]:
    """Normalizes a stream of buffers into ones of length buffer_len

    Deprecated: use soundit.equal_chunk_stream instead

    - data_iterable is the iterable of buffers.
    - buffer_len is the size to normalize buffers to

    Note that the yielded buffer is not guaranteed to be unchanged. Basically,
    create a copy if it needs to be used for longer than a single iteration. It
    may be reused inside this function to reduce object creation and
    collection.

    The last buffer yielded is always smaller than buffer_len. Other code can
    fill it with zeros, drop it, or execute clean up code.

        >>> list(map(bytes, equal_chunk_stream([b"abcd", b"efghi"], 3)))
        [b'abc', b'def', b'ghi', b'']
        >>> list(map(bytes, equal_chunk_stream([b"abcd", b"efghijk"], 3)))
        [b'abc', b'def', b'ghi', b'jk']
        >>> list(map(bytes, equal_chunk_stream([b"a", b"b", b"c", b"d"], 3)))
        [b'abc', b'd']
        >>> list(map(bytes, equal_chunk_stream([], 3)))
        [b'']
        >>> list(map(bytes, equal_chunk_stream([b"", b""], 3)))
        [b'']
        >>> list(map(bytes, equal_chunk_stream([b"", b"", b"a", b""], 3)))
        [b'a']

    """
    import warnings
    warnings.warn(
        "use soundit.equal_chunk_stream instead",
        DeprecationWarning,
        stacklevel=2,
    )
    return soundit.equal_chunk_stream(data_iterable, buffer_len)

# - Playing audio

def play_stream(
    stream: Iterable[bytes],
    *,
    output: Optional[sounddevice.RawOutputStream] = None,
) -> None:
    """Plays a stream

    Deprecated: use soundit.play_output_chunks or output.write instead

    - data_iterable is the 48000 Hz signed 16-bit little endian stereo audio
    - output is an optional output stream (should have same format)

    """
    import warnings
    warnings.warn(
        "use soundit.play_output_chunks or output.write instead",
        DeprecationWarning,
        stacklevel=2,
    )

    if output is None:
        soundit.play_output_chunks(stream)
    else:
        # Caller is responsible for closing the output stream
        for chunk in stream:
            output.write(chunk)

# - Command line

# Modified from argparse._HelpAction (it immediately exits when specified)
class _ListDevicesAction(argparse.Action):
    def __call__(self, parser: argparse.ArgumentParser, *_: Any) -> NoReturn:
        print(str(sounddevice.query_devices()))
        parser.exit()

# Delay version retrieval (because it's kinda slow)
class _VersionAction(argparse.Action):
    def __call__(self, parser: argparse.ArgumentParser, *_: Any) -> NoReturn:
        try:
            # TODO: Replace with importlib_metadata.version when it's typed
            version = importlib_metadata.metadata("playbacque")["version"]
        except importlib_metadata.PackageNotFoundError:
            version = "UNKNOWN"
        print(f"{parser.prog} {version}")
        parser.exit()

parser: Final = argparse.ArgumentParser(
    description="Loop play audio",
)
parser.add_argument(
    "filename",
    help="file to play, use - for stdin",
)
parser.add_argument(
    "-b", "--buffer",
    action="store_true",
    default=None,
    help="force a buffer to be used for looping (such as for URLs)",
)
parser.add_argument(
    "-p", "--pcm",
    action="store_true",
    help="file is PCM audio (48000 Hz signed 16-bit little endian stereo)",
)
out_group = parser.add_mutually_exclusive_group()
out_group.add_argument(
    "-o", "--out",
    action="store_true",
    help="output PCM audio to stdout instead of playing it",
)
out_group.add_argument(
    "-D", "--device",
    type=int,
    help="play to the specified device instead of the default",
)
parser.add_argument(
    "-L", "--list-devices",
    action=_ListDevicesAction,
    nargs=0,
    help="show detected devices in python-sounddevice format and exit",
)
parser.add_argument(
    "-V", "--version",
    action=_VersionAction,
    nargs=0,
    help="show program's version number and exit",
)

def main(argv: Optional[List[str]] = None) -> NoReturn:
    """Command line entry point

    - argv => sys.argv[1:]

    """
    if argv is None:
        argv = sys.argv[1:]

    args = parser.parse_args(argv)
    file = args.filename

    if file == "-":
        file = "pipe:"

    input_args = None
    if args.pcm:
        input_args = _PCM_ARGS

    # Create stream (with PCM input if specified)
    stream = loop_stream_ffmpeg(
        file,
        buffer=args.buffer,
        input_args=input_args,
    )

    try:
        if args.out:
            try:
                # Output to stdout if specified
                _write = sys.stdout.buffer.write
                for chunk in stream:
                    _write(chunk)

            except BrokenPipeError:
                parser.exit(message="error: stdout closed")

            # We could get an OSError: [Errno 22] Invalid argument if stdout is
            # closed before we manage to output anything (for some reason)
            except OSError as e:
                if e.errno != errno.EINVAL:
                    raise
                parser.exit(message="error: stdout closed")

        elif args.device is not None:
            # Play to the specified device
            soundit.play_output_chunks(stream, device=args.device)

        else:
            # Play to default device
            play_stream(stream)

    except KeyboardInterrupt:
        parser.exit()

    else:
        parser.exit(1)  # FFmpeg probably has printed an error to stderr

if __name__ == "__main__":
    main()
