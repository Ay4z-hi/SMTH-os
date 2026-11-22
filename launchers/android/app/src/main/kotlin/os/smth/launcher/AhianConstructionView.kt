package os.smth.launcher

import android.animation.Animator
import android.animation.AnimatorListenerAdapter
import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RadialGradient
import android.graphics.RectF
import android.graphics.Shader
import android.graphics.Typeface
import android.provider.Settings
import android.view.MotionEvent
import android.view.View
import android.view.animation.LinearInterpolator
import java.util.Random
import kotlin.math.PI
import kotlin.math.ceil
import kotlin.math.cos
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin
import kotlin.math.sqrt

/**
 * The AHIAN takeover: three acts, 25.8 seconds, the same sequence and timing as
 * the ISO and the Windows launcher (`ahian_startup_model.py`).
 *
 * ```
 * act 1  0 - 10 s   the SMTH desktop is buried under custom error windows
 * act 2  10 - 19 s  a full-screen AH1AN system screen counts down from nine
 * act 3  19 - 25.8 s the screen collapses to a line, the line opens into the
 *                    flowing cold-glass wallpaper, the dot-matrix SMTH mark
 *                    assembles, then the icons, taskbar and widgets arrive
 * ```
 *
 * The final frame sits exactly on the live AHIAN desktop, which is already
 * drawn underneath, so the fade uncovers the real launcher. A tap skips. With
 * Reduce Motion enabled the whole thing collapses to a short fade of the
 * finished desktop.
 */
class AhianConstructionView(context: Context) : View(context) {

    private companion object {
        const val DURATION_MS = 19000L
        const val REDUCED_MS = 700L

        const val BLUE_START = 10000f
        const val BLUE_END = 19000f
        const val BLUE_OPEN_START = 10220f
        const val BLUE_OPEN_MS = 380f
        const val CARD_ENTER = 360f
        const val CARD_FLASH = 300f
        const val COUNTDOWN_FROM = 9

        val MAROON = 0xFF701B35.toInt()
        val MAROON_DEEP = 0xFF1E0A0F.toInt()
        val BLUSH = 0xFFF2C6D2.toInt()
        val OBSIDIAN = 0xFF09090B.toInt()
        val OBSIDIAN_DEEP = 0xFF06050A.toInt()
        val PURPLE = 0xFF4FB0E0.toInt()          // cold blue (was purple)
        val TEAL = 0xFFF0A85A.toInt()            // amber (was teal)
        val TEAL_BRIGHT = 0xFFF0A85A.toInt()     // amber (was teal bright)
        val PURPLE_SOFT = 0xFF4FB0E0.toInt()     // cold blue (was purple soft)
        val VIOLET = 0xFF141822.toInt()         // glass panel (was violet)
        val INK = 0xFFE7ECF5.toInt()            // frost (was ink)
        val PANEL = 0xFF141822.toInt()          // glass panel (was panel)
        val WALL_PURPLE = 0xFF07080B.toInt()     // glass void (was wall purple)
        val WALL_TEAL = 0xFF141822.toInt()       // glass panel (was wall teal)
        val BLUE_TOP = 0xFF0B1C42.toInt()
        val BLUE_BOTTOM = 0xFF14428F.toInt()
        val BLUE_INK = 0xFFF2F7FF.toInt()
        val BLUE_DIM = 0xFFA5C4F2.toInt()
        val BLUE_RULE = 0xFF32518A.toInt()
        val CRIMSON = 0xFF9E3357.toInt()
        val GLASS_VOID = 0xFF07080B.toInt()
        val GLASS_VOID_DEEP = 0xFF040507.toInt()
        val GLASS_PANEL = 0xFF0E1016.toInt()
        val GLASS_PANEL_RAISED = 0xFF141822.toInt()
        val FROST = 0xFFE7ECF5.toInt()
        val MUTED_INK = 0xFF9DA6B2.toInt()
        val GHOST_INK = 0xFF6E7686.toInt()
        val AMBER = 0xFFF0A85A.toInt()
        val AMBER_HOT = 0xFFFFC67A.toInt()
        val SIGNAL_RED = 0xFFE05A5A.toInt()
        val BLUE_COLD = 0xFF4FB0E0.toInt()
        val CHROME = 0xFF9AA6BF.toInt()
        val BLUE_GLOW = 0xFF77BCDF.toInt()

        val ACCENTS = intArrayOf(MAROON, BLUSH, PURPLE, TEAL, PURPLE_SOFT, CRIMSON)
        val CARD_HEADERS = arrayOf(
            "SMTH SYSTEM", "SURFACE", "AHIAN WATCH", "COMPOSITOR", "SESSION", "INDEX",
        )
        val BRAND_GLYPHS = mapOf(
            'S' to intArrayOf(15, 16, 16, 14, 1, 1, 30),
            'M' to intArrayOf(17, 27, 21, 21, 17, 17, 17),
            'T' to intArrayOf(31, 4, 4, 4, 4, 4, 4),
            'H' to intArrayOf(17, 17, 17, 31, 17, 17, 17),
            'A' to intArrayOf(14, 17, 17, 31, 17, 17, 17),
            'I' to intArrayOf(14, 4, 4, 4, 4, 4, 14),
            'N' to intArrayOf(17, 25, 21, 19, 17, 17, 17),
        )
        val DIGIT_GLYPHS = mapOf(
            '0' to intArrayOf(14, 17, 19, 21, 25, 17, 14),
            '1' to intArrayOf(4, 12, 4, 4, 4, 4, 14),
            '2' to intArrayOf(14, 17, 1, 2, 4, 8, 31),
            '3' to intArrayOf(30, 1, 1, 14, 1, 1, 30),
            '4' to intArrayOf(2, 6, 10, 18, 31, 2, 2),
            '5' to intArrayOf(31, 16, 30, 1, 1, 17, 14),
            '6' to intArrayOf(6, 8, 16, 30, 17, 17, 14),
            '7' to intArrayOf(31, 1, 2, 4, 8, 8, 8),
            '8' to intArrayOf(14, 17, 17, 14, 17, 17, 14),
            '9' to intArrayOf(14, 17, 17, 15, 1, 2, 12),
            ':' to intArrayOf(0, 4, 4, 0, 4, 4, 0),
        )
        val ERRORS = arrayOf(
        Err("SYSTEM FAILURE", "display pipeline stopped responding", "0x00A1", 0.235f, 0.245f, 0.245f, 0.19f, 0, 700f),
        Err("DESKTOP CORRUPTED", "surface buffer 3 returned an invalid state", "0x00B4", 0.715f, 0.168f, 0.23f, 0.155f, 1, 1180f),
        Err("REALITY NOT FOUND", "the compositor could not resolve a scene", "0x00C9", 0.435f, 0.47f, 0.265f, 0.185f, 2, 1620f),
        Err("SIGNAL LOST", "input device 0 is no longer present", "0x00D2", 0.845f, 0.35f, 0.205f, 0.15f, 0, 2010f),
        Err("MEMORY MISALIGNED", "block 0x7F3A exceeds its bounds", "0x00E0", 0.165f, 0.63f, 0.25f, 0.175f, 3, 2360f),
        Err("WRITE PROTECTED", "cannot persist session state", "0x00E8", 0.56f, 0.665f, 0.215f, 0.15f, 1, 2670f),
        Err("RECURSION LIMIT", "the desktop rebuilt itself faster than it renders", "0x00F1", 0.855f, 0.705f, 0.235f, 0.165f, 0, 2950f),
        Err("TRUST BOUNDARY", "unrecognised aesthetic signature", "0x00F7", 0.12f, 0.415f, 0.21f, 0.15f, 4, 3200f),
        Err("DISPLAY DRIVER HALTED", "falling back to software compositing", "0x0104", 0.468f, 0.218f, 0.24f, 0.16f, 0, 3420f),
        Err("AHIAN INITIALIZATION", "waiting for the user to look away", "0xA11A", 0.74f, 0.5f, 0.25f, 0.205f, 2, 3620f),
        Err("SESSION STATE LOST", "session 3 has no resting state", "0x0112", 0.305f, 0.315f, 0.2f, 0.15f, 1, 3800f),
        Err("UNKNOWN PROCESS", "pid 1 is drawing outside the frame", "0x0118", 0.625f, 0.72f, 0.215f, 0.15f, 3, 3960f),
        Err("PANEL UNRESPONSIVE", "the bar stopped greeting you", "0x011E", 0.08f, 0.79f, 0.23f, 0.15f, 0, 4110f),
        Err("FACTORY COLOURS", "maroon rejected by the incoming palette", "0x0125", 0.895f, 0.15f, 0.215f, 0.15f, 2, 4250f),
        Err("CLOCK OUT OF SYNC", "one second is missing", "0x012B", 0.395f, 0.815f, 0.2f, 0.145f, 4, 6050f),
        Err("INDEX REBUILD", "every icon is being re-sorted", "0x0133", 0.68f, 0.3f, 0.19f, 0.145f, 1, 6280f),
        Err("DESKTOP CORRUPTED", "the second pass could not repair the first", "0x0139", 0.195f, 0.155f, 0.22f, 0.15f, 5, 6500f),
        Err("REALITY NOT FOUND", "retrying with a nicer one", "0x0140", 0.52f, 0.555f, 0.2f, 0.145f, 2, 6700f),
        Err("AHIAN INITIALIZATION", "aesthetics 84% loaded", "0xA11A", 0.82f, 0.59f, 0.21f, 0.185f, 3, 6880f),
        Err("SYSTEM FAILURE", "this is not an error any more", "0x014A", 0.3f, 0.505f, 0.185f, 0.14f, 0, 7040f),
        Err("REALITY NOT FOUND", "searching a warmer universe", "0x0152", 0.7f, 0.83f, 0.195f, 0.145f, 2, 7190f),
        Err("AHIAN INITIALIZATION", "do not look away", "0xA11A", 0.455f, 0.365f, 0.225f, 0.185f, 2, 7330f),
        )
    }

    private data class Err(
        val title: String,
        val body: String,
        val code: String,
        val cx: Float,
        val cy: Float,
        val wf: Float,
        val hf: Float,
        val accent: Int,
        val start: Float,
    )

    private val fill = Paint(Paint.ANTI_ALIAS_FLAG)
    private val stroke = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
    }
    private val textPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        typeface = Typeface.MONOSPACE
        textAlign = Paint.Align.LEFT
    }

    private var elapsed = 0f
    private var animator: ValueAnimator? = null
    private var reduced = false
    private var blueOpened = false

    /**
     * Fires once, when the blue screen is fully opaque. The caller switches the
     * real desktop in here, so the new wallpaper is never visible through the
     * opening beam.
     */
    var onBlueOpen: (() -> Unit)? = null
    private val rng = Random(1107)

    private var w = 0f
    private var h = 0f
    private var u = 1f

    init {
        // Absolutely no background: the live launcher desktop is the backdrop.
        setBackgroundColor(android.graphics.Color.TRANSPARENT)
        contentDescription = "AHIAN takeover; tap to skip"
        isClickable = true
    }

    // ---- lifecycle -----------------------------------------------------------
    private fun reducedMotion(): Boolean = try {
        Settings.Global.getFloat(
            context.contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f,
        ) == 0f
    } catch (e: Exception) {
        false
    }

    fun start(onComplete: (() -> Unit)? = null) {
        animator?.cancel()
        blueOpened = false
        reduced = reducedMotion()
        val duration = if (reduced) REDUCED_MS else DURATION_MS
        val anim = ValueAnimator.ofFloat(0f, duration.toFloat()).apply {
            this.duration = duration
            interpolator = LinearInterpolator()
            addUpdateListener { value ->
                elapsed = value.animatedValue as Float
                if (!blueOpened && elapsed >= BLUE_OPEN_START + BLUE_OPEN_MS) {
                    blueOpened = true
                    onBlueOpen?.invoke()
                }
                alpha = overlayAlpha(elapsed)
                invalidate()
            }
            addListener(object : AnimatorListenerAdapter() {
                override fun onAnimationEnd(animation: Animator) {
                    onComplete?.invoke()
                }
            })
        }
        animator = anim
        alpha = 1f
        anim.start()
    }

    fun stop() {
        animator?.cancel()
        animator = null
    }

    override fun onDetachedFromWindow() {
        animator?.cancel()
        super.onDetachedFromWindow()
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        if (event.action == MotionEvent.ACTION_DOWN) {
            if (animator?.isRunning == true) animator?.end()
            return true
        }
        return super.onTouchEvent(event)
    }

    private fun overlayAlpha(t: Float): Float = if (reduced) {
        (1f - t / REDUCED_MS).coerceIn(0f, 1f)
    } else {
        // The overlay is removed at zero; it never fades a rendered desktop.
        1f
    }

    // ---- helpers -------------------------------------------------------------
    private fun ease(v: Float): Float {
        val x = v.coerceIn(0f, 1f)
        return 1f - (1f - x) * (1f - x) * (1f - x)
    }

    private fun easeInOut(v: Float): Float {
        val x = v.coerceIn(0f, 1f)
        return x * x * (3f - 2f * x)
    }

    private fun mix(a: Int, b: Int, t: Float): Int {
        val k = t.coerceIn(0f, 1f)
        return Color.rgb(
            (Color.red(a) + (Color.red(b) - Color.red(a)) * k).toInt(),
            (Color.green(a) + (Color.green(b) - Color.green(a)) * k).toInt(),
            (Color.blue(a) + (Color.blue(b) - Color.blue(a)) * k).toInt(),
        )
    }

    private fun withAlpha(colour: Int, a: Float): Int =
        (colour and 0x00FFFFFF) or
            ((a.coerceIn(0f, 1f) * 255f).toInt().coerceIn(0, 255) shl 24)

    private fun textWidth(s: String, size: Float, tracking: Float): Float {
        if (s.isEmpty()) return 0f
        textPaint.textSize = size
        var total = 0f
        for (ch in s) total += textPaint.measureText(ch.toString())
        return total + tracking * (s.length - 1)
    }

    private fun text(
        canvas: Canvas,
        s: String,
        x: Float,
        baseline: Float,
        size: Float,
        colour: Int,
        tracking: Float = 0f,
        bold: Boolean = false,
        align: Int = 0, // 0 left, 1 centre, 2 right
    ) {
        textPaint.textSize = size
        textPaint.color = colour
        textPaint.isFakeBoldText = bold
        var cursor = x
        if (align != 0) {
            val width = textWidth(s, size, tracking)
            cursor = if (align == 1) x - width / 2f else x - width
        }
        for (ch in s) {
            canvas.drawText(ch.toString(), cursor, baseline, textPaint)
            cursor += textPaint.measureText(ch.toString()) + tracking
        }
        textPaint.isFakeBoldText = false
    }

    private fun wrap(s: String, size: Float, tracking: Float, maxWidth: Float): List<String> {
        val words = s.split(" ")
        val lines = ArrayList<String>()
        var current = ""
        for (word in words) {
            val candidate = if (current.isEmpty()) word else "$current $word"
            if (current.isNotEmpty() && textWidth(candidate, size, tracking) > maxWidth) {
                lines.add(current)
                current = word
            } else {
                current = candidate
            }
        }
        if (current.isNotEmpty()) lines.add(current)
        return lines
    }

    private fun dotMatrix(
        canvas: Canvas,
        s: String,
        x: Float,
        baseline: Float,
        dot: Float,
        colour: Int,
        glyphs: Map<Char, IntArray> = BRAND_GLYPHS,
    ) {
        fill.color = colour
        for (index in s.indices) {
            val rows = glyphs[s[index]] ?: continue
            for (row in 0 until 7) {
                for (col in 0 until 5) {
                    if ((rows[row] shr (4 - col)) and 1 != 1) continue
                    val cx = x + (index * 6 + col) * dot
                    val cy = baseline - (6 - row) * dot - dot * 0.5f
                    canvas.drawCircle(cx, cy, dot * 0.38f, fill)
                }
            }
        }
    }

    private fun rounded(canvas: Canvas, rect: RectF, radius: Float, colour: Int) {
        fill.color = colour
        canvas.drawRoundRect(rect, radius, radius, fill)
    }

    private fun line(canvas: Canvas, x0: Float, y0: Float, x1: Float, y1: Float,
                     colour: Int, width: Float) {
        stroke.color = colour
        stroke.strokeWidth = width
        canvas.drawLine(x0, y0, x1, y1, stroke)
    }

    private fun cardAccent(e: Err): Int = when (e.accent % 6) {
        0, 2 -> AMBER_HOT
        1, 4 -> BLUE_COLD
        else -> SIGNAL_RED
    }

    private fun roundedPath(rect: RectF, radius: Float): Path = Path().apply {
        addRoundRect(rect, radius, radius, Path.Direction.CW)
    }

    private fun cardRect(e: Err): RectF {
        // Content-sized windows: title bar, title, two body lines, footer.
        val width = max(e.wf * w, 292f * u)
        val height = (100f + 6f * (e.accent % 3) +
            if (e.code == "0xA11A") 10f else 0f) * u
        val cx = e.cx * w
        val cy = e.cy * h
        return RectF(cx - width / 2f, cy - height / 2f,
            cx + width / 2f, cy + height / 2f)
    }

    private fun drawCards(canvas: Canvas, t: Float) {
        for (e in ERRORS) {
            if (t < e.start) continue
            val progress = ease(((t - e.start) / CARD_ENTER).coerceIn(0f, 1f))
            val flash = (1f - (t - e.start) / CARD_FLASH).coerceIn(0f, 1f)
            val base = cardRect(e)
            val scale = 1f + 0.035f * (1f - progress)
            val drift = (1f - progress) * 9f * u
            val cx = base.centerX()
            val cy = base.centerY() + drift
            val halfW = base.width() / 2f * scale
            val halfH = base.height() / 2f * scale
            val rect = RectF(cx - halfW, cy - halfH, cx + halfW, cy + halfH)
            val accent = cardAccent(e)
            val ahian = e.code == "0xA11A"
            val readout = !ahian && e.accent % 2 == 1
            val a = progress

            // Soft shadow: the window floats above the buried desktop.
            val shadowRect = RectF(rect.left + 2f * u, rect.top + 7f * u,
                rect.right + 2f * u, rect.bottom + 7f * u)
            fill.color = withAlpha(Color.BLACK, 0.45f * a)
            canvas.drawRoundRect(shadowRect, 10f * u, 10f * u, fill)

            canvas.save()
            canvas.clipPath(roundedPath(rect, 10f * u))
            fill.shader = LinearGradient(rect.left, rect.top, rect.left, rect.bottom,
                if (ahian) 0xFF1C1710.toInt() else 0xFF171A23.toInt(),
                if (ahian) 0xFF0A0906.toInt() else 0xFF08090D.toInt(),
                Shader.TileMode.CLAMP)
            canvas.drawRect(rect, fill)
            fill.shader = null
            // The one saturated surface: a status rail down the left edge.
            fill.color = withAlpha(accent, a)
            canvas.drawRect(rect.left, rect.top, rect.left + 2.6f * u, rect.bottom, fill)

            val pad = 15f * u
            val left = rect.left + pad
            val right = rect.right - 13f * u
            var titleY: Float
            var bodyY: Float
            if (readout) {
                text(canvas, "DIAGNOSTIC READOUT", left, rect.top + 14f * u, 7f * u,
                    withAlpha(mix(accent, FROST, 0.25f), 0.9f * a), 1.4f * u)
                text(canvas, e.code, right, rect.top + 14f * u, 8f * u,
                    withAlpha(accent, 0.95f * a), 0.6f * u, bold = true, align = 2)
                line(canvas, left, rect.top + 20f * u, right, rect.top + 20f * u,
                    withAlpha(FROST, 0.10f * a), 1f)
                titleY = rect.top + 38f * u
                bodyY = rect.top + 54f * u
            } else {
                val barH = 24f * u
                fill.color = withAlpha(
                    if (ahian) 0xFF231D14.toInt() else 0xFF1A1D27.toInt(), a)
                canvas.drawRect(rect.left, rect.top, rect.right, rect.top + barH, fill)
                line(canvas, rect.left, rect.top + barH, rect.right, rect.top + barH,
                    withAlpha(Color.BLACK, 0.5f * a), 1f)
                val g = 3.2f * u
                val gx = left + g
                val gy = rect.top + barH / 2f
                val lozenge = Path().apply {
                    moveTo(gx, gy - g)
                    lineTo(gx + g, gy)
                    lineTo(gx, gy + g)
                    lineTo(gx - g, gy)
                    close()
                }
                fill.color = withAlpha(accent, 0.96f * a)
                canvas.drawPath(lozenge, fill)
                val name = if (ahian) "AH1AN" else "SMTH OS"
                text(canvas, name, left + 11f * u, gy + 2.5f * u, 7f * u,
                    withAlpha(FROST, 0.95f * a), 1.2f * u, bold = true)
                text(canvas, "SYSTEM",
                    left + 11f * u + textWidth(name, 7f * u, 1.2f * u) + 9f * u,
                    gy + 2.5f * u, 7f * u, withAlpha(GHOST_INK, 0.86f * a), 1.2f * u)
                if (ahian) {
                    text(canvas, "0xA11A", right, gy + 2.5f * u, 8f * u,
                        withAlpha(accent, 0.95f * a), 0.8f * u, bold = true, align = 2)
                } else {
                    line(canvas, right - 38f * u, gy, right - 32f * u, gy,
                        withAlpha(CHROME, 0.75f * a), 1f)
                    stroke.color = withAlpha(CHROME, 0.75f * a)
                    stroke.strokeWidth = 1f
                    canvas.drawRect(right - 23f * u, gy - 2.4f * u,
                        right - 18f * u, gy + 2.4f * u, stroke)
                    line(canvas, right - 10f * u, gy - 2.6f * u,
                        right - 5f * u, gy + 2.6f * u, withAlpha(CHROME, 0.86f * a), 1f)
                    line(canvas, right - 10f * u, gy + 2.6f * u,
                        right - 5f * u, gy - 2.6f * u, withAlpha(CHROME, 0.86f * a), 1f)
                }
                titleY = rect.top + barH + 23f * u
                bodyY = rect.top + barH + 39f * u + if (ahian) 2f * u else 0f
            }

            var size = 13.2f * u
            while (size > 9f * u && textWidth(e.title, size, 0.5f * u) > right - left) {
                size -= 0.4f * u
            }
            text(canvas, e.title, left, titleY, size, withAlpha(FROST, a),
                0.5f * u, bold = true)
            var used = 0
            for (row in wrap(e.body, 9.5f * u, 0f, right - left - 2f * u)) {
                if (used == 2) break
                text(canvas, row, left, bodyY, 9.5f * u,
                    withAlpha(MUTED_INK, 0.96f * a), 0.15f * u)
                bodyY += 13.6f * u
                used++
            }
            val footerY = rect.bottom - 11f * u
            if (ahian) {
                val trackY = footerY - 15f * u
                line(canvas, left, trackY, right, trackY,
                    withAlpha(FROST, 0.10f * a), 1.5f * u)
                line(canvas, left, trackY, left + (right - left) * 0.62f, trackY,
                    withAlpha(accent, 0.95f * a), 1.8f * u)
            }
            line(canvas, left, footerY - 8f * u, right, footerY - 8f * u,
                withAlpha(FROST, 0.09f * a), 1f)
            val state = when {
                ahian -> "AESTHETIC SUBSYSTEM"
                e.accent % 2 == 1 -> "RETRYING"
                else -> "NO RESPONSE"
            }
            text(canvas, state, left, footerY, 7f * u,
                withAlpha(GHOST_INK, 0.95f * a), 1.2f * u)
            text(canvas, e.code, right, footerY, 8f * u,
                withAlpha(accent, 0.95f * a), 0.7f * u, bold = true, align = 2)
            canvas.restore()

            stroke.color = withAlpha(FROST, 0.16f * a)
            stroke.strokeWidth = 1f
            canvas.drawRoundRect(rect, 10f * u, 10f * u, stroke)
            if (flash > 0.02f) {
                stroke.color = withAlpha(accent, 0.7f * flash)
                stroke.strokeWidth = max(1f, 1.4f * u)
                canvas.drawRoundRect(rect, 10f * u, 10f * u, stroke)
            }
        }
    }

    private fun drawGlitch(canvas: Canvas, t: Float) {
        // Translucent interference only: it tints the overlay, never the live
        // desktop underneath. The tremor itself moves the windows in onDraw.
        var flash = 0f
        var split = 0f
        var slice = -1f
        var sliceShift = 0f
        var scan = -1f
        val events = arrayOf(
            floatArrayOf(1350f, 70f, 0f, 0.16f), floatArrayOf(2180f, 110f, 1f, 2.5f),
            floatArrayOf(2960f, 90f, 2f, 14f), floatArrayOf(3520f, 60f, 0f, 0.22f),
            floatArrayOf(4460f, 100f, 1f, 4f), floatArrayOf(4980f, 80f, 2f, 26f),
            floatArrayOf(5320f, 90f, 0f, 0.30f), floatArrayOf(5980f, 110f, 1f, 7f),
            floatArrayOf(6300f, 70f, 3f, 0.9f), floatArrayOf(6620f, 140f, 2f, 38f),
            floatArrayOf(6900f, 90f, 0f, 0.42f), floatArrayOf(7460f, 120f, 1f, 10f),
            floatArrayOf(7720f, 90f, 2f, 52f), floatArrayOf(7960f, 70f, 0f, 0.55f),
            floatArrayOf(8180f, 140f, 3f, 1f), floatArrayOf(8680f, 120f, 1f, 13f),
            floatArrayOf(8930f, 100f, 2f, 66f), floatArrayOf(9180f, 90f, 0f, 0.62f),
            floatArrayOf(9660f, 110f, 1f, 16f),
        )
        for (event in events) {
            val start = event[0]
            val duration = event[1]
            if (t < start || t >= start + duration) continue
            val local = (t - start) / duration
            val env = sin(local * PI).toFloat()
            when (event[2].toInt()) {
                0 -> flash = max(flash, event[3] * env)
                1 -> split = max(split, event[3] * env)
                2 -> {
                    slice = ((t * 0.37f) % 0.72f) + 0.14f
                    sliceShift = event[3] * env * if ((t.toInt() % 2) == 0) 1f else -1f
                }
                3 -> scan = local
            }
        }
        if (flash > 0.01f) {
            fill.color = withAlpha(0xFFE2F0FF.toInt(), flash * 0.7f)
            canvas.drawRect(0f, 0f, w, h, fill)
        }
        if (split > 0.5f) {
            // Chromatic separation on a band, like a signal losing sync.
            val y0 = h * 0.32f
            val y1 = h * 0.62f
            fill.color = withAlpha(Color.RED, 0.10f)
            canvas.drawRect(split, y0, w + split, y1, fill)
            fill.color = withAlpha(Color.CYAN, 0.10f)
            canvas.drawRect(-split, y0, w - split, y1, fill)
        }
        if (slice >= 0f && sliceShift != 0f) {
            val y0 = h * (slice - 0.05f).coerceIn(0f, 1f)
            val y1 = h * (slice + 0.05f).coerceIn(0f, 1f)
            canvas.save()
            canvas.clipRect(0f, y0, w, y1)
            fill.color = withAlpha(0xFFB4CCE8.toInt(), 0.07f)
            canvas.drawRect(sliceShift, y0, w + sliceShift, y1, fill)
            canvas.restore()
        }
        if (scan >= 0f) {
            fill.color = withAlpha(0xFFB4E1FF.toInt(), 0.10f)
            canvas.drawRect(0f, scan * h - 26f * u, w, scan * h + 26f * u, fill)
        }
        // Fine grain: sparse single pixels, never a heavy overlay.
        val grain = if (t < BLUE_START) 0.10f + 0.35f * ease((t / 9000f)
            .coerceIn(0f, 1f)) else 0.10f
        fill.color = withAlpha(Color.WHITE, 0.10f * grain)
        for (i in 0 until 220) {
            val gx = rng.nextFloat() * w
            val gy = rng.nextFloat() * h
            canvas.drawRect(gx, gy, gx + 1.5f * u, gy + 1.5f * u, fill)
        }
    }

    // ---- act 2: the AH1AN system screen --------------------------------------
    private fun countdown(t: Float): Int =
        ceil((BLUE_END - max(t, BLUE_START)) / 1000f).toInt().coerceIn(0, COUNTDOWN_FROM)

    private fun drawBlue(canvas: Canvas, t: Float) {
        fill.shader = LinearGradient(0f, 0f, 0f, h, BLUE_TOP, BLUE_BOTTOM,
            Shader.TileMode.CLAMP)
        canvas.drawRect(0f, 0f, w, h, fill)
        fill.shader = null
        fill.color = withAlpha(0xFF4F7AD0.toInt(), 0.16f)
        canvas.drawCircle(w * 0.14f, -h * 0.05f, max(w, h) * 0.55f, fill)
        fill.color = withAlpha(0xFF2B4C86.toInt(), 0.22f)
        canvas.drawCircle(w * 0.92f, h * 1.02f, max(w, h) * 0.48f, fill)

        // Dot field and two very faint orbits: depth without a panel.
        val fieldStep = 28f * u
        val fieldDot = max(0.6f, 0.7f * u)
        fill.color = withAlpha(BLUE_GLOW, 0.06f)
        var fy = fieldStep
        while (fy < h) {
            var fx = fieldStep
            while (fx < w) {
                canvas.drawCircle(fx, fy, fieldDot, fill)
                fx += fieldStep
            }
            fy += fieldStep
        }
        stroke.color = withAlpha(BLUE_GLOW, 0.10f)
        stroke.strokeWidth = 1f
        canvas.drawCircle(w * 0.86f, h * 0.34f, h * 0.62f, stroke)
        stroke.color = withAlpha(BLUE_GLOW, 0.07f)
        canvas.drawCircle(w * 0.86f, h * 0.34f, h * 0.40f, stroke)

        val pad = max(34f * u, 0.072f * w)
        val left = pad
        val right = w - pad
        val top = h * 0.075f

        // ---- brand row
        dotMatrix(canvas, "SMTH", left, top, max(1.4f, 2f * u), BLUE_INK)
        text(canvas, "SMTH OS", left + 84f * u, top - 2f * u, 10.4f * u,
            BLUE_INK, 0.8f * u, bold = true)
        text(canvas, "KERNEL EVENT  ·  SESSION 03", left + 84f * u,
            top + 13f * u, 7.4f * u, withAlpha(BLUE_DIM, 0.78f), 1.3f * u)
        text(canvas, "AH1AN", right, top - 2f * u, 9f * u,
            withAlpha(BLUE_GLOW, 0.95f), 3f * u, bold = true, align = 2)
        text(canvas, "AESTHETIC SUBSYSTEM ONLINE", right, top + 13f * u,
            7.4f * u, withAlpha(BLUE_DIM, 0.66f), 1.1f * u, align = 2)

        // ---- headline: two deliberate lines, never a reflowed paragraph
        var size = min(0.092f * h, 0.072f * w)
        val words = "AHIAN HAS TAKEN CONTROL".split(" ")
        val lines = listOf(words.take(2).joinToString(" "),
            words.drop(2).joinToString(" "))
        while (size > 0.040f * h &&
            lines.any { textWidth(it, size, 0.4f * u) > right - left }
        ) {
            size *= 0.94f
        }
        val headY = h * 0.300f
        lines.forEachIndexed { index, row ->
            text(canvas, row, left, headY + index * size * 1.04f, size,
                BLUE_INK, 0.4f * u, bold = true)
        }
        val subSize = max(13f * u, size * 0.28f)
        val subY = headY + lines.size * size * 1.04f + subSize * 0.55f
        text(canvas, "AHIAN wants to make your life beautiful.", left, subY,
            subSize, withAlpha(BLUE_DIM, 0.94f), 0.15f * u)

        // ---- countdown: the hero, opposite the headline in landscape
        val progress = ((t - BLUE_START) / (BLUE_END - BLUE_START))
            .coerceIn(0f, 1f)
        val portrait = h >= w * 0.95f
        val ringCx: Float
        val ringCy: Float
        val radius: Float
        if (portrait) {
            ringCx = (left + right) / 2f
            ringCy = h * 0.610f
            radius = min(0.120f * h, 0.200f * (right - left))
        } else {
            ringCx = left + (right - left) * 0.70f
            ringCy = h * 0.610f
            radius = min(0.120f * h, 0.110f * (right - left))
        }
        stroke.color = withAlpha(BLUE_RULE, 0.92f)
        stroke.strokeWidth = max(2f, 1.6f * u)
        canvas.drawCircle(ringCx, ringCy, radius, stroke)
        val sweep = 360f * (1f - progress)
        if (sweep > 0.5f) {
            stroke.color = withAlpha(BLUE_GLOW, 0.98f)
            stroke.strokeWidth = max(2f, 3.2f * u)
            canvas.drawArc(RectF(ringCx - radius, ringCy - radius,
                ringCx + radius, ringCy + radius), 270f, sweep, false, stroke)
        }
        text(canvas, "COUNTDOWN", ringCx, ringCy - radius - 20f * u,
            7.6f * u, withAlpha(BLUE_GLOW, 0.9f), 3.2f * u, align = 1)
        val sinceTick = (BLUE_END - t) / 1000f
        val tick = (1f - (sinceTick - sinceTick.toInt()) / 0.28f)
            .coerceIn(0f, 1f)
        val numberSize = radius * 1.18f * (1f + 0.05f * tick)
        text(canvas, countdown(t).toString(), ringCx,
            ringCy + numberSize * 0.34f, numberSize, BLUE_INK, 0f,
            bold = true, align = 1)
        text(canvas, "AHIAN IS REBUILDING YOUR REALITY", ringCx,
            ringCy + radius + 26f * u, 7.6f * u,
            withAlpha(BLUE_DIM, 0.84f), 1.8f * u, align = 1)
        val barW = radius * 2.10f
        val barY = ringCy + radius + 38f * u
        rounded(canvas, RectF(ringCx - barW / 2f, barY,
            ringCx + barW / 2f, barY + 3f * u), 2f * u,
            withAlpha(0xFF294052.toInt(), 0.9f))
        if (progress > 0.01f) {
            rounded(canvas, RectF(ringCx - barW / 2f, barY,
                ringCx - barW / 2f + barW * progress, barY + 3f * u),
                2f * u, BLUE_GLOW)
        }
        text(canvas, "${(progress * 100).toInt()}%", ringCx + barW / 2f + 12f * u,
            barY + 3.2f * u, 7.8f * u, withAlpha(BLUE_DIM, 0.88f), 0.8f * u)

        // ---- footer: nine segments, then the stop code
        val ruleY = h * 0.845f
        line(canvas, left, ruleY, right, ruleY, withAlpha(BLUE_RULE, 0.8f), 1f)
        val gap = 6f * u
        val segW = (right - left - gap * 8f) / 9f
        for (i in 0 until 9) {
            val x = left + i * (segW + gap)
            val on = progress >= (i + 1) / 9f - 0.001f
            fill.color = if (on) BLUE_GLOW else withAlpha(BLUE_RULE, 0.65f)
            canvas.drawRect(x, ruleY + 8f * u, x + segW, ruleY + 11.4f * u, fill)
        }
        val metaY = ruleY + 33f * u
        text(canvas, "STOP CODE: AH1AN_ASCENSION", left, metaY, 7.4f * u,
            withAlpha(BLUE_DIM, 0.86f), 1.5f * u)
        text(canvas, "0x0000A11A  ·  MODE: AHIAN", left, metaY + 15f * u,
            7.4f * u, withAlpha(BLUE_DIM, 0.64f), 1.2f * u)
        val pulse = 0.55f + 0.45f * sin(t / 280f)
        fill.color = withAlpha(AMBER_HOT, 0.35f + 0.55f * pulse)
        canvas.drawCircle(right - 5f * u, metaY - 4f * u, 2.6f * u, fill)
        text(canvas, "DO NOT POWER OFF", right - 16f * u, metaY, 7.4f * u,
            withAlpha(BLUE_DIM, 0.82f), 1.5f * u, align = 2)
        text(canvas, "AHIAN / 9.0 SEC", right, metaY + 15f * u, 7.4f * u,
            withAlpha(BLUE_DIM, 0.58f), 1.2f * u, align = 2)
    }

    private fun drawBeam(canvas: Canvas) {
        val y = h / 2f
        val glow = max(1f, 8f * u)
        fill.color = withAlpha(0xFF96BEE1.toInt(), 0.16f)
        canvas.drawRect(0f, y - glow, w, y - 1f, fill)
        fill.color = withAlpha(0xFFC8E0F8.toInt(), 0.90f)
        canvas.drawRect(0f, y - 1f, w, y + 1f, fill)
        fill.color = withAlpha(0xFF96BEE1.toInt(), 0.16f)
        canvas.drawRect(0f, y + 1f, w, y + glow, fill)
    }

    override fun onDraw(canvas: Canvas) {
        w = width.toFloat()
        h = height.toFloat()
        if (w <= 0f || h <= 0f) return
        u = min(w / 1280f, h / 800f)
        if (h >= w * 0.95f) u = min(w / 900f, h / 1600f)
        u = u.coerceIn(0.72f, 2.6f)

        val t = elapsed.coerceIn(0f, if (reduced) REDUCED_MS.toFloat()
        else DURATION_MS.toFloat())
        // Nothing is painted behind act 1: the view is transparent, so the
        // real wallpaper, icons and taskbar remain exactly as they are.
        if (reduced) return

        if (t < BLUE_START) {
            val shake = 2.4f * u * ease(((t - 2600f) / 7200f).coerceIn(0f, 1f))
            canvas.save()
            if (shake > 0.05f) {
                canvas.translate(sin(t / 46f) * shake, cos(t / 61f) * shake * 0.55f)
            }
            drawCards(canvas, t)
            canvas.restore()
            drawGlitch(canvas, t)
            return
        }

        if (t < BLUE_END) {
            if (t < BLUE_OPEN_START) {
                drawBeam(canvas)
                return
            }
            val open = easeInOut(((t - BLUE_OPEN_START) / BLUE_OPEN_MS).coerceIn(0f, 1f))
            val bandH = max(2f, h * open)
            val top = (h - bandH) / 2f
            canvas.save()
            canvas.clipRect(0f, top, w, top + bandH)
            drawBlue(canvas, t)
            canvas.restore()
            val edge = max(1f, 1.6f * u)
            fill.color = withAlpha(0xFFCFF0FF.toInt(), 0.9f)
            canvas.drawRect(0f, top - edge, w, top, fill)
            canvas.drawRect(0f, top + bandH, w, top + bandH + edge, fill)
            drawGlitch(canvas, t)
            return
        }

        // Exactly zero: the countdown has stopped. Nothing is drawn; the view
        // is removed and the live AHIAN desktop underneath is revealed.
    }
}
