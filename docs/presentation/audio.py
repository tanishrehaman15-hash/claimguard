"""Original background music, sound effects and the final audio mix (all synthesised with numpy).

Writes build/music.wav, build/sfx_cues.json and build/mix.wav.
"""
import json
import subprocess
from pathlib import Path

import imageio_ffmpeg
import numpy as np

HERE = Path(__file__).parent
BUILD = HERE / "build"
FF = imageio_ffmpeg.get_ffmpeg_exe()
SR = 48000
TL = json.loads((BUILD / "timeline.json").read_text())
DUR = TL["duration"]
N = int(DUR * SR)
BPM = 104
BEAT = 60 / BPM
rng = np.random.default_rng(7)

NOTE = {"A2": 110.0, "C3": 130.81, "D3": 146.83, "E3": 164.81, "F2": 87.31, "F3": 174.61, "G2": 98.0, "G3": 196.0,
        "A3": 220.0, "B3": 246.94, "C4": 261.63, "D4": 293.66, "E4": 329.63, "F4": 349.23, "G4": 392.0, "A4": 440.0,
        "B4": 493.88, "C5": 523.25, "E5": 659.25, "D5": 587.33, "G5": 783.99}
# Am - F - C - G : hopeful, techy, student-presentation energy
CHORDS = [("A2", ["A3", "C4", "E4"], ["A4", "C5", "E5", "C5"]),
          ("F2", ["F3", "A3", "C4"], ["A4", "C5", "F4", "C5"]),
          ("C3", ["C4", "E4", "G4"], ["G4", "C5", "E5", "C5"]),
          ("G2", ["G3", "B3", "D4"], ["G4", "B4", "D5", "B4"])]


def scene_span(sid):
    s = next(x for x in TL["scenes"] if x["id"] == sid)
    return s["start"], s["end"]


def env_adsr(n, a, d, s, r):
    a, d, r = int(a * SR), int(d * SR), int(r * SR)
    e = np.full(n, s, dtype=np.float32)
    e[:a] = np.linspace(0, 1, a)
    e[a:a + d] = np.linspace(1, s, max(d, 1))[: max(0, min(d, n - a))]
    if r:
        e[-r:] *= np.linspace(1, 0, r)
    return e


def onepole_lp(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    # vectorised IIR via scipy-free trick: process in python only for short buffers
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def saw(freq, n, detune=0.0):
    t = np.arange(n) / SR
    return (2 * ((t * freq * (1 + detune)) % 1.0) - 1).astype(np.float32)


def section_gain(t):
    """Per-layer intensity across the video, following the story."""
    g = {"pad": np.ones_like(t) * 0.0, "arp": np.zeros_like(t), "drums": np.zeros_like(t), "bass": np.zeros_like(t)}
    plan = {  # scene: (pad, arp, drums, bass)
        "hook": (0.6, 0.0, 0.0, 0.3), "intro": (1.0, 1.0, 1.0, 1.0), "problem": (0.9, 0.35, 0.0, 0.6),
        "solution": (1.0, 0.9, 0.8, 1.0), "how": (1.0, 1.0, 0.7, 1.0), "demo": (0.8, 0.7, 0.6, 0.8),
        "results": (1.0, 1.0, 1.0, 1.0), "ibmz": (1.0, 0.8, 0.8, 1.0), "close": (1.0, 0.5, 0.0, 0.8)}
    for sc in TL["scenes"]:
        m = (t >= sc["start"]) & (t < sc["end"])
        for k, v in zip(("pad", "arp", "drums", "bass"), plan[sc["id"]]):
            g[k][m] = v
    m = t < TL["scenes"][0]["start"]
    g["pad"][m] = 0.5
    end = TL["scenes"][-1]["end"]
    m = t >= end
    for k in g:
        g[k][m] = 0.0
    g["pad"][m] = 1.0
    # smooth transitions (~0.4 s)
    k = int(0.4 * 200)
    for name in g:
        coarse = g[name][:: SR // 200]
        sm = np.convolve(coarse, np.ones(k) / k, mode="same")
        g[name] = np.interp(t, np.arange(len(sm)) / 200, sm).astype(np.float32)
    return g


def music():
    t = np.arange(N) / SR
    bar = 4 * BEAT
    pad = np.zeros(N, np.float32)
    arp = np.zeros(N, np.float32)
    bass = np.zeros(N, np.float32)
    kick = np.zeros(N, np.float32)
    hats = np.zeros(N, np.float32)
    clap = np.zeros(N, np.float32)
    n_bars = int(DUR / bar) + 1
    bar_n = int(bar * SR)

    # pad: detuned saws per chord, filtered once per chord voicing (cached)
    cache = {}
    for b in range(n_bars):
        root, triad, _ = CHORDS[b % 4]
        key = tuple(triad)
        if key not in cache:
            x = sum(saw(NOTE[nm], bar_n, d) for nm in triad for d in (-0.004, 0.0, 0.005)) / 9
            cache[key] = onepole_lp(x, 1400.0) * env_adsr(bar_n, 0.25, 0.3, 0.85, 0.3)
        s = b * bar_n
        seg = cache[key][: max(0, min(bar_n, N - s))]
        pad[s:s + len(seg)] += seg

    # arp: 16th-note plucks
    step = BEAT / 4
    pl_n = int(0.22 * SR)
    pt = np.arange(pl_n) / SR
    pluck_env = np.exp(-pt * 18).astype(np.float32)
    for i in range(int(DUR / step)):
        b = int(i * step / bar)
        notes = CHORDS[b % 4][2]
        f = NOTE[notes[i % 4]]
        tone = (np.sin(2 * np.pi * f * pt) + 0.3 * np.sin(4 * np.pi * f * pt)) * pluck_env
        s = int(i * step * SR)
        seg = tone[: max(0, min(pl_n, N - s))]
        arp[s:s + len(seg)] += seg.astype(np.float32) * (1.0 if i % 4 == 0 else 0.7)

    # bass: 8th notes on the root
    b_n = int(BEAT / 2 * SR)
    bt = np.arange(b_n) / SR
    for i in range(int(DUR / (BEAT / 2))):
        b = int(i * BEAT / 2 / bar)
        f = NOTE[CHORDS[b % 4][0]]
        tone = np.sin(2 * np.pi * f * bt) * np.exp(-bt * 6)
        s = i * b_n
        seg = tone[: max(0, min(b_n, N - s))]
        bass[s:s + len(seg)] += seg.astype(np.float32)

    # drums
    k_n = int(0.35 * SR)
    kt = np.arange(k_n) / SR
    k_wave = np.sin(2 * np.pi * np.cumsum(45 + 110 * np.exp(-kt * 30)) / SR) * np.exp(-kt * 9)
    h_n = int(0.05 * SR)
    c_n = int(0.18 * SR)
    for i in range(int(DUR / BEAT)):
        s = int(i * BEAT * SR)
        seg = k_wave[: max(0, min(k_n, N - s))]
        kick[s:s + len(seg)] += seg.astype(np.float32)
        hs = int((i + 0.5) * BEAT * SR)
        if hs + h_n < N:
            noise = rng.standard_normal(h_n)
            hats[hs:hs + h_n] += (np.diff(noise, prepend=0) * np.exp(-np.arange(h_n) / SR * 80)).astype(np.float32)
        if i % 2 == 1 and s + c_n < N:
            noise = rng.standard_normal(c_n)
            clap[s:s + c_n] += (noise * np.exp(-np.arange(c_n) / SR * 25)).astype(np.float32)

    # sidechain pump from the kick
    pump = np.ones(N, np.float32)
    for i in range(int(DUR / BEAT)):
        s = int(i * BEAT * SR)
        L = min(int(BEAT * SR), N - s)
        pump[s:s + L] = 1 - 0.45 * np.exp(-np.arange(L) / SR * 9)

    g = section_gain(t.astype(np.float32))
    drums_on = g["drums"]
    pump_mix = 1 - (1 - pump) * drums_on
    left = (0.55 * pad * g["pad"] * pump_mix + 0.22 * arp * g["arp"] + 0.5 * bass * g["bass"] * pump_mix
            + drums_on * (0.9 * kick + 0.05 * hats + 0.12 * clap))
    right = np.roll(left, int(0.012 * SR)) * 0.6 + left * 0.4  # a little width
    out = np.stack([left, right], 1)
    out /= np.abs(out).max() + 1e-9
    fade = int(1.5 * SR)
    out[-fade:] *= np.linspace(1, 0, fade)[:, None]
    return (out * 0.9).astype(np.float32)


# ------------------------------------------------------------------ sound effects
def sfx_whoosh(d=0.6, up=True):
    n = int(d * SR)
    noise = rng.standard_normal(n).astype(np.float32)
    env = np.sin(np.linspace(0, np.pi, n)) ** 2
    cut = np.linspace(400, 5000, n) if up else np.linspace(5000, 400, n)
    y = np.empty(n, np.float32)
    acc = 0.0
    for i in range(n):
        a = np.exp(-2 * np.pi * cut[i] / SR)
        acc = (1 - a) * noise[i] + a * acc
        y[i] = acc
    return y * env * 1.8


def sfx_pop(f0=700, f1=1400, d=0.09):
    n = int(d * SR)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * np.cumsum(np.linspace(f0, f1, n)) / SR) * np.exp(-t * 35)).astype(np.float32) * 0.7


def sfx_impact(d=0.8):
    n = int(d * SR)
    t = np.arange(n) / SR
    low = np.sin(2 * np.pi * np.cumsum(40 + 80 * np.exp(-t * 20)) / SR) * np.exp(-t * 5)
    noise = rng.standard_normal(n) * np.exp(-t * 30) * 0.3
    return (low + noise).astype(np.float32)


def sfx_ding():
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    return ((np.sin(2 * np.pi * 1318.5 * t) + 0.5 * np.sin(2 * np.pi * 1975.5 * t)) * np.exp(-t * 5)).astype(np.float32) * 0.45


def sfx_alert():
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    tone = np.sign(np.sin(2 * np.pi * 220 * t)) * 0.25 + np.sin(2 * np.pi * 330 * t) * 0.4
    return (tone * np.exp(-t * 4)).astype(np.float32) * 0.5


def sfx_riser(d=1.2):
    n = int(d * SR)
    t = np.arange(n) / SR
    f = np.linspace(200, 1600, n)
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * (t / d) ** 2 * 0.3 + sfx_whoosh(d) * 0.4).astype(np.float32)


def sfx_type(d=0.6):
    n = int(d * SR)
    y = np.zeros(n, np.float32)
    for k in range(int(d * 18)):
        s = int(k / 18 * SR + rng.uniform(0, 0.01) * SR)
        m = int(0.012 * SR)
        if s + m < n:
            y[s:s + m] += rng.standard_normal(m).astype(np.float32) * np.exp(-np.arange(m) / SR * 400) * 0.35
    return y


def cues():
    """Sound-effect cues, shared with the animation page so visuals hit on the same frames."""
    L = TL["lines"]
    sc = {s["id"]: s for s in TL["scenes"]}
    line = lambda scene, n: next(x for x in L if x["scene"] == scene and x["n"] == n)  # noqa: E731
    c = [("riser", 0.0)]
    c += [("impact", line("hook", 0)["start"]), ("impact", line("hook", 1)["start"] + 0.9),
          ("impact", line("hook", 2)["start"] + 2.2)]
    for s in TL["scenes"][1:]:
        c.append(("whoosh", s["start"] - 0.25))
    c += [("pop", sc["intro"]["start"] + 0.9 + 0.18 * k) for k in range(6)]
    c += [("pop", line("solution", 1)["start"] + 0.2), ("pop", line("solution", 1)["start"] + 1.9),
          ("pop", line("solution", 2)["start"] + 0.3)]
    c += [("pop", sc["how"]["start"] + 0.5 + 0.55 * k) for k in range(5)]
    c += [("ding", line("demo", 5)["start"] + 2.6), ("alert", line("demo", 6)["start"] + 1.6),
          ("type", line("demo", 4)["start"] + 1.2)]
    c += [("pop", line("results", 1)["start"] + 3.0), ("pop", line("results", 2)["start"] + 0.4),
          ("pop", line("results", 2)["start"] + 3.4)]
    c += [("pop", sc["ibmz"]["start"] + 1.6 + 0.6 * k) for k in range(4)]
    c += [("impact", sc["close"]["start"] + 0.1)]
    return sorted(c, key=lambda x: x[1])


def load(path):
    raw = subprocess.run([FF, "-loglevel", "error", "-i", str(path), "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2)


def write(path, x):
    subprocess.run([FF, "-y", "-loglevel", "error", "-f", "f32le", "-ac", "2", "-ar", str(SR), "-i", "-",
                    str(path)], input=np.ascontiguousarray(x, np.float32).tobytes(), check=True)


def main():
    m = music()
    write(BUILD / "music.wav", m)

    voice = np.zeros((N, 2), np.float32)
    for ln in TL["lines"]:
        v = load(BUILD / "voice" / f"{ln['i']:02d}.wav")
        s = int(ln["start"] * SR)
        e = min(N, s + len(v))
        voice[s:e] += v[: e - s]
    voice /= np.abs(voice).max() + 1e-9
    voice *= 0.85

    # duck music under speech (smoothed envelope)
    env = np.abs(voice).max(1)
    win = int(0.25 * SR)
    env = np.convolve(env, np.ones(win) / win, mode="same")
    talking = np.clip(env / 0.02, 0, 1)
    duck = 0.30 + 0.70 * (1 - talking)  # music at ~-10 dB under voice
    music_bed = m * (0.42 * duck)[:, None]

    fx = np.zeros((N, 2), np.float32)
    gen = {"riser": sfx_riser, "impact": sfx_impact, "whoosh": sfx_whoosh, "pop": sfx_pop, "ding": sfx_ding,
           "alert": sfx_alert, "type": sfx_type}
    vol = {"riser": 0.5, "impact": 0.55, "whoosh": 0.22, "pop": 0.25, "ding": 0.35, "alert": 0.3, "type": 0.5}
    cue_list = cues()
    for name, at in cue_list:
        y = gen[name]() * vol[name]
        s = max(0, int(at * SR))
        e = min(N, s + len(y))
        fx[s:e] += y[: e - s, None]
    (BUILD / "sfx_cues.json").write_text(json.dumps(cue_list))

    mix = voice + music_bed + fx
    mix = np.tanh(mix * 1.1) / np.tanh(1.1)  # soft limiter
    mix = mix / (np.abs(mix).max() + 1e-9) * 0.93
    write(BUILD / "mix.wav", mix)
    print("mix", round(len(mix) / SR, 1), "s, peak", round(float(np.abs(mix).max()), 3))


if __name__ == "__main__":
    main()
