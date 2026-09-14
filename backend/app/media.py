"""Local media pipeline: TTS audio (gTTS) + slide PNGs (Pillow) + video (moviepy).

Zero-cost, no external video API. Every step degrades gracefully:
- no internet  -> silent WAV placeholder instead of TTS mp3
- no ffmpeg/moviepy -> slides + audio still served, video_url stays None
"""
from __future__ import annotations

import textwrap
import wave
from pathlib import Path

from .config import settings

MEDIA_ROOT = Path(__file__).resolve().parent.parent / settings.media_dir
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

SLIDE_W, SLIDE_H = 1280, 720


def _lecture_dir(course_id: str, lecture_id: str) -> Path:
    d = MEDIA_ROOT / course_id / lecture_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _narration_text(title: str, body_markdown: str, key_points: list[str]) -> str:
    # Strip markdown noise for cleaner speech.
    import re

    text = re.sub(r"^#+\s*", "", body_markdown, flags=re.M)
    text = re.sub(r"[*_`>-]", "", text)
    text = " ".join(text.split())
    kp = "; ".join(key_points[:4])
    script = f"{title}. {text}"
    if kp:
        script += f" Key points: {kp}."
    return script[:4000]  # gTTS handles ~4k chars fine


def _silent_wav(path: Path, seconds: int) -> Path:
    path = path.with_suffix(".wav")
    framerate = 22050
    nframes = max(1, seconds * framerate)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(framerate)
        w.writeframes(b"\x00\x00" * nframes)
    return path


def make_audio(course_id: str, lecture_id: str, title: str, body: str, key_points: list[str]) -> str | None:
    """Returns public URL path like /media/<course>/<lecture>/audio.mp3|wav, or None."""
    d = _lecture_dir(course_id, lecture_id)
    script = _narration_text(title, body, key_points)
    mp3 = d / "audio.mp3"
    try:
        from gtts import gTTS

        # Keep each request short; gTTS is happier with chunks.
        tts = gTTS(text=script[:3500] or title, lang="en", slow=False)
        tts.save(str(mp3))
        return f"/media/{course_id}/{lecture_id}/audio.mp3"
    except Exception as e:
        print(f"[media] gTTS failed, writing silent WAV: {e}")
        wav = _silent_wav(d / "audio.wav", seconds=max(10, min(300, len(script.split()) // 2)))
        return f"/media/{course_id}/{lecture_id}/{wav.name}"


def make_slides(course_id: str, lecture_id: str, title: str, key_points: list[str]) -> list[str]:
    """Render title slide + one slide per key point (max 5). Returns public URL paths."""
    from PIL import Image, ImageDraw, ImageFont

    d = _lecture_dir(course_id, lecture_id)
    pages = [title] + (key_points[:4] or ["Overview"])
    urls: list[str] = []
    try:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()
    except Exception:
        font_big = font_small = None  # type: ignore

    for i, text in enumerate(pages):
        img = Image.new("RGB", (SLIDE_W, SLIDE_H), (17, 24, 39))
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, SLIDE_W, 110], fill=(37, 99, 235))
        draw.text((60, 30), f"Slide {i + 1}/{len(pages)}", fill=(219, 234, 254), font=font_small)
        wrapped = textwrap.wrap(text, width=34)
        y = 200
        for line in wrapped[:8]:
            draw.text((60, y), line, fill=(255, 255, 255), font=font_big)
            y += 60
        if i == 0:
            draw.text((60, SLIDE_H - 100), "Medash Academy", fill=(147, 197, 253), font=font_small)
        fname = f"slide_{i + 1}.png"
        img.save(d / fname)
        urls.append(f"/media/{course_id}/{lecture_id}/{fname}")
    return urls


def _audio_duration(path: str) -> float | None:
    """Probe duration via ffmpeg's stderr (no ffprobe needed)."""
    import re
    import subprocess

    try:
        exe = _ffmpeg_exe()
        p = subprocess.run([exe, "-i", path], capture_output=True, text=True, timeout=30)
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", p.stderr or "")
        if not m:
            return None
        h, mi, s, ms = int(m[1]), int(m[2]), int(m[3]), int(m[4])
        return float(h * 3600 + mi * 60 + s + ms / 100.0)
    except Exception:
        return None


def _ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def make_video(course_id: str, lecture_id: str, slide_files: list[str], audio_file: str | None) -> str | None:
    """Mux slides + narration into lecture.mp4 using ffmpeg directly (fast, no per-frame Python)."""
    import subprocess

    if not slide_files:
        return None
    d = _lecture_dir(course_id, lecture_id)
    out = d / "lecture.mp4"
    total = max(1, len(slide_files))
    audio_path = str(d / Path(audio_file).name) if audio_file else None
    audio_dur = _audio_duration(audio_path) if audio_path else None
    per_slide = (audio_dur / total) if audio_dur else 6.0
    try:
        cmd = [_ffmpeg_exe(), "-y"]
        for sf in slide_files:
            cmd += ["-loop", "1", "-t", f"{per_slide:.3f}", "-i", str(d / Path(sf).name)]
        if audio_path:
            cmd += ["-i", audio_path]
        filt = f"[0:v][1:v]" + "".join(f"[{i}:v]" for i in range(2, total)) + f"concat=n={total}:v=1:a=0[v]"
        cmd += ["-filter_complex", filt, "-map", "[v]"]
        if audio_path:
            cmd += ["-map", f"{total}:a"]
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-movflags", "+faststart", "-r", "15", "-shortest", str(out)]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if p.returncode != 0 or not out.exists():
            print(f"[media] ffmpeg failed: {(p.stderr or '')[-500:]}")
            return None
        return f"/media/{course_id}/{lecture_id}/lecture.mp4"
    except Exception as e:
        print(f"[media] video render skipped: {e}")
        return None
