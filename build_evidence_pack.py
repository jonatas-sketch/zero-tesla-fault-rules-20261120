"""Build a local, timestamped evidence pack for a video the reviewer can access."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile
import wave

FRAME_INTERVAL = 2


def run(*command):
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout


def source_digest(video):
    digest = hashlib.sha256()
    with video.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_video(video):
    metadata = json.loads(run(
        "ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
        "-of", "json", str(video),
    ))
    duration = float(metadata["format"]["duration"])
    tracks = {stream.get("codec_type") for stream in metadata.get("streams", [])}
    if not math.isfinite(duration) or duration <= 0 or "video" not in tracks:
        raise ValueError("Expected a finite, positive-duration video track")
    return duration, "audio" in tracks


def extract_frames(video, frames, duration):
    frames.mkdir()
    expected_count = math.ceil(duration / FRAME_INTERVAL)
    run(
        "ffmpeg", "-v", "error", "-nostdin", "-copyts", "-start_at_zero",
        "-i", str(video), "-map", "0:v:0", "-an",
        "-vf", f"fps=1/{FRAME_INTERVAL}:start_time=0:round=up:eof_action=pass,scale='min(768,iw)':-2",
        "-frames:v", str(expected_count), "-start_number", "0", str(frames / "frame-%06d.jpg"),
    )
    images = sorted(frames.glob("frame-*.jpg"))
    if len(images) != expected_count:
        raise ValueError(f"Expected {expected_count} sampled frames, found {len(images)}")
    return [
        {"timestamp_seconds": index * FRAME_INTERVAL, "file": f"frames/{image.name}"}
        for index, image in enumerate(images)
    ]


def transcribe(video, output, model_name, duration):
    import numpy as np
    from faster_whisper import WhisperModel

    audio = output / "temporary-audio.wav"
    run(
        "ffmpeg", "-v", "error", "-nostdin", "-copyts", "-start_at_zero",
        "-i", str(video), "-map", "0:a:0", "-vn",
        "-af", "aresample=async=1:first_pts=0", "-ar", "16000", "-ac", "1", str(audio),
    )
    model = WhisperModel(model_name, device="cpu", compute_type="int8", local_files_only=True)
    with wave.open(str(audio), "rb") as stream:
        pcm = stream.readframes(stream.getnframes())
    waveform = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768
    segments, _ = model.transcribe(waveform, word_timestamps=True, vad_filter=True)
    words = []
    for segment in segments:
        for word in segment.words or []:
            start = round(word.start, 3)
            end = round(word.end, 3)
            if start < 0 or end < start or end > duration + 0.1:
                raise ValueError(f"Word timestamp outside source timeline: {start}–{end}")
            if start < duration and word.word.strip():
                words.append({
                    "word": word.word.strip(),
                    "start_seconds": start,
                    "end_seconds": round(min(end, duration), 3),
                })
    audio.unlink()
    return words


def build_pack(video, output_root, clip_id, source_kind, model_name):
    if not clip_id.replace("-", "").replace("_", "").isalnum():
        raise ValueError("Use only letters, numbers, underscores, and hyphens for the clip ID")
    duration, audio_present = inspect_video(video)
    output_root.mkdir(parents=True, exist_ok=True)
    destination = output_root / clip_id
    if destination.exists():
        raise FileExistsError(f"Evidence pack already exists: {destination}")

    with tempfile.TemporaryDirectory(prefix=f".{clip_id}-", dir=output_root) as temp:
        work = Path(temp) / "pack"
        work.mkdir()
        frames = extract_frames(video, work / "frames", duration)
        words = transcribe(video, work, model_name, duration) if audio_present else []
        pack = {
            "clip_id": clip_id,
            "source_kind": source_kind,
            "source_filename": video.name,
            "source_sha256": source_digest(video),
            "duration_seconds": duration,
            "frame_interval_seconds": FRAME_INTERVAL,
            "frames": frames,
            "transcript_status": (
                "transcribed" if words else "no_speech_detected" if audio_present else "no_audio_track"
            ),
            "words": words,
        }
        (work / "pack.json").write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n")
        work.rename(destination)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--id", required=True)
    parser.add_argument("--source-kind", choices=["synthetic_test", "candidate", "reviewer_source"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="base", help="Cached local faster-whisper model name or directory")
    args = parser.parse_args()
    print(build_pack(args.video.resolve(), args.output.resolve(), args.id, args.source_kind, args.model))


if __name__ == "__main__":
    main()
