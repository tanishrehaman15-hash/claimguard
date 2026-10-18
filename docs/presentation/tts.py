"""Generate both presenters' lines, process them to sound like a mic recording, and build the timeline."""
import json
import re
import subprocess
from pathlib import Path

import imageio_ffmpeg

from script import GAP_SAME, GAP_SWITCH, SCENE_TAIL, SCENES, TEMPO, VOICES

HERE = Path(__file__).parent
BUILD = HERE / "build"
VOICE = BUILD / "voice"
FF = imageio_ffmpeg.get_ffmpeg_exe()
LEAD = 0.9  # music sting before the first word

# Gentle "recorded with a decent USB mic in a small room" chain.
CHAIN = {
    "T": "highpass=f=110,equalizer=f=3200:t=q:w=1.2:g=2,lowpass=f=11500",
    "R": "highpass=f=80,equalizer=f=180:t=q:w=1:g=1.5,equalizer=f=3000:t=q:w=1.2:g=1.5,lowpass=f=11000",
}
POST = "acompressor=threshold=-20dB:ratio=2.5:attack=8:release=120,aecho=0.85:0.6:22|37:0.10|0.06,volume=1.6"


def duration(path):
    out = subprocess.run([FF, "-i", str(path)], capture_output=True, text=True).stderr
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def main():
    VOICE.mkdir(parents=True, exist_ok=True)
    t = LEAD
    timeline = {"scenes": [], "lines": []}
    idx = 0
    for sid, lines in SCENES:
        scene = {"id": sid, "start": round(t, 3), "lines": []}
        for j, (spk, spoken, caption) in enumerate(lines):
            raw, wav = VOICE / f"{idx:02d}.aiff", VOICE / f"{idx:02d}.wav"
            subprocess.run(["say", "-v", VOICES[spk], "-o", str(raw), spoken], check=True)
            subprocess.run([FF, "-y", "-loglevel", "error", "-i", str(raw), "-af",
                            f"atempo={TEMPO[spk]},{CHAIN[spk]},{POST},aresample=48000", "-ac", "2", str(wav)],
                           check=True)
            d = duration(wav)
            line = {"i": idx, "speaker": spk, "text": caption, "start": round(t, 3), "end": round(t + d, 3),
                    "scene": sid, "n": j}
            timeline["lines"].append(line)
            scene["lines"].append(idx)
            nxt = lines[j + 1][0] if j + 1 < len(lines) else None
            t += d + (SCENE_TAIL if nxt is None else GAP_SAME if nxt == spk else GAP_SWITCH)
            idx += 1
        scene["end"] = round(t, 3)
        timeline["scenes"].append(scene)
    timeline["duration"] = round(t + 1.2, 3)  # let the end card breathe
    (BUILD / "timeline.json").write_text(json.dumps(timeline, indent=1))
    for s in timeline["scenes"]:
        print(f"{s['id']:9s} {s['start']:6.1f} -> {s['end']:6.1f}  ({s['end'] - s['start']:.1f}s)")
    print("TOTAL", timeline["duration"])


if __name__ == "__main__":
    main()
