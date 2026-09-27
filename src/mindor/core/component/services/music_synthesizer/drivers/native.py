from __future__ import annotations

from typing import Optional, Dict, List, Any, TYPE_CHECKING
from mindor.dsl.schema.component import MusicSynthesizerComponentConfig
from mindor.dsl.schema.action import MusicSynthesizerActionConfig, MusicSynthesizerInstrument
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.audio import PcmStreamResource
from mindor.core.utils.audio import encode_waveform_to_pcm
from ..base import MusicSynthesizerDriver, MusicSynthesizerDriverType, register_music_synthesizer_driver
from ..base import ComponentActionContext
from .common import MusicSynthesizerAction

if TYPE_CHECKING:
    import numpy as np

class BeatSequenceSynthesizer:
    """Beat-timeline sequencer that renders a stereo mix from track events.

    Kept as a plain class (not an action helper) so the pure-numpy code path
    stays free of ``asyncio`` and can be exercised from a thread executor.
    """

    _NOTE_SEMITONES: Dict[str, int] = { "C": -9, "D": -7, "E": -5, "F": -4, "G": -2, "A": 0, "B": 2 }

    def __init__(
        self,
        bpm: float,
        beats: float,
        sample_rate: int,
        channels: int,
        seed: Optional[int],
    ):
        import numpy as np

        self.bpm = bpm
        self.beats = beats
        self.sample_rate = sample_rate
        self.channels = channels

        self._seconds_per_beat = 60.0 / bpm
        self._total_samples = int(round(beats * self._seconds_per_beat * sample_rate))
        self._rng = np.random.default_rng(seed) if seed is not None else np.random.default_rng()

    def render(
        self,
        tracks: List[Dict[str, Any]],
        sidechain: Optional[Dict[str, Any]],
        master: Dict[str, Any],
    ) -> np.ndarray:
        import numpy as np

        buses: Dict[str, np.ndarray] = { track["id"]: self._render_track(track) for track in tracks }

        if sidechain:
            duck = self._render_sidechain_envelope(buses, sidechain)

            for target in sidechain["targets"]:
                if target in buses:
                    buses[target] = buses[target] * duck[:, None]

        mix = np.zeros((self._total_samples, self.channels), dtype=np.float64)

        for bus in buses.values():
            mix += bus

        mix = self._apply_master(mix, master)

        return mix

    def _render_track(self, track: Dict[str, Any]) -> np.ndarray:
        import numpy as np

        track_gain = float(track.get("gain", 1.0))
        track_pan  = float(track.get("pan", 0.0))
        buffer = np.zeros((self._total_samples, self.channels), dtype=np.float64)

        for event in track["events"]:
            instrument = event["instrument"]
            gain       = float(event.get("gain", 1.0)) * track_gain
            pan        = self._combine_pan(float(event.get("pan", 0.0)), track_pan)
            length   = event.get("length")
            length   = float(length) if length is not None else None
            params     = event.get("params", {}) or {}

            for beat in event["beat"]:
                signal       = self._render_instrument(instrument, params, length)
                start_sample = self._beat_to_sample(float(beat))

                if signal.size > 0 and start_sample < self._total_samples:
                    self._mix_samples_into_buffer(buffer, start_sample, signal, gain, pan)

        return buffer

    def _render_instrument(
        self,
        instrument: MusicSynthesizerInstrument,
        params: Dict[str, Any],
        length: Optional[float],
    ) -> np.ndarray:
        if instrument == MusicSynthesizerInstrument.KICK:
            return self._synthesize_kick(bool(params.get("big", False)))

        if instrument == MusicSynthesizerInstrument.SNARE:
            return self._synthesize_snare(float(params.get("velocity", 1.0)))

        if instrument == MusicSynthesizerInstrument.HAT:
            return self._synthesize_hat(bool(params.get("open", False)))

        if instrument == MusicSynthesizerInstrument.TICK:
            return self._synthesize_tick(float(params.get("frequency", 1760.0)))

        if instrument == MusicSynthesizerInstrument.TOM:
            return self._synthesize_tom(float(params.get("frequency", 140.0)))

        if instrument == MusicSynthesizerInstrument.POP:
            return self._synthesize_pop()

        if instrument == MusicSynthesizerInstrument.WHOOSH:
            return self._synthesize_whoosh(
                seconds=self._beats_to_seconds(length) if length is not None else 1.0,
                f0=float(params.get("f0", 200.0)),
                f1=float(params.get("f1", 6000.0)),
                peak=float(params.get("peak", 0.7)),
            )

        if instrument == MusicSynthesizerInstrument.CHORD:
            return self._synthesize_chord(
                seconds=self._beats_to_seconds(length) if length is not None else 4.0,
                notes=list(params.get("notes") or ["A3", "C4", "E4", "A4"]),
                cutoff=float(params.get("cutoff", 2000.0)),
                sweep_from=params.get("sweep_from"),
                sweep_to=params.get("sweep_to"),
            )

        if instrument == MusicSynthesizerInstrument.SUB_BASS:
            return self._synthesize_sub_bass(
                self._beats_to_seconds(length) if length is not None else 0.45,
                float(params.get("frequency", 55.0))
            )

        if instrument == MusicSynthesizerInstrument.SINE:
            return self._synthesize_sine(
                self._beats_to_seconds(length) if length is not None else 0.5,
                float(params.get("frequency", 440.0)),
                float(params.get("decay", 4.0))
            )

        if instrument == MusicSynthesizerInstrument.NOISE_BURST:
            return self._synthesize_noise_burst(
                seconds=self._beats_to_seconds(length) if length is not None else 0.25,
                kind=str(params.get("kind", "highpass")),
                freq=params.get("frequency", 3000.0),
                decay=float(params.get("decay", 20.0)),
                order=int(params.get("order", 2)),
            )

        raise ValueError(f"Unsupported instrument: {instrument}")

    def _mix_samples_into_buffer(
        self,
        buffer: np.ndarray,
        start_sample: int,
        signal: np.ndarray,
        gain: float,
        pan: float,
    ) -> None:
        import numpy as np

        if signal.ndim == 1:
            signal = signal[: self._total_samples - start_sample]
            left  = np.cos((pan + 1.0) * np.pi / 4.0)
            right = np.sin((pan + 1.0) * np.pi / 4.0)

            if self.channels == 2:
                buffer[start_sample : start_sample + signal.size, 0] += signal * gain * left
                buffer[start_sample : start_sample + signal.size, 1] += signal * gain * right
            else:
                buffer[start_sample : start_sample + signal.size, 0] += signal * gain
        else: # signal.ndim == 2
            signal = signal[: self._total_samples - start_sample]

            if self.channels == 2:
                buffer[start_sample : start_sample + signal.shape[0]] += signal * gain
            else:
                buffer[start_sample : start_sample + signal.shape[0], 0] += signal.mean(axis=1) * gain

    def _render_sidechain_envelope(
        self,
        buses: Dict[str, np.ndarray],
        sidechain: Dict[str, Any],
    ) -> np.ndarray:
        import numpy as np

        trigger_id = sidechain["trigger"]

        if trigger_id not in buses:
            return np.ones(self._total_samples, dtype=np.float64)

        depth        = float(sidechain["depth"])
        attack_time  = max(float(sidechain["attack_time"]), 1.0 / self.sample_rate)
        release_time = max(float(sidechain["release_time"]), 1.0 / self.sample_rate)

        # Detect trigger hits from the trigger track's own event beats. We
        # reconstruct them from the config indirectly by looking at samples where
        # the track has non-zero content — kicks always have a hard onset, so a
        # simple "first sample above threshold within a window" is enough.
        trigger = buses[trigger_id]
        mono_signal = trigger.mean(axis=1) if trigger.ndim == 2 else trigger
        threshold = float(np.max(np.abs(mono_signal))) * 0.5 if mono_signal.size else 0.0

        duck = np.ones(self._total_samples, dtype=np.float64)

        if threshold <= 0.0:
            return duck

        min_gap_samples = int(0.05 * self.sample_rate)
        sample_index = 0

        while sample_index < mono_signal.size:
            if abs(mono_signal[sample_index]) >= threshold:
                self._apply_duck(duck, sample_index, depth, attack_time, release_time)
                sample_index += min_gap_samples
            else:
                sample_index += 1

        return duck

    def _apply_duck(
        self,
        duck: np.ndarray,
        onset: int,
        depth: float,
        attack_time: float,
        release_time: float,
    ) -> None:
        import numpy as np

        tail_samples = duck.size - onset

        if tail_samples <= 0:
            return

        time_delta = np.arange(tail_samples) / self.sample_rate
        # Envelope: attack pulls gain down from 1.0 toward (1.0 - depth), then
        # release recovers back to 1.0 exponentially.
        curve = 1.0 - depth * np.exp(-time_delta / release_time) * (1.0 - np.exp(-time_delta / attack_time))
        duck[onset:] = np.minimum(duck[onset:], curve)

    def _apply_master(self, mix: np.ndarray, master: Dict[str, Any]) -> np.ndarray:
        import numpy as np

        soft_clip = float(master.get("soft_clip") or 0.0)

        if soft_clip > 0.0:
            mix = np.tanh(mix * soft_clip)

        normalize_level = master.get("normalize_level")

        if normalize_level is not None:
            peak = float(np.max(np.abs(mix)))
            if peak > 0.0:
                target = 10.0 ** (float(normalize_level) / 20.0)
                mix = mix * (target / peak)

        for fade in master.get("fades", []) or []:
            self._apply_fade(mix, float(fade["start_beat"]), float(fade["end_beat"]), str(fade["curve"]))

        for silence in master.get("silences", []) or []:
            self._apply_silence(mix, float(silence["start_beat"]), float(silence["end_beat"]), float(silence["pre_fade_duration"]))

        return mix

    def _apply_fade(self, mix: np.ndarray, start_beat: float, end_beat: float, curve: str) -> None:
        import numpy as np

        start = self._beat_to_sample(start_beat)
        end   = self._beat_to_sample(end_beat)
        start = max(0, min(start, self._total_samples))
        end   = max(0, min(end, self._total_samples))

        if end <= start:
            return

        ramp = np.linspace(1.0, 0.0, end - start)

        if curve == "quadratic":
            ramp = ramp ** 2

        mix[start:end] *= ramp[:, None]

        if end < self._total_samples:
            mix[end:] = 0.0

    def _apply_silence(self, mix: np.ndarray, start_beat: float, end_beat: float, pre_fade_duration: float) -> None:
        import numpy as np

        start = self._beat_to_sample(start_beat)
        end   = self._beat_to_sample(end_beat)
        start = max(0, min(start, self._total_samples))
        end   = max(0, min(end, self._total_samples))

        if end <= start:
            return

        fade_samples = max(int(pre_fade_duration * self.sample_rate), 0)

        if fade_samples > 0:
            fade_start = max(0, start - fade_samples)
            if fade_start < start:
                ramp = np.linspace(1.0, 0.0, start - fade_start)
                mix[fade_start:start] *= ramp[:, None]

        mix[start:end] = 0.0

    def _t_axis(self, seconds: float) -> np.ndarray:
        import numpy as np

        return np.arange(int(seconds * self.sample_rate)) / self.sample_rate

    def _synthesize_kick(self, big: bool) -> np.ndarray:
        import numpy as np

        time = self._t_axis(0.55 if big else 0.38)
        frequency = 48.0 + (160.0 if big else 130.0) * np.exp(-time * 38.0)
        phase = 2.0 * np.pi * np.cumsum(frequency) / self.sample_rate
        body = np.sin(phase) * np.exp(-time * (6.0 if big else 9.0))
        click = self._filter_signal(self._rng.standard_normal(time.size), "highpass", 2500.0) * np.exp(-time * 400.0) * 0.25

        return np.tanh((body + click) * 1.6)

    def _synthesize_snare(self, velocity: float) -> np.ndarray:
        import numpy as np

        time = self._t_axis(0.25)
        tone = np.sin(2.0 * np.pi * 185.0 * time) * np.exp(-time * 30.0) * 0.5
        body = self._synthesize_noise_burst(0.25, "bandpass", [900.0, 6000.0], 22.0)

        return (tone + body) * velocity

    def _synthesize_hat(self, open_: bool) -> np.ndarray:
        return self._synthesize_noise_burst(
            seconds=0.25 if open_ else 0.06,
            kind="highpass",
            freq=7500.0,
            decay=14.0 if open_ else 70.0,
            order=4,
        ) * 0.9

    def _synthesize_tick(self, frequency: float) -> np.ndarray:
        import numpy as np

        time = self._t_axis(0.05)

        return np.sin(2.0 * np.pi * frequency * time) * np.exp(-time * 90.0)

    def _synthesize_tom(self, frequency: float) -> np.ndarray:
        import numpy as np

        time = self._t_axis(0.3)
        sweep = frequency * (1.0 + 0.6 * np.exp(-time * 30.0))

        return np.sin(2.0 * np.pi * np.cumsum(sweep) / self.sample_rate) * np.exp(-time * 12.0)

    def _synthesize_pop(self) -> np.ndarray:
        import numpy as np

        time = self._t_axis(0.18)
        sweep = 300.0 * (1.0 + 3.0 * time / 0.18)

        return np.sin(2.0 * np.pi * np.cumsum(sweep) / self.sample_rate) * np.exp(-time * 18.0)

    def _synthesize_whoosh(self, seconds: float, f0: float, f1: float, peak: float) -> np.ndarray:
        import numpy as np

        time = self._t_axis(seconds)

        if time.size == 0:
            return np.zeros(0, dtype=np.float64)

        progress = time / seconds

        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            envelope = np.where(progress < peak, (progress / peak) ** 2, np.exp(-(progress - peak) / max(1e-6, 1.0 - peak) * 4.0))

        return self._swept_bandpass(self._rng.standard_normal(time.size), f0, f1) * envelope

    def _synthesize_chord(
        self,
        seconds: float,
        notes: List[str],
        cutoff: float,
        sweep_from: Optional[Any],
        sweep_to: Optional[Any],
    ) -> np.ndarray:
        import numpy as np

        sample_count = int(seconds * self.sample_rate)

        if sample_count <= 0 or not notes:
            return np.zeros((0, self.channels), dtype=np.float64)

        stack = np.zeros((sample_count, 2), dtype=np.float64)

        for note in notes:
            if not note or note[0] not in self._NOTE_SEMITONES:
                raise ValueError(f"Invalid note name: {note!r}")

            stack += self._supersaw_note(self._note_frequency(note), seconds)

        stack = stack / max(1, len(notes))

        time = np.arange(sample_count) / self.sample_rate
        envelope = np.minimum(1.0, time / 0.02) * np.minimum(1.0, (seconds - time) / 0.05)

        for channel in range(2):
            column = stack[:, channel]

            if sweep_from is not None and sweep_to is not None:
                column = self._swept_bandpass(column, float(sweep_from), float(sweep_to))
            else:
                column = self._filter_signal(column, "lowpass", cutoff, 2)

            stack[:, channel] = column * envelope

        if self.channels == 1:
            return stack.mean(axis=1)
        return stack

    def _synthesize_sub_bass(self, seconds: float, frequency: float) -> np.ndarray:
        import numpy as np

        time = self._t_axis(seconds)
        envelope = np.minimum(1.0, time / 0.005) * np.exp(-time * 4.0)

        return np.sin(2.0 * np.pi * frequency * time) * envelope

    def _synthesize_sine(self, seconds: float, frequency: float, decay: float) -> np.ndarray:
        import numpy as np

        time = self._t_axis(seconds)

        return np.sin(2.0 * np.pi * frequency * time) * np.exp(-time * decay)

    def _synthesize_noise_burst(self, seconds: float, kind: str, freq: Any, decay: float, order: int = 2) -> np.ndarray:
        import numpy as np

        time = self._t_axis(seconds)

        if time.size == 0:
            return np.zeros(0, dtype=np.float64)

        noise = self._filter_signal(self._rng.standard_normal(time.size), kind, freq, order)

        return noise * np.exp(-time * decay)

    def _supersaw_note(
        self,
        frequency: float,
        seconds: float,
        voices: int = 7,
        detune_cents: float = 14.0,
    ) -> np.ndarray:
        import numpy as np

        sample_count = int(seconds * self.sample_rate)
        output = np.zeros((sample_count, 2), dtype=np.float64)
        spread = np.linspace(-1.0, 1.0, voices)

        for offset in spread:
            detuned_frequency = frequency * 2.0 ** (offset * detune_cents / 1200.0)
            wave = self._saw_blep(detuned_frequency, seconds, phase0=float(self._rng.random()))
            pan = offset * 0.8
            output[:, 0] += wave * np.cos((pan + 1.0) * np.pi / 4.0)
            output[:, 1] += wave * np.sin((pan + 1.0) * np.pi / 4.0)

        return output / max(1, voices)

    def _saw_blep(self, frequency: float, seconds: float, phase0: float) -> np.ndarray:
        import numpy as np

        sample_count = int(seconds * self.sample_rate)

        if sample_count <= 0 or frequency <= 0:
            return np.zeros(sample_count, dtype=np.float64)

        phase_step = frequency / self.sample_rate
        phase = (phase0 + phase_step * np.arange(sample_count)) % 1.0
        wave = 2.0 * phase - 1.0

        mask = phase < phase_step
        polyblep_t = phase[mask] / phase_step
        wave[mask] -= polyblep_t + polyblep_t - polyblep_t * polyblep_t - 1.0

        mask = phase > 1.0 - phase_step
        polyblep_t = (phase[mask] - 1.0) / phase_step
        wave[mask] -= polyblep_t * polyblep_t + polyblep_t + polyblep_t + 1.0

        return wave

    def _filter_signal(self, x: np.ndarray, kind: str, freq: Any, order: int = 2) -> np.ndarray:
        from scipy.signal import butter, sosfilt

        sos = butter(order, freq, btype=kind, fs=self.sample_rate, output="sos")

        return sosfilt(sos, x)

    def _swept_bandpass(
        self,
        x: np.ndarray,
        f0: float,
        f1: float,
        q: float = 1.2,
        block_size: int = 256,
    ) -> np.ndarray:
        from scipy.signal import butter, sosfilt, sosfilt_zi
        import numpy as np

        if x.size == 0:
            return x

        output = np.zeros_like(x)
        block_count = int(np.ceil(x.size / block_size))
        zi = None
        frequency_ratio = f1 / f0 if f0 > 0 else 1.0
        nyquist = self.sample_rate / 2.0

        for block_index in range(block_count):
            center_frequency = f0 * frequency_ratio ** (block_index / max(1, block_count - 1))
            low  = max(1.0, center_frequency / (1.0 + 1.0 / (2.0 * q)))
            high = min(nyquist * 0.95, center_frequency * (1.0 + 1.0 / (2.0 * q)))

            if high <= low:
                continue

            sos = butter(2, [low, high], btype="bandpass", fs=self.sample_rate, output="sos")

            if zi is None:
                zi = sosfilt_zi(sos) * 0.0

            start = block_index * block_size
            end   = min(start + block_size, x.size)
            output[start:end], zi = sosfilt(sos, x[start:end], zi=zi)

        return output

    def _beats_to_seconds(self, length: float) -> float:
        return max(float(length) * self._seconds_per_beat, 1.0 / self.sample_rate)

    def _beat_to_sample(self, beat: float) -> int:
        return int(round(beat * self._seconds_per_beat * self.sample_rate))

    @staticmethod
    def _combine_pan(event_pan: float, track_pan: float) -> float:
        return max(-1.0, min(1.0, event_pan + track_pan))

    @classmethod
    def _note_frequency(cls, name: str) -> float:
        semitones = cls._NOTE_SEMITONES[name[0]] + 12 * (int(name[1:]) - 4)
        return 440.0 * 2.0 ** (semitones / 12.0)

class NativeMusicSynthesizerAction(MusicSynthesizerAction):
    async def _sequence(
        self,
        tracks: List[Dict[str, Any]],
        beats: float,
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> PcmStreamResource:
        def _render() -> bytes:
            synthesizer = BeatSequenceSynthesizer(
                bpm=float(params["bpm"]),
                beats=beats,
                sample_rate=int(params["sample_rate"]),
                channels=int(params["channels"]),
                seed=params.get("seed"),
            )
            mix = synthesizer.render(
                tracks=tracks,
                sidechain=params.get("sidechain"),
                master=params["master"],
            )
            pcm_bytes, _ = encode_waveform_to_pcm(mix, format="s16le")
            return pcm_bytes

        pcm_bytes = await self._run_in_executor(_render)

        return PcmStreamResource(pcm_bytes, attrs={
            "sample_rate": int(params["sample_rate"]),
            "channels":    int(params["channels"]),
            "bit_depth":   16,
            "format":      "s16le",
        })

@register_music_synthesizer_driver(MusicSynthesizerDriverType.NATIVE)
class NativeMusicSynthesizerService(MusicSynthesizerDriver):
    def __init__(self, id: str, config: MusicSynthesizerComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [ "numpy", "scipy" ]

    async def _run(self, action: MusicSynthesizerActionConfig, context: ComponentActionContext) -> Any:
        return await NativeMusicSynthesizerAction(action).run(context)
