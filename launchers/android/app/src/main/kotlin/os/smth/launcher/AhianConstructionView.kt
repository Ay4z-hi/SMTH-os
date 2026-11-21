package os.smth.launcher

import android.animation.Animator
import android.animation.AnimatorListenerAdapter
import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.Shader
import android.graphics.Typeface
import android.provider.Settings
import android.view.View
import android.view.animation.LinearInterpolator
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.math.cos
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin
import kotlin.random.Random

/**
 * AHIAN desktop reconstruction reveal (about 9 seconds).
 *
 * The desktop rebuilds itself: purple/teal fragments drift in, the wallpaper
 * assembles from geometric dot-matrix tiles, the taskbar draws itself, then the
 * desktop icons materialise in their real positions and the overlay fades into
 * the live launcher. There are no cursors anywhere in this sequence.
 *
 * The final frame is drawn with exactly the same crop, scrim and gradient tint
 * as the live launcher, so the fade reveals the desktop that is already there
 * instead of reloading a second wallpaper.
 *
 * Reduce Motion (system animator scale 0) collapses this to a short fade of the
 * finished scene. A rendering failure in the caller must still leave a usable
 * desktop: this view never blocks touch after it completes.
 */
class AhianConstructionView(context: Context) : View(context) {
    companion object {
        private const val DURATION_MS = 9000L
        private const val REDUCED_MS = 600L
        private const val VOID_END = 1000f
        private const val WALL_START = 1000f
        private const val WALL_END = 3000f
        private const val STRUCT_START = 3000f
        private const val STRUCT_END = 5000f
        private const val ELEMENTS_START = 5000f
        private const val ELEMENTS_END = 7000f
        private const val REVEAL_START = 7600f
        private const val FADE_END = 9000f
        private const val TILE_SPAN = 1400f
        private const val TILE_DURATION = 480f
        private const val PARTICLE_END = 3400f

        private val ICON_LABELS = arrayOf(
            "TERMINAL", "CHROME", "PHONE", "MESSAGES", "CAMERA", "SETTINGS",
        )
        private val RING_STARTS = floatArrayOf(1050f, 1400f, 1750f, 2100f)
        private const val RING_DURATION = 1250f
        private val SEGMENT_FRACTIONS = floatArrayOf(0.085f, 0.095f, 0.095f, 0.095f, 0.11f, 0.16f)
        private const val ICON_COUNT = 6
    }

    private val density = context.resources.displayMetrics.density
    private fun dp(v: Float) = v * density

    private val dark = Color.parseColor("#07060D")
    private val obsidian = Color.parseColor("#09090B")
    private val panel = Color.parseColor("#120A24")
    private val purple = Color.parseColor("#7C4DFF")
    private val teal = Color.parseColor("#2BD9C4")
    private val purpleSoft = Color.parseColor("#9E75FF")
    private val tealBright = Color.parseColor("#33E5CC")
    private val violet = Color.parseColor("#5738A0")
    private val ink = Color.parseColor("#EDE7FF")
    private val grey = Color.parseColor("#8C879C")

    private val fill = Paint(Paint.ANTI_ALIAS_FLAG)
    private val stroke = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = dp(1f)
    }
    private val text = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        typeface = Typeface.MONOSPACE
        textAlign = Paint.Align.LEFT
    }

    private val wallpaper: Bitmap? = try {
        BitmapFactory.decodeResource(resources, R.drawable.smth_wallpaper)
    } catch (e: Exception) {
        null
    }

    private var wallShader: LinearGradient? = null
    private var scrimShader: LinearGradient? = null
    private var shaderWidth = 0
    private var shaderHeight = 0
    private var dest = RectF()

    private data class Fragment(
        val x: Float, val y: Float, val vx: Float, val vy: Float,
        val r: Float, val phase: Float, val colour: Int,
    )

    private val fragments: List<Fragment> by lazy {
        val rng = Random(1107)
        val colours = intArrayOf(purple, teal, purpleSoft, tealBright, violet)
        List(42) { i ->
            Fragment(
                x = 0.02f + rng.nextFloat() * 0.96f,
                y = 0.02f + rng.nextFloat() * 0.96f,
                vx = -0.012f + rng.nextFloat() * 0.024f,
                vy = -0.020f + rng.nextFloat() * 0.014f,
                r = 0.0016f + rng.nextFloat() * 0.0032f,
                phase = rng.nextFloat() * 6.2832f,
                colour = colours[i % colours.size],
            )
        }
    }

    private var elapsed = 0f
    private var animator: ValueAnimator? = null
    private var reduced = false

    init {
        setBackgroundColor(dark)
        contentDescription = "AHIAN desktop reconstruction; tap to skip"
        isClickable = true
        setOnClickListener { finish() }
    }

    /** Reads the system animator scale so Reduce Motion skips the long sequence. */
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

    private fun finish() {
        if (animator?.isRunning == true) {
            animator?.end()
        }
    }

    override fun onDetachedFromWindow() {
        animator?.cancel()
        super.onDetachedFromWindow()
    }

    private fun overlayAlpha(t: Float): Float {
        if (reduced) return (1f - t / REDUCED_MS.toFloat()).coerceIn(0f, 1f)
        return if (t < REVEAL_START) 1f
        else (1f - (t - REVEAL_START) / (FADE_END - REVEAL_START)).coerceIn(0f, 1f)
    }

    // ---- helpers ------------------------------------------------------------
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

    private fun withAlpha(colour: Int, a: Float): Int {
        val alpha = (a.coerceIn(0f, 1f) * 255f).toInt().coerceIn(0, 255)
        return (colour and 0x00FFFFFF) or (alpha shl 24)
    }

    private fun buildShaders(w: Int, h: Int) {
        if (w == shaderWidth && h == shaderHeight) return
        shaderWidth = w
        shaderHeight = h
        wallShader = LinearGradient(
            0f, 0f, w.toFloat(), h.toFloat(),
            intArrayOf(purple, teal), null, Shader.TileMode.CLAMP,
        )
        scrimShader = LinearGradient(
            0f, 0f, 0f, h.toFloat(),
            intArrayOf(
                withAlpha(obsidian, 0.58f),
                withAlpha(obsidian, 0.18f),
                withAlpha(obsidian, 0.66f),
            ),
            floatArrayOf(0f, 0.45f, 1f), Shader.TileMode.CLAMP,
        )
        val bmp = wallpaper
        if (bmp == null) {
            dest = RectF(0f, 0f, w.toFloat(), h.toFloat())
        } else {
            val scale = max(w.toFloat() / bmp.width, h.toFloat() / bmp.height)
            val dw = bmp.width * scale
            val dh = bmp.height * scale
            dest = RectF((w - dw) / 2f, (h - dh) / 2f, (w + dw) / 2f, (h + dh) / 2f)
        }
    }

    // ---- draw ---------------------------------------------------------------
    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val w = width.toFloat()
        val h = height.toFloat()
        if (w <= 0f || h <= 0f) return
        buildShaders(width, height)
        val t = elapsed.coerceIn(0f, (if (reduced) REDUCED_MS else DURATION_MS).toFloat())
        canvas.drawColor(dark)
        drawWallpaper(canvas, w, h, t)
        drawRings(canvas, w, h, t)
        drawFragments(canvas, w, h, t)
        drawStructure(canvas, w, h, t)
        drawWindow(canvas, w, h, t)
    }

    private fun drawWallpaper(canvas: Canvas, w: Float, h: Float, t: Float) {
        val cols = if (w >= h) 14 else 8
        val rows = if (w >= h) 8 else 14
        val tileW = w / cols
        val tileH = h / rows
        val detail = (1f - (t - 2400f) / 900f).coerceIn(0f, 1f)
        for (row in 0 until rows) {
            for (col in 0 until cols) {
                val order = (col.toFloat() / (cols - 1)) * 0.58f +
                    (row.toFloat() / (rows - 1)) * 0.42f
                val start = WALL_START + order * TILE_SPAN
                val progress = ((t - start) / TILE_DURATION).coerceIn(0f, 1f)
                if (progress <= 0f) continue
                val a = if (reduced) 1f else ease(progress)
                val scale = 0.82f + 0.18f * a
                val cx = col * tileW + tileW / 2f
                val cy = row * tileH + tileH / 2f
                canvas.save()
                canvas.translate(cx, cy)
                canvas.scale(scale, scale)
                canvas.translate(-cx, -cy)
                val left = col * tileW
                val top = row * tileH
                canvas.clipRect(left, top, left + tileW + 0.6f, top + tileH + 0.6f)
                // The same flowing gradient the live wallpaper draws, sampled
                // at this tile. Phase 1 (final frame) equals live phase 0.
                fill.shader = null
                fill.color = withAlpha(
                    AhianFlow.color((col + 0.5f) / cols, (row + 0.5f) / rows,
                        if (reduced) 0f else (t / DURATION_MS.toFloat())),
                    a,
                )
                canvas.drawRect(left, top, left + tileW + 0.6f, top + tileH + 0.6f, fill)
                fill.alpha = 255
                // Dot-matrix construction detail, gone once the wall is assembled.
                if (detail > 0.01f) {
                    val tint = mix(purple, teal, order)
                    val n = 3
                    val sx = tileW / (n + 1)
                    val sy = tileH / (n + 1)
                    fill.shader = null
                    fill.color = withAlpha(tint, 0.55f * a * detail)
                    for (r in 0 until n) {
                        for (c in 0 until n) {
                            canvas.drawCircle(
                                left + sx * (c + 1), top + sy * (r + 1),
                                max(1f, min(sx, sy) * 0.08f), fill,
                            )
                        }
                    }
                }
                canvas.restore()
            }
        }
    }

    private fun drawRings(canvas: Canvas, w: Float, h: Float, t: Float) {
        if (reduced) return
        val base = min(w, h)
        val cx = w * 0.5f
        val cy = h * 0.48f
        RING_STARTS.forEachIndexed { index, start ->
            val progress = ((t - start) / RING_DURATION).coerceIn(0f, 1f)
            if (progress <= 0f || progress >= 1f) return@forEachIndexed
            stroke.color = withAlpha(mix(purple, teal, index / 3f), (1f - progress) * 0.42f)
            stroke.strokeWidth = dp(1.2f)
            canvas.drawCircle(cx, cy, base * (0.05f + 0.42f * easeInOut(progress)), stroke)
        }
    }

    private fun drawFragments(canvas: Canvas, w: Float, h: Float, t: Float) {
        if (reduced || t > PARTICLE_END) return
        val alpha = (t / 420f).coerceIn(0f, 1f) *
            ((PARTICLE_END - t) / 900f).coerceIn(0f, 1f)
        if (alpha <= 0f) return
        val seconds = t / 1000f
        fill.shader = null
        for (f in fragments) {
            val x = wrap(f.x + f.vx * seconds + 0.004f * sin(seconds * 1.7f + f.phase))
            val y = wrap(f.y + f.vy * seconds)
            val pulse = 0.55f + 0.45f * sin(seconds * 2.4f + f.phase)
            fill.color = withAlpha(f.colour, alpha * (0.24f + 0.34f * pulse))
            canvas.drawCircle(x * w, y * h, max(1f, f.r * min(w, h)), fill)
        }
    }

    private fun wrap(v: Float): Float {
        val m = v % 1f
        return if (m < 0f) m + 1f else m
    }

    private fun drawStructure(canvas: Canvas, w: Float, h: Float, t: Float) {
        val barLeft = dp(12f)
        val barTop = h - dp(56f)
        val barRight = w - dp(12f)
        val barBottom = h - dp(10f)
        val bar = RectF(barLeft, barTop, barRight, barBottom)
        val barProgress = ((t - STRUCT_START) / 620f).coerceIn(0f, 1f)
        val a = if (reduced) 1f else ease(barProgress)
        if (a > 0f) {
            fill.shader = null
            fill.color = withAlpha(panel, 0.92f * a)
            canvas.drawRoundRect(bar, dp(13f), dp(13f), fill)
            stroke.color = withAlpha(teal, 0.42f * a)
            stroke.strokeWidth = dp(1f)
            canvas.drawRoundRect(bar, dp(13f), dp(13f), stroke)
            text.color = withAlpha(ink, a)
            text.textSize = dp(10f)
            canvas.drawText("SMTH", barLeft + dp(14f), barTop + dp(28f), text)
            val time = SimpleDateFormat("HH:mm", Locale.getDefault()).format(Date())
            text.color = withAlpha(tealBright, a)
            text.textAlign = Paint.Align.RIGHT
            canvas.drawText(time, barRight - dp(14f), barTop + dp(21f), text)
            text.color = withAlpha(ink, 0.58f * a)
            text.textSize = dp(8f)
            canvas.drawText(
                SimpleDateFormat("EEE dd MMM", Locale.getDefault()).format(Date()).uppercase(),
                barRight - dp(14f), barTop + dp(35f), text,
            )
            text.textAlign = Paint.Align.LEFT
        }
        // Taskbar segments assemble one after another.
        if (!reduced) {
            val usable = bar.width() - dp(16f)
            var x = barLeft + dp(8f)
            SEGMENT_FRACTIONS.forEachIndexed { i, frac ->
                val width = max(dp(18f), usable * frac)
                val progress = ((t - (STRUCT_START + i * 110f)) / 360f).coerceIn(0f, 1f)
                if (progress > 0f) {
                    val accent = when (i % 3) {
                        0 -> purple
                        1 -> teal
                        else -> purpleSoft
                    }
                    fill.shader = null
                    fill.color = withAlpha(accent, 0.22f * progress)
                    canvas.drawRoundRect(
                        x, barTop + dp(9f), x + width * progress, barBottom - dp(9f),
                        dp(2f), dp(2f), fill,
                    )
                }
                x += width + dp(8f)
            }
        }
        // Desktop icons materialise in place, in the launcher's own positions.
        for (i in 0 until ICON_COUNT) {
            val start = ELEMENTS_START + i * 140f
            val progress = ((t - start) / 380f).coerceIn(0f, 1f)
            if (progress <= 0f) continue
            val scale = 0.72f + 0.28f * ease(progress)
            val cx = dp(20f) + dp(44f)
            val cy = dp(18f) + dp(30f) + i * dp(66f)
            canvas.save()
            canvas.translate(cx, cy)
            canvas.scale(scale, scale)
            canvas.translate(-cx, -cy)
            val rect = RectF(cx - dp(42f), cy - dp(28f), cx + dp(42f), cy + dp(28f))
            val accent = when (i % 6) {
                0 -> purple
                1 -> teal
                2 -> purpleSoft
                3 -> tealBright
                4 -> violet
                else -> purple
            }
            fill.shader = null
            fill.color = withAlpha(panel, 0.55f * progress)
            canvas.drawRoundRect(rect, dp(6f), dp(6f), fill)
            stroke.color = withAlpha(accent, 0.75f * progress)
            stroke.strokeWidth = dp(1f)
            canvas.drawRoundRect(rect, dp(6f), dp(6f), stroke)
            // 3x3 dot-matrix app mark.
            val dot = dp(3f)
            val gx = cx - dot * 2.4f
            val gy = cy - dp(12f)
            fill.color = withAlpha(accent, 0.9f * progress)
            for (r in 0 until 3) {
                for (c in 0 until 3) {
                    if ((r + c + i) % 4 == 3) continue
                    canvas.drawCircle(gx + c * dot * 1.6f, gy + r * dot * 1.6f, dot * 0.44f, fill)
                }
            }
            text.color = withAlpha(ink, progress)
            text.textSize = dp(8.5f)
            text.textAlign = Paint.Align.CENTER
            canvas.drawText(ICON_LABELS[i], cx, cy + dp(24f), text)
            text.textAlign = Paint.Align.LEFT
            canvas.restore()
        }
    }

    private fun drawWindow(canvas: Canvas, w: Float, h: Float, t: Float) {
        val start = ELEMENTS_START + 280f
        val progress = ((t - start) / 900f).coerceIn(0f, 1f)
        if (progress <= 0f) return
        val fade = if (t > 6500f) (1f - (t - 6500f) / 420f).coerceIn(0f, 1f) else 1f
        if (fade <= 0f) return
        if (reduced) return
        val a = ease(progress) * fade
        val rect = RectF(w * 0.28f, h * 0.18f, w * 0.72f, h * 0.68f)
        fill.shader = null
        fill.color = withAlpha(panel, 0.82f * a)
        canvas.drawRoundRect(rect, dp(8f), dp(8f), fill)
        stroke.color = withAlpha(purple, 0.6f * a)
        stroke.strokeWidth = dp(1f)
        canvas.drawRoundRect(rect, dp(8f), dp(8f), stroke)
        val barH = dp(28f)
        fill.color = withAlpha(Color.BLACK, 0.55f * a)
        canvas.drawRoundRect(
            RectF(rect.left, rect.top, rect.right, rect.top + barH),
            dp(8f), dp(8f), fill,
        )
        val dots = intArrayOf(purple, teal, purpleSoft)
        dots.forEachIndexed { i, colour ->
            fill.color = withAlpha(colour, 0.95f * a)
            canvas.drawCircle(rect.left + dp(16f) + i * dp(14f), rect.top + barH / 2f, dp(3f), fill)
        }
        text.color = withAlpha(ink, a)
        text.textSize = dp(9f)
        canvas.drawText("SMTH / WINDOW", rect.left + dp(66f), rect.top + dp(19f), text)
        text.textSize = dp(10f)
        canvas.drawText("DESKTOP RECONSTRUCTION", rect.left + dp(18f), rect.top + dp(56f), text)
        val lineW = rect.width() - dp(36f)
        for (i in 0 until 4) {
            val y = rect.top + dp(76f) + i * dp(20f)
            if (y > rect.bottom - dp(70f)) break
            fill.color = withAlpha(if (i == 0) teal else purple, (if (i == 0) 0.5f else 0.22f) * a)
            canvas.drawRect(
                rect.left + dp(18f), y,
                rect.left + dp(18f) + lineW * (0.78f - i * 0.12f), y + dp(4f), fill,
            )
        }
        val base = rect.bottom - dp(18f)
        val bars = 14
        for (i in 0 until bars) {
            val height = dp(56f) * (0.22f + 0.7f * ((i * 7) % 11) / 10f)
            fill.color = withAlpha(
                if (i % 3 == 0) teal else purpleSoft,
                (if (i % 3 == 0) 0.55f else 0.25f) * a,
            )
            val bx = rect.left + dp(18f) + i * (lineW / 16f)
            canvas.drawRect(bx, base - height, bx + lineW / 26f, base, fill)
        }
    }

    // Keep the affordance honest: a tap skips, and completion is guaranteed.
    override fun onTouchEvent(event: android.view.MotionEvent): Boolean {
        if (event.action == android.view.MotionEvent.ACTION_DOWN) {
            finish()
            return true
        }
        return super.onTouchEvent(event)
    }
}
