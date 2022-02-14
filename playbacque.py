"""Loop play audio"""

import argparse
import sys
import collections
import contextlib
import subprocess
import errno
if sys.version_info >= (3, 8):
    import importlib.metadata as importlib_metadata
else:
    import importlib_metadata

from typing import (
    TYPE_CHECKING, Optional, Any, Iterable, List, Dict, Deque, Iterator,
    NoReturn,
)
if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias
if sys.version_info >= (3, 8):
    from typing import Literal, Final
else:
    from typing_extensions import Literal, Final

import sounddevice  # type: ignore[import]
import ffmpeg  # type: ignore[import]

# FFmpeg arguments for PCM audio
_PCM_KWARGS: Final = dict(f="s16le", ar=48000, ac=2)

# sounddevice arguments for PCM audio
_PCM_SETTINGS: Final = dict(samplerate=48000, channels=2, dtype="int16")

# - Streaming audio

def loop_stream_ffmpeg(
    filename: str,
    *,
    buffer: Optional[bool] = None,
    input_kwargs: Optional[Dict[str, Any]] = None,
) -> Iterator[bytes]:
    """Forever yields audio chunks from the file using FFmpeg

    - filename is the file to loop (can be - or pipe: to use stdin)
    - buffer => file in ("pipe:", "-"): whether to buffer in memory to loop
    - input_kwargs => {}: specify extra input arguments (useful for PCM files)

    The yielded chunks are hard coded to be 48000 Hz signed 16-bit little
    endian stereo.

    If buffer is True or file is - or pipe:, loop_stream will be used to
    loop the audio. Otherwise, -stream_loop -1 will be used.

    """
    if filename == "-":
        filename = "pipe:"
    if buffer is None:
        buffer = filename == "pipe:"
    if input_kwargs is None:
        input_kwargs = {}

    if not buffer:
        # -1 means to loop forever
        input_kwargs = {**input_kwargs, "stream_loop": -1}

    # Create stream from FFmpeg subprocess
    stream = _stream_subprocess(
        ffmpeg
            .input(filename, **input_kwargs)  # noqa: E131
            .output("pipe:", **_PCM_KWARGS)
            .global_args("-loglevel", "error", "-nostdin")  # Quieter output
            .run_async(pipe_stdout=True)
    )

    if buffer:
        # Loop forever using an in memory buffer if necessary
        stream = loop_stream(stream)

    yield from stream

# - Streaming process stdout

if TYPE_CHECKING or sys.version_info >= (3, 9):
    Popen: TypeAlias = subprocess.Popen[bytes]
else:
    Popen: TypeAlias = subprocess.Popen

def _stream_subprocess(
    process: Popen,
    *,
    close: Optional[bool] = True,
) -> Iterator[bytes]:
    """Yield chunks from the process's stdout

    - process is the subprocess to stream stdout from
    - close => True: whether to terminate the process when finished

    """
    if close is None:
        close = True

    if process.stdout is None:
        raise ValueError("process has no stdout")

    _read = process.stdout.read  # Remove attribute lookup
    stream = iter(lambda: _read(65536), b"")  # Yield until b""

    if not close:
        # Stream stdout until EOF
        yield from stream
        return

    with process:
        try:
            yield from stream
        finally:
            # Terminating instead of closing pipes makes FFmpeg not cry
            # "Error writing trailer of pipe:: Broken pipe" on .mp3s
            process.terminate()

# - Looping audio stream

def loop_stream(
    data_iterable: Iterable[bytes],
    *,
    copy: Optional[bool] = True,
    when_empty: Optional[Literal["ignore", "error"]] = "error",
) -> Iterator[bytes]:
    """Consumes a stream of buffers and loops them forever

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
    if copy is None:
        copy = True
    if when_empty is None:
        when_empty = "error"
    if when_empty not in ("ignore", "error"):
        raise ValueError("when_empty must be ignore or error")
    data_iterator = iter(data_iterable)

    # Deques have a guaranteed O(1) append; lists have worst case O(n)
    data_buffers: Deque[bytes] = collections.deque()
    data_buffers_size = 0

    if copy:
        # Read and copy data until empty
        while True:
            data = next(data_iterator, None)
            if data is None:
                break
            data = bytes(data)  # copy = True
            data_buffers.append(data)
            data_buffers_size += len(data)
            yield data

    else:
        # Read data until empty
        while True:
            data = next(data_iterator, None)
            if data is None:
                break
            data_buffers.append(data)
            data_buffers_size += len(data)
            yield data

    # Sanity check for empty buffer length
    if when_empty == "error" and data_buffers_size == 0:
        raise RuntimeError("empty data buffers")

    # Yield buffers forever
    while True:
        yield from data_buffers

# - Chunking audio stream

def equal_chunk_stream(
    data_iterable: Iterable[bytes],
    buffer_len: int,
) -> Iterator[bytes]:
    """Normalizes a stream of buffers into ones of length buffer_len

    - data_iterable is the iterable of buffers.
    - buffer_len is the size to normalize buffers to

    Note that the yielded buffer is not guaranteed to be unchanged. Basically,
    create a copy if it needs to be used for longer than a single iteration.
    It may be reused inside this function to reduce object creation and
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
    if not buffer_len > 0:
        raise ValueError("buffer length is not positive")
    data_iterator = iter(data_iterable)

    # Initialize buffer / data variables
    buffer = memoryview(bytearray(buffer_len))
    buffer_ptr = 0
    data = b""
    data_ptr = 0
    data_len = len(data)

    while True:
        # Buffer is full. This must come before the data checking so that the
        # final chunk always passes an if len(chunk) != buffer_len.
        if buffer_ptr == buffer_len:
            yield buffer
            buffer_ptr = 0

        # Data is consumed
        if data_ptr == data_len:
            data_item = next(data_iterator, None)
            if data_item is None:
                # Yield everything that we have left (could be b"") so that
                # other code can simply check the length to know if the stream
                # is ending.
                yield buffer[:buffer_ptr]
                return
            data = memoryview(data_item)
            data_ptr = 0
            data_len = len(data)

        # Either fill up the buffer or consume the data (or both)
        take = min(buffer_len - buffer_ptr, data_len - data_ptr)
        buffer[buffer_ptr:buffer_ptr + take] = data[data_ptr:data_ptr + take]
        buffer_ptr += take
        data_ptr += take

# - Playing audio

def play_stream(
    stream: Iterable[bytes],
    *,
    output: Optional[sounddevice.RawOutputStream] = None,
) -> None:
    """Plays a stream

    - data_iterable is the 48000 Hz signed 16-bit little endian stereo audio
    - output is an optional output stream (should have same format)

    """
    if output is None:
        output = sounddevice.RawOutputStream(**_PCM_SETTINGS)
    else:
        # Caller is responsible for closing the output stream
        output = contextlib.nullcontext(output)

    with output as output:
        blocksize = output.blocksize

        if not blocksize:
            # Blocksize is 20 ms * dtype * channels
            blocksize = round(output.samplerate * 0.02) * output.samplesize

        # Using the specified blocksize is better for performance
        for chunk in equal_chunk_stream(stream, blocksize):
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
            # Alternative to importlib_metadata.version (which isn't typed)
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

    input_kwargs = None
    if args.pcm:
        input_kwargs = _PCM_KWARGS

    # Create stream (with PCM input if specified)
    stream = loop_stream_ffmpeg(
        file,
        buffer=args.buffer,
        input_kwargs=input_kwargs,
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
            with sounddevice.RawOutputStream(
                device=args.device,
                **_PCM_SETTINGS,
            ) as output:
                play_stream(stream, output=output)

        else:
            # Play to default device
            play_stream(stream)

    except KeyboardInterrupt:
        parser.exit()

    else:
        parser.exit(1)  # FFmpeg probably has printed an error to stderr

if __name__ == "__main__":
    main()
