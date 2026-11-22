"""SMTH OS startup: the logo fade, and nothing else.

The startup overlay exists for exactly one gesture: the SMTH logo fades in,
holds, and fades out.  There is no cursor choreography, no desktop
reconstruction and no intermediate scene.  When the logo is gone the overlay
closes and the live session is already there.

This module is deliberately free of GTK and cairo so the timing can be tested
on any machine.  `startup.py` draws the same model with GTK4/cairo.
"""
from dataclasses import dataclass

# ---- timeline ---------------------------------------------------------------
LOGO_IN_MS = 620               # logo is fully opaque here
LOGO_HOLD_MS = 980             # it starts fading out here
LOGO_OUT_MS = 1560             # it has completely faded out here
DURATION_MS = LOGO_OUT_MS
REDUCED_MS = 640

# ---- inks -------------------------------------------------------------------
BLACK = (0.0, 0.0, 0.0)
WHITE = (1.0, 1.0, 1.0)


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def ease(value):
    """Smooth, slightly decelerating ease used by the fade in."""
    value = clamp(value)
    return 1.0 - (1.0 - value) ** 3


@dataclass(frozen=True)
class Frame:
    t_ms: float
    phase: str
    logo_alpha: float
    logo_reveal: float
    logo_scale: float
    overlay_alpha: float
    done: bool
    reduced: bool


class StartupScene:
    """Resolution-independent logo fade.  Create one per display size."""

    def __init__(self, width, height, reduced=False):
        self.width = max(640.0, float(width))
        self.height = max(480.0, float(height))
        self.reduced = bool(reduced)
        self.portrait = self.height >= self.width * 0.95

    def phase(self, t_ms):
        if self.reduced:
            return "logo" if t_ms < REDUCED_MS else "done"
        if t_ms < LOGO_IN_MS:
            return "logo-in"
        if t_ms < LOGO_HOLD_MS:
            return "logo-hold"
        if t_ms < LOGO_OUT_MS:
            return "logo-out"
        return "done"

    def logo_state(self, t_ms):
        """(alpha, reveal, scale) for the wordmark at this moment."""
        if self.reduced:
            if t_ms < 300:
                alpha = ease(t_ms / 300.0)
                reveal = clamp(t_ms / 340.0)
            elif t_ms < 400:
                alpha, reveal = 1.0, 1.0
            else:
                alpha = 1.0 - ease((t_ms - 400) / (REDUCED_MS - 400.0))
                reveal = 1.0
            return alpha, reveal, 0.94 + 0.06 * ease(reveal)

        if t_ms < LOGO_IN_MS:
            alpha = ease(t_ms / LOGO_IN_MS)
            reveal = clamp(t_ms / (LOGO_IN_MS + 60.0))
        elif t_ms < LOGO_HOLD_MS:
            alpha, reveal = 1.0, 1.0
        else:
            alpha = 1.0 - ease((t_ms - LOGO_HOLD_MS) / (LOGO_OUT_MS - LOGO_HOLD_MS))
            reveal = 1.0
        return alpha, reveal, 0.94 + 0.06 * ease(reveal)

    def frame(self, t_ms):
        duration = REDUCED_MS if self.reduced else DURATION_MS
        t_ms = clamp(t_ms, 0, duration)
        alpha, reveal, scale = self.logo_state(t_ms)
        return Frame(
            t_ms=t_ms,
            phase=self.phase(t_ms),
            logo_alpha=alpha,
            logo_reveal=reveal,
            logo_scale=scale,
            overlay_alpha=1.0,
            done=t_ms >= duration,
            reduced=self.reduced,
        )
