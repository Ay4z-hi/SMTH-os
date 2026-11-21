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
 *                    flowing purple-teal wallpaper, the dot-matrix SMTH mark
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
        const val DURATION_MS = 25800L
        const val REDUCED_MS = 700L

        const val BLUE_START = 10000f
        const val BLUE_END = 19000f
        const val COLLAPSE_MS = 220f
        const val BLUE_OPEN_START = 10220f
        const val BLUE_OPEN_MS = 380f
        const val BLUE_CLOSE_MS = 180f
        const val WALL_OPEN_START = 19180f
        const val WALL_OPEN_MS = 430f
        const val HOLE_START = 21200f
        const val BRAND_START = 19520f
        const val BRAND_MS = 980f
        const val BRAND_SETTLE = 20600f
        const val BRAND_SETTLED = 21600f
        const val PANEL_START = 20120f
        const val PANEL_MS = 620f
        const val ICON_START = 20460f
        const val ICON_STEP = 86f
        const val ICON_MS = 430f
        const val WIDGET_START = 21420f
        const val WIDGET_MS = 620f
        const val TOAST_START = 22260f
        const val TOAST_MS = 320f
        const val TOAST_END = 24280f
        const val FADE_START = 25000f
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

        val ACCENTS = intArrayOf(MAROON, BLUSH, PURPLE, TEAL, PURPLE_SOFT, CRIMSON)
        val CARD_HEADERS = arrayOf(
            "SMTH SYSTEM", "SURFACE", "AHIAN WATCH", "COMPOSITOR", "SESSION", "INDEX",
        )
        val ICON_LABELS = arrayOf(
            "TERMINAL", "CHROME", "PHONE", "MESSAGES", "CAMERA", "SETTINGS",
        )
        val ICON_GLYPHS = arrayOf("terminal", "globe", "phone", "chat", "camera", "gear")

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
    private val rng = Random(1107)

    private var w = 0f
    private var h = 0f
    private var u = 1f

    init {
        setBackgroundColor(OBSIDIAN_DEEP)
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
        reduced = reducedMotion()
        val duration = if (reduced) REDUCED_MS else DURATION_MS
        val anim = ValueAnimator.ofFloat(0f, duration.toFloat()).apply {
            this.duration = duration
            interpolator = LinearInterpolator()
            addUpdateListener { value ->
                elapsed = value.animatedValue as Float
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
    } else if (t < FADE_START) {
        1f
    } else {
        (1f - (t - FADE_START) / (DURATION_MS - FADE_START)).coerceIn(0f, 1f)
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

    private fun flow(uu: Float, vv: Float, phase: Float): Int {
        val x = uu.coerceIn(0f, 1f)
        val y = vv.coerceIn(0f, 1f)
        val tau = (2f * PI).toFloat()
        var wave = sin((x + y * 0.62f) * tau + phase * tau) * 0.075f
        wave += sin((x * 1.7f - y * 1.1f) * tau - phase * tau * 2f) * 0.035f
        val band = 0.5f + 0.5f * sin((x * 0.8f - y * 0.55f) * tau - phase * tau)
        var d = (x * 0.58f + y * 0.42f + wave).coerceIn(0f, 1f)
        d = d * d * (3f - 2f * d)
        val wall = mix(WALL_PURPLE, WALL_TEAL, d)
        val accent = mix(PURPLE_SOFT, TEAL_BRIGHT, (x * 0.7f + y * 0.3f).coerceIn(0f, 1f))
        return mix(wall, accent, 0.035f + 0.075f * band)
    }

    // ---- glyphs --------------------------------------------------------------
    private fun glyph(canvas: Canvas, name: String, cx: Float, cy: Float, size: Float,
                      colour: Int) {
        val s = size / 2f
        val width = max(1f, size * 0.09f)
        fun ln(x0: Float, y0: Float, x1: Float, y1: Float) =
            line(canvas, cx + x0 * s, cy + y0 * s, cx + x1 * s, cy + y1 * s, colour, width)

        fun box(x0: Float, y0: Float, x1: Float, y1: Float) {
            stroke.color = colour
            stroke.strokeWidth = width
            canvas.drawRect(cx + x0 * s, cy + y0 * s, cx + x1 * s, cy + y1 * s, stroke)
        }

        when (name) {
            "folder" -> {
                val path = Path()
                path.moveTo(cx - s * 0.82f, cy - s * 0.40f)
                path.lineTo(cx - s * 0.22f, cy - s * 0.40f)
                path.lineTo(cx - s * 0.08f, cy - s * 0.62f)
                path.lineTo(cx + s * 0.82f, cy - s * 0.62f)
                stroke.color = colour
                stroke.strokeWidth = width
                canvas.drawPath(path, stroke)
                box(-0.82f, -0.38f, 0.82f, 0.62f)
            }
            "globe" -> {
                stroke.color = colour
                stroke.strokeWidth = width
                canvas.drawCircle(cx, cy, s * 0.72f, stroke)
                ln(0f, -0.72f, 0f, 0.72f)
                val oval = RectF(cx - s * 0.72f, cy - s * 0.42f, cx + s * 0.72f,
                    cy + s * 0.42f)
                canvas.drawOval(oval, stroke)
            }
            "terminal" -> {
                box(-0.82f, -0.62f, 0.82f, 0.62f)
                ln(-0.5f, -0.28f, -0.16f, 0f)
                ln(-0.16f, 0f, -0.5f, 0.28f)
                ln(0.1f, 0.3f, 0.52f, 0.3f)
            }
            "gear" -> {
                stroke.color = colour
                stroke.strokeWidth = width
                canvas.drawCircle(cx, cy, s * 0.32f, stroke)
                val dirs = arrayOf(
                    0f to -1f, 0f to 1f, -1f to 0f, 1f to 0f,
                    -0.72f to -0.72f, 0.72f to 0.72f, -0.72f to 0.72f, 0.72f to -0.72f,
                )
                for ((dx, dy) in dirs) ln(dx * 0.44f, dy * 0.44f, dx * 0.72f, dy * 0.72f)
            }
            "camera" -> {
                box(-0.82f, -0.44f, 0.82f, 0.54f)
                box(-0.24f, -0.62f, 0.24f, -0.44f)
                stroke.color = colour
                stroke.strokeWidth = width
                canvas.drawCircle(cx, cy + s * 0.06f, s * 0.28f, stroke)
            }
            "phone" -> {
                stroke.color = colour
                stroke.strokeWidth = width
                canvas.drawRoundRect(
                    RectF(cx - s * 0.42f, cy - s * 0.78f, cx + s * 0.42f, cy + s * 0.78f),
                    s * 0.16f, s * 0.16f, stroke,
                )
                ln(-0.16f, 0.56f, 0.16f, 0.56f)
            }
            "chat" -> {
                box(-0.78f, -0.62f, 0.78f, 0.32f)
                ln(-0.24f, 0.32f, -0.34f, 0.62f)
                ln(-0.34f, 0.62f, 0.06f, 0.32f)
            }
            else -> box(-0.7f, -0.7f, 0.7f, 0.7f)
        }
    }

    // ---- the desktop the takeover starts from --------------------------------
    private fun barRect(): RectF = RectF(12f * u, h - 66f * u, w - 12f * u, h - 14f * u)

    private fun drawDesktop(canvas: Canvas) {
        fill.shader = LinearGradient(0f, 0f, 0f, h, OBSIDIAN, 0xFF1A111B.toInt(),
            Shader.TileMode.CLAMP)
        canvas.drawRect(0f, 0f, w, h, fill)
        fill.shader = null
        fill.color = withAlpha(MAROON, 0.18f)
        canvas.drawCircle(w * 0.05f, h * 0.95f, max(w, h) * 0.55f, fill)
        fill.color = withAlpha(MAROON_DEEP, 0.55f)
        canvas.drawCircle(w * 1.05f, h * 0.02f, max(w, h) * 0.40f, fill)

        // Shortcut column, in the same place the live launcher keeps it.
        val cellW = 108f * u
        val cellH = 78f * u
        for (i in ICON_LABELS.indices) {
            val cx = 16f * u + 48f * u + cellW * 0.5f
            val top = 22f * u + i * cellH
            val size = 50f * u
            rounded(canvas, RectF(cx - size / 2, top, cx + size / 2, top + size),
                13f * u, withAlpha(OBSIDIAN_DEEP, 0.84f))
            glyph(canvas, ICON_GLYPHS[i], cx, top + size / 2f, size * 0.52f, BLUSH)
            text(canvas, ICON_LABELS[i], cx, top + size + 15f * u, 8.6f * u,
                withAlpha(BLUSH, 0.72f), 1f * u, align = 1)
        }

        // The taskbar the desktop already shows.
        val bar = barRect()
        rounded(canvas, bar, 14f * u, withAlpha(0xFF0B0A0E.toInt(), 0.94f))
        stroke.color = withAlpha(BLUSH, 0.12f)
        stroke.strokeWidth = 1f
        canvas.drawRoundRect(bar, 14f * u, 14f * u, stroke)
        val cy = bar.centerY()
        val startX = bar.left + 32f * u
        rounded(canvas, RectF(startX - 17f * u, cy - 17f * u, startX + 17f * u,
            cy + 17f * u), 10f * u, withAlpha(MAROON, 0.88f))
        dotMatrix(canvas, "S", startX - 9f * u, cy + 7f * u, 1.9f * u, BLUSH)
        for ((index, name) in arrayOf("globe", "terminal", "folder").withIndex()) {
            glyph(canvas, name, bar.left + 84f * u + index * 54f * u, cy, 23f * u,
                withAlpha(BLUSH, 0.8f))
        }
        text(canvas, "09:41", bar.right - 18f * u, cy + 3.4f * u, 10f * u,
            withAlpha(BLUSH, 0.88f), 0.6f * u, align = 2)
    }

    // ---- act 1: error windows -------------------------------------------------
    private fun cardRect(e: Err): RectF {
        val lines = if (e.body.length <= 46) 1 else 2
        var content = (30f + 9f + 6f + 17f + 5f + 13f * lines + 8f + 11f) * u
        if (e.accent == 2) content += 15f * u
        val height = (e.hf * h).coerceIn(content, content * 1.45f)
        val width = max(e.wf * w, 250f * u)
        val cx = e.cx * w
        val cy = e.cy * h
        return RectF(cx - width / 2f, cy - height / 2f, cx + width / 2f, cy + height / 2f)
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
            val accent = ACCENTS[e.accent % ACCENTS.size]
            val a = progress

            // Shadow, then the panel: a floating sheet, not a system dialog.
            rounded(canvas, RectF(rect.left, rect.top + 8f * u, rect.right,
                rect.bottom + 8f * u), 10f * u, withAlpha(Color.BLACK, 0.42f * a))
            rounded(canvas, rect, 10f * u, withAlpha(PANEL, 0.97f * a))
            stroke.color = withAlpha(Color.WHITE, 0.09f * a)
            stroke.strokeWidth = 1f
            canvas.drawRoundRect(rect, 10f * u, 10f * u, stroke)
            rounded(canvas, RectF(rect.left, rect.top + 16f * u, rect.left + 3.2f * u,
                rect.bottom - 16f * u), 1.6f * u, withAlpha(accent, 0.9f * a))

            val left = rect.left + 19f * u
            fill.color = withAlpha(accent, 0.92f * a)
            canvas.drawRect(left, rect.top + 15f * u, left + 5f * u, rect.top + 20f * u, fill)
            text(canvas, CARD_HEADERS[e.accent % CARD_HEADERS.size],
                left + 11f * u, rect.top + 20.5f * u, 7.8f * u,
                withAlpha(0xC6BED6.toInt(), 0.62f * a), 1.15f * u)
            val titleColour = if (e.code == "0xA11A") 0xFFE0FFF8.toInt() else 0xFFF7F2FF.toInt()
            text(canvas, e.title, left, rect.top + 44f * u, 13.4f * u,
                withAlpha(titleColour, a), 0.55f * u, bold = true)

            var bodyY = rect.top + 62f * u
            var used = 0
            for (row in wrap(e.body, 9.8f * u, 0f, rect.width() - 41f * u)) {
                if (used == 2) break
                text(canvas, row, left, bodyY, 9.8f * u,
                    withAlpha(0xAEA6C2.toInt(), 0.92f * a))
                bodyY += 13.5f * u
                used++
            }
            if (e.code == "0xA11A") {
                val track = RectF(left, bodyY + 2f * u, rect.right - 22f * u,
                    bodyY + 5.2f * u)
                rounded(canvas, track, 1.6f * u, withAlpha(Color.WHITE, 0.13f * a))
                rounded(canvas, RectF(track.left, track.top,
                    track.left + track.width() * 0.62f, track.bottom), 1.6f * u,
                    withAlpha(mix(PURPLE, TEAL, 0.7f), 0.92f * a))
            }
            text(canvas, "NO RESPONSE", left, rect.bottom - 13f * u, 7.8f * u,
                withAlpha(0x988EA6.toInt(), 0.68f * a), 1.1f * u)
            text(canvas, e.code, rect.right - 19f * u, rect.bottom - 13f * u, 8.4f * u,
                withAlpha(accent, 0.92f * a), 0.8f * u, align = 2)

            if (flash > 0.02f) {
                stroke.color = withAlpha(accent, 0.7f * flash)
                stroke.strokeWidth = max(1f, 1.4f * u)
                canvas.drawRoundRect(rect, 10f * u, 10f * u, stroke)
            }
        }
    }

    private fun drawGlitch(canvas: Canvas, t: Float) {
        // A building tremor, brief flashes, one displaced band and fine grain.
        val shake = if (t < BLUE_START) 2.4f * u * ease(((t - 2600f) / 7200f)
            .coerceIn(0f, 1f)) else 0f
        if (shake > 0.05f) {
            canvas.translate(sin(t / 46f) * shake, cos(t / 61f) * shake * 0.55f)
        }
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
            fill.color = withAlpha(Color.BLACK, 0.22f)
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
        fill.color = withAlpha(0xFF5C8CE0.toInt(), 0.14f)
        canvas.drawCircle(w * 0.18f, -h * 0.05f, max(w, h) * 0.55f, fill)
        fill.color = withAlpha(0xFF6B43D8.toInt(), 0.12f)
        canvas.drawCircle(w * 0.95f, h * 1.02f, max(w, h) * 0.45f, fill)

        val pad = w * 0.075f
        // ---- header
        dotMatrix(canvas, "SMTH", pad, 46f * u, max(1.4f, 1.75f * u), BLUE_INK)
        text(canvas, "SMTH OS", pad + 98f * u, 38f * u, 11f * u, BLUE_INK, 1.2f * u,
            bold = true)
        text(canvas, "SESSION 03  ·  KERNEL EVENT", pad + 98f * u, 50f * u, 8.2f * u,
            withAlpha(BLUE_DIM, 0.68f), 1.4f * u)
        text(canvas, "AH1AN", w - pad, 38f * u, 8.2f * u, withAlpha(TEAL_BRIGHT, 0.84f),
            2.2f * u, align = 2)
        text(canvas, "AESTHETIC SUBSYSTEM ONLINE", w - pad, 50f * u, 8.2f * u,
            withAlpha(BLUE_DIM, 0.56f), 1.2f * u, align = 2)

        // ---- headline
        val size = min(0.066f * h, 0.036f * w)
        val tracking = 0.9f * u
        var y = 0.300f * h
        for (row in wrap("AHIAN HAS TAKEN CONTROL", size, tracking, w - 2 * pad)) {
            text(canvas, row, pad, y, size, BLUE_INK, tracking, bold = true)
            y += size * 1.16f
        }
        text(canvas, "AHIAN wants to make your life beautiful.", pad,
            y + size * 0.20f, size * 0.40f, withAlpha(BLUE_DIM, 0.94f), 0.4f * u)
        val ruleY = y + size * 0.78f
        line(canvas, pad, ruleY, pad + min(w - 2 * pad, 0.46f * w), ruleY,
            withAlpha(BLUE_RULE, 0.92f), max(1f, 1.2f * u))
        line(canvas, pad, ruleY, pad + 56f * u, ruleY, TEAL_BRIGHT, max(2f, 2.2f * u))

        // ---- countdown
        val progress = ((t - BLUE_START) / (BLUE_END - BLUE_START)).coerceIn(0f, 1f)
        val cy = 0.605f * h + 52f * u
        val radius = 44f * u
        val cx = pad + radius
        stroke.color = withAlpha(BLUE_RULE, 0.86f)
        stroke.strokeWidth = max(1f, 1.4f * u)
        canvas.drawCircle(cx, cy, radius, stroke)
        val sweep = 360f * (1f - progress)
        if (sweep > 0.5f) {
            stroke.color = TEAL_BRIGHT
            stroke.strokeWidth = max(2f, 2.6f * u)
            canvas.drawArc(RectF(cx - radius, cy - radius, cx + radius, cy + radius),
                270f, sweep, false, stroke)
        }
        val sinceTick = (BLUE_END - t) / 1000f
        val tick = (1f - (sinceTick - sinceTick.toInt()) / 0.28f).coerceIn(0f, 1f)
        text(canvas, countdown(t).toString(), cx, cy + 15f * u,
            40f * u * (1f + 0.06f * tick), BLUE_INK, 0f, bold = true, align = 1)

        val textX = cx + radius + 26f * u
        text(canvas, "RECONFIGURING DESKTOP", textX, cy - 23f * u, 8.6f * u,
            withAlpha(BLUE_DIM, 0.84f), 2.4f * u)
        text(canvas, "AHIAN is rebuilding your reality", textX, cy - 7f * u, 11.4f * u,
            withAlpha(BLUE_INK, 0.94f), 0.4f * u)
        val barRight = min(w - textX - pad, 330f * u) + textX
        val barTop = cy + 10f * u
        rounded(canvas, RectF(textX, barTop, barRight, barTop + 3.6f * u), 2f * u,
            withAlpha(0xD2EBFF.toInt(), 0.18f))
        val fillTo = textX + (barRight - textX) * progress
        if (fillTo > textX + 1f) {
            rounded(canvas, RectF(textX, barTop, fillTo, barTop + 3.6f * u), 2f * u,
                TEAL_BRIGHT)
        }
        for (i in 0 until COUNTDOWN_FROM) {
            val x = textX + i * 14f * u
            val on = progress >= (i + 1) / COUNTDOWN_FROM.toFloat()
            fill.color = if (on) TEAL_BRIGHT else withAlpha(BLUE_RULE, 0.55f)
            canvas.drawRect(x, cy + 22f * u, x + 8f * u, cy + 26f * u, fill)
        }
        text(canvas, "${(progress * 100).toInt()}%", barRight + 14f * u,
            cy + 14f * u, 8f * u, withAlpha(BLUE_DIM, 0.84f), 0.8f * u)

        // ---- footer
        val metaY = 0.870f * h
        text(canvas, "STOP CODE: AH1AN_ASCENSION", pad, metaY, 8.6f * u,
            withAlpha(BLUE_DIM, 0.82f), 1.6f * u)
        text(canvas, "0x0000AH1A  ·  MODE: AHIAN", pad, metaY + 17f * u, 8.2f * u,
            withAlpha(BLUE_DIM, 0.57f), 1.4f * u)
        val pulse = 0.55f + 0.45f * sin(t / 260f)
        fill.color = withAlpha(TEAL_BRIGHT, 0.47f + 0.47f * pulse)
        canvas.drawCircle(w - pad - 4f * u, metaY - 9f * u, 3.4f * u, fill)
        text(canvas, "DO NOT POWER OFF", w - pad - 14f * u, metaY, 8.6f * u,
            withAlpha(BLUE_DIM, 0.68f), 1.6f * u, align = 2)
        text(canvas, "AHIAN / 9.0 SEC", w - pad, metaY + 17f * u, 8.2f * u,
            withAlpha(BLUE_DIM, 0.53f), 1.4f * u, align = 2)
    }

    // ---- act 3: the AHIAN desktop --------------------------------------------
    private fun drawWallpaper(canvas: Canvas, phase: Float) {
        val stops = IntArray(9) { i ->
            val k = i / 8f
            flow(k, k * 0.62f, phase)
        }
        fill.shader = LinearGradient(0f, 0f, w, h, stops, null, Shader.TileMode.CLAMP)
        canvas.drawRect(0f, 0f, w, h, fill)
        fill.shader = null
        fill.color = withAlpha(PURPLE, 0.28f)
        canvas.drawCircle(w * 0.10f, h * 0.16f, max(w, h) * 0.45f, fill)
        fill.color = withAlpha(TEAL, 0.22f)
        canvas.drawCircle(w * 1.02f, h * 1.04f, max(w, h) * 0.42f, fill)
        val step = 34f * u
        fill.color = withAlpha(INK, 0.055f)
        var y = step
        while (y < h) {
            var x = step
            while (x < w) {
                canvas.drawCircle(x, y, max(0.9f, 1.0f * u), fill)
                x += step
            }
            y += step
        }
    }

    private fun drawBlackHole(canvas: Canvas, t: Float, alpha: Float) {
        if (alpha <= 0.01f) return
        val cx = w * 0.66f
        val cy = h * 0.50f
        val radius = h * 0.105f
        val scale = h / 1080f
        val seconds = t / 1000f
        val cs = cos(-0.22f)
        val sn = sin(-0.22f)
        val tilt = 0.27f
        val gold = (PI * (3 - sqrt(5.0))).toFloat()
        val dotPaint = Paint(Paint.ANTI_ALIAS_FLAG)
        for (i in 0 until 280) {
            val rr = 1.45f + 2.95f * sqrt((i + 0.5f) / 280f)
            val angle = i * gold + 0.55f * (1.45f / rr).pow(1.5f) * seconds
            val r = rr * radius
            val x = r * cos(angle)
            val s = sin(angle)
            val yy = if (s >= 0f) r * s * tilt
            else -sqrt(max(0f, r * r - x * x)) * 0.93f
            val tr = (rr - 1.45f) / 2.95f
            val bright = 0.62f - 0.38f * cos(angle)
            val size = max(1f, (1f + 3.4f * bright * (1f - 0.55f * tr)) * scale * 0.9f)
            val px = cx + x * cs - yy * sn
            val py = cy + x * sn + yy * cs
            dotPaint.color = withAlpha(if (i % 2 == 0) TEAL else PURPLE_SOFT,
                0.82f * bright * alpha)
            canvas.drawCircle(px, py, size, dotPaint)
        }
        fill.color = withAlpha(0xFF05030A.toInt(), alpha)
        canvas.drawCircle(cx, cy, radius, fill)
        stroke.color = withAlpha(TEAL_BRIGHT, 0.92f * alpha)
        stroke.strokeWidth = max(1f, (1.2f + 1.8f * (0.65f + 0.35f *
            sin(seconds * 2.2f))) * scale)
        canvas.drawCircle(cx, cy, radius * 1.08f, stroke)
    }

    private fun Float.pow(exp: Float): Float = Math.pow(this.toDouble(), exp.toDouble())
        .toFloat()

    private fun drawBrand(canvas: Canvas, t: Float) {
        if (t < BRAND_START) return
        val settle = easeInOut(((t - BRAND_SETTLE) / (BRAND_SETTLED - BRAND_SETTLE))
            .coerceIn(0f, 1f))
        val brandAlpha = 1f - settle
        if (brandAlpha <= 0.02f) return
        val markW = min(0.42f * w, 0.50f * h * (23f / 7f))
        val spacing = markW / 23f * (1f - 0.06f * settle)
        val dot = spacing * 0.30f
        val cx = 0.5f * w
        val cy = (0.44f - 0.045f * settle) * h
        val originX = cx - (23 * spacing) / 2f
        val originY = cy - (7 * spacing) / 2f
        for ((col, row) in brandDots()) {
            val order = (col / 22f) * 0.62f + (row / 6f) * 0.38f
            val start = BRAND_START + order * (BRAND_MS - 260f)
            val progress = ((t - start) / 260f).coerceIn(0f, 1f)
            if (progress <= 0f) continue
            val radius = dot * (1.16f - 0.16f * ease(progress))
            val x = originX + (col + 0.5f) * spacing
            val y = originY + (row + 0.5f) * spacing
            fill.color = withAlpha(mix(PURPLE_SOFT, TEAL_BRIGHT,
                col / 22f * 0.7f + row / 6f * 0.3f), brandAlpha * progress)
            canvas.drawCircle(x, y, radius, fill)
        }
        val ruleW = markW * 0.74f * ease(((t - BRAND_START) / BRAND_MS).coerceIn(0f, 1f))
        val ruleY = cy + (7 * spacing) / 2f + 26f * u
        line(canvas, cx - ruleW / 2f, ruleY, cx + ruleW / 2f, ruleY,
            withAlpha(TEAL_BRIGHT, 0.82f * brandAlpha), 1f)
        if (brandAlpha > 0.3f) {
            text(canvas, "A H I A N", cx, ruleY + 21f * u, 8.6f * u,
                withAlpha(INK, 0.62f * brandAlpha), 3f * u, align = 1)
        }
    }

    private fun brandDots(): List<Pair<Int, Int>> {
        val dots = ArrayList<Pair<Int, Int>>()
        for ((index, ch) in "SMTH".withIndex()) {
            val rows = BRAND_GLYPHS[ch] ?: continue
            for (row in 0 until 7) {
                for (col in 0 until 5) {
                    if ((rows[row] shr (4 - col)) and 1 == 1) {
                        dots.add((index * 6 + col) to row)
                    }
                }
            }
        }
        return dots
    }

    private fun drawTaskbar(canvas: Canvas, progress: Float) {
        if (progress <= 0.005f) return
        val bar = barRect()
        val rise = (1f - progress) * bar.height() * 1.5f
        bar.offset(0f, rise)
        rounded(canvas, RectF(bar.left, bar.top + 4f * u, bar.right, bar.bottom + 4f * u),
            16f * u, withAlpha(Color.BLACK, 0.35f * progress))
        rounded(canvas, bar, 16f * u, withAlpha(0xFF0E0C18.toInt(), 0.93f * progress))
        stroke.color = withAlpha(TEAL, 0.24f * progress)
        stroke.strokeWidth = 1f
        canvas.drawRoundRect(bar, 16f * u, 16f * u, stroke)
        val cy = bar.centerY()
        val startX = bar.left + 32f * u
        rounded(canvas, RectF(startX - 17f * u, cy - 17f * u, startX + 17f * u,
            cy + 17f * u), 10f * u, withAlpha(PURPLE, 0.88f * progress))
        dotMatrix(canvas, "S", startX - 9f * u, cy + 7f * u, 1.9f * u,
            withAlpha(INK, 0.95f * progress))
        for ((index, name) in arrayOf("globe", "terminal", "folder").withIndex()) {
            glyph(canvas, name, bar.left + 84f * u + index * 54f * u, cy, 23f * u,
                withAlpha(INK, 0.84f * progress))
        }
        text(canvas, "09:41", bar.right - 18f * u, cy + 3.4f * u, 10f * u,
            withAlpha(INK, 0.9f * progress), 0.6f * u, align = 2)
    }

    private fun drawDesktopIcons(canvas: Canvas, t: Float) {
        val cellW = 108f * u
        val cellH = 78f * u
        for (i in ICON_LABELS.indices) {
            val start = ICON_START + i * ICON_STEP
            val progress = ease(((t - start) / ICON_MS).coerceIn(0f, 1f))
            if (progress <= 0f) continue
            val cx = 16f * u + 48f * u + cellW * 0.5f
            val top = 22f * u + i * cellH + (1f - progress) * 16f * u
            val size = 50f * u * (0.9f + 0.1f * progress)
            val accent = ACCENTS[(i + 2) % ACCENTS.size]
            rounded(canvas, RectF(cx - size / 2, top, cx + size / 2, top + size),
                13f * u, withAlpha(0xFF0E0B1A.toInt(), 0.82f * progress))
            stroke.color = withAlpha(accent, 0.35f * progress)
            stroke.strokeWidth = 1f
            canvas.drawRoundRect(RectF(cx - size / 2, top, cx + size / 2, top + size),
                13f * u, 13f * u, stroke)
            glyph(canvas, ICON_GLYPHS[i], cx, top + size / 2f, size * 0.52f,
                withAlpha(INK, 0.94f * progress))
            text(canvas, ICON_LABELS[i], cx, top + size + 15f * u, 8.6f * u,
                withAlpha(INK, 0.78f * progress), 1f * u, align = 1)
        }
    }

    private fun drawClock(canvas: Canvas, progress: Float) {
        if (progress <= 0.005f) return
        val rise = (1f - progress) * 14f * u
        val x = 30f * u
        val baseline = h - 112f * u + rise
        val dot = 3.4f * u
        val time = "09:41"
        for (index in time.indices) {
            val rows = DIGIT_GLYPHS[time[index]] ?: continue
            for (row in 0 until 7) {
                for (col in 0 until 5) {
                    if ((rows[row] shr (4 - col)) and 1 != 1) continue
                    val cx = x + (index * 6 + col) * dot
                    val cy = baseline - (6 - row) * dot
                    fill.color = withAlpha(if ((index * 6 + col) % 2 == 0) PURPLE_SOFT
                    else TEAL_BRIGHT, 0.95f * progress)
                    canvas.drawCircle(cx, cy, dot * 0.38f, fill)
                }
            }
        }
        text(canvas, "FRIDAY 21 NOVEMBER", x, baseline + 28f * u, 8f * u,
            withAlpha(INK, 0.55f * progress), 1.6f * u)
    }

    private fun drawToast(canvas: Canvas, t: Float) {
        val toastIn = ease(((t - TOAST_START) / TOAST_MS).coerceIn(0f, 1f))
        val toastOut = ((t - TOAST_END) / 420f).coerceIn(0f, 1f)
        val progress = toastIn * (1f - toastOut)
        if (progress <= 0.01f) return
        val label = "AHIAN  ·  UPGRADE COMPLETE"
        val size = 8.8f * u
        val width = textWidth(label, size, 1.6f * u) + 64f * u
        val height = 34f * u
        val x = (w - width) / 2f
        val y = h - 122f * u + (1f - progress) * 12f * u
        rounded(canvas, RectF(x, y + 3f * u, x + width, y + height + 3f * u),
            height / 2f, withAlpha(Color.BLACK, 0.38f * progress))
        rounded(canvas, RectF(x, y, x + width, y + height), height / 2f,
            withAlpha(0xFF0B0A10.toInt(), 0.93f * progress))
        stroke.color = withAlpha(TEAL, 0.43f * progress)
        stroke.strokeWidth = 1f
        canvas.drawRoundRect(RectF(x, y, x + width, y + height), height / 2f,
            height / 2f, stroke)
        fill.color = withAlpha(TEAL_BRIGHT, progress)
        canvas.drawCircle(x + 22f * u, y + height / 2f, 3.4f * u, fill)
        text(canvas, label, x + 36f * u, y + height / 2f + 3.2f * u, size,
            withAlpha(INK, 0.94f * progress), 1.6f * u)
    }

    // ---- frame ---------------------------------------------------------------
    private fun crtOpen(t: Float): Float = when {
        t < BLUE_OPEN_START -> 0f
        t < BLUE_OPEN_START + BLUE_OPEN_MS ->
            easeInOut((t - BLUE_OPEN_START) / BLUE_OPEN_MS)
        t < BLUE_END - BLUE_CLOSE_MS -> 1f
        t < BLUE_END -> 1f - easeInOut((t - (BLUE_END - BLUE_CLOSE_MS)) / BLUE_CLOSE_MS)
        t < WALL_OPEN_START -> 0f
        t < WALL_OPEN_START + WALL_OPEN_MS ->
            easeInOut((t - WALL_OPEN_START) / WALL_OPEN_MS)
        else -> 1f
    }

    private fun squeeze(canvas: Canvas, open: Float, edge: Int): Boolean {
        if (open >= 0.999f) return false
        val bandH = max(2f, h * open)
        val top = (h - bandH) / 2f
        canvas.save()
        canvas.clipRect(0f, top, w, top + bandH)
        lastBand = Pair(top, bandH)
        lastEdge = edge
        return true
    }

    private var lastBand = Pair(0f, 0f)
    private var lastEdge = 0

    private fun endSqueeze(canvas: Canvas) {
        canvas.restore()
        val (top, bandH) = lastBand
        fill.color = lastEdge
        canvas.drawRect(0f, top - max(1f, 1.6f * u), w, top, fill)
        canvas.drawRect(0f, top + bandH, w, top + bandH + max(1f, 1.6f * u), fill)
        canvas.drawRect(0f, top + bandH / 2f - 1f, w, top + bandH / 2f + 1f, fill)
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        w = width.toFloat()
        h = height.toFloat()
        if (w <= 0f || h <= 0f) return
        u = min(w / 1280f, h / 800f)
        if (h >= w * 0.95f) u = min(w / 900f, h / 1600f)
        u = u.coerceIn(0.72f, 2.6f)

        val t = elapsed.coerceIn(0f, if (reduced) REDUCED_MS.toFloat()
        else DURATION_MS.toFloat())
        if (reduced) {
            drawWallpaper(canvas, 0f)
            drawBlackHole(canvas, FADE_START + 90f, 1f)
            drawDesktopIcons(canvas, DURATION_MS.toFloat())
            drawClock(canvas, 1f)
            drawTaskbar(canvas, 1f)
            return
        }

        canvas.drawColor(OBSIDIAN_DEEP)
        if (t < BLUE_START) {
            canvas.save()
            drawDesktop(canvas)
            // Dim the desktop as the windows pile up.
            fill.color = withAlpha(Color.BLACK, ease(t / BLUE_START) * 0.46f)
            canvas.drawRect(0f, 0f, w, h, fill)
            drawCards(canvas, t)
            drawGlitch(canvas, t)
            canvas.restore()
            return
        }

        if (t < BLUE_END) {
            val open = crtOpen(t)
            if (t < BLUE_OPEN_START) {
                // The desktop is squeezed into the line the blue screen opens from.
                val squeezeAmount = 1f - ((t - BLUE_START) / COLLAPSE_MS).coerceIn(0f, 1f)
                canvas.save()
                drawDesktop(canvas)
                fill.color = withAlpha(Color.BLACK, 0.46f)
                canvas.drawRect(0f, 0f, w, h, fill)
                drawCards(canvas, BLUE_START)
                canvas.restore()
                if (squeeze(canvas, squeezeAmount, 0xFFCEE8FF.toInt())) endSqueeze(canvas)
                return
            }
            val clipped = squeeze(canvas, open, 0xFFD7F0FF.toInt())
            drawBlue(canvas, t)
            if (clipped) endSqueeze(canvas)
            drawGlitch(canvas, t)
            return
        }

        val open = crtOpen(t)
        if (t < WALL_OPEN_START) {
            val squeezeAmount = 1f - ((t - BLUE_END) / BLUE_CLOSE_MS).coerceIn(0f, 1f)
            val clipped = squeeze(canvas, squeezeAmount, 0xFFD7F0FF.toInt())
            drawBlue(canvas, BLUE_END - 40f)
            if (clipped) endSqueeze(canvas)
            return
        }
        val clipped = squeeze(canvas, open, 0xFFAAFFF0.toInt())
        val phase = (((BLUE_END - t) / 1000f) * 0.022f) % 1f
        drawWallpaper(canvas, (phase + 1f) % 1f)
        val hole = ease(((t - HOLE_START) / 1150f).coerceIn(0f, 1f))
        drawBlackHole(canvas, t, hole)
        drawBrand(canvas, t)
        drawDesktopIcons(canvas, t)
        drawClock(canvas, ease(((t - WIDGET_START) / WIDGET_MS).coerceIn(0f, 1f)))
        drawTaskbar(canvas, ease(((t - PANEL_START) / PANEL_MS).coerceIn(0f, 1f)))
        drawToast(canvas, t)
        if (clipped) endSqueeze(canvas)
    }
}
