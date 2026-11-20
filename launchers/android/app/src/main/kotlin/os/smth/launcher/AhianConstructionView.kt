package os.smth.launcher

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.LinearGradient
import android.graphics.Shader
import android.view.View
import android.view.animation.LinearInterpolator
import kotlin.math.sin

/**
 * AHIAN desktop reconstruction: a real View (not a video) that draws the
 * purple/teal desktop being assembled by several independent cursors, then
 * fades out. Honours Reduce Motion by skipping (caller checks animator scale).
 */
class AhianConstructionView(context: Context) : View(context) {
    private val density = context.resources.displayMetrics.density
    private fun dp(v: Float) = v * density

    private val purple = Color.parseColor("#7C4DFF")
    private val teal = Color.parseColor("#00C2A8")
    private val softPurple = Color.parseColor("#9E75FF")
    private val brightTeal = Color.parseColor("#33E5CC")
    private val violet = Color.parseColor("#5738A0")
    private val white = Color.WHITE

    private val cursorColors = intArrayOf(purple, teal, softPurple, brightTeal, violet, brightTeal, softPurple)

    // Normalized paths (x,y in 0..1) for 7 cursors, entering from different edges.
    private val paths = arrayOf(
        arrayOf(Pair(0.05f, 0.0f), Pair(0.38f, 0.55f), Pair(0.02f, 0.02f), Pair(0.35f, 0.25f), Pair(0.85f, 0.8f), Pair(1.06f, 0.94f)),
        arrayOf(Pair(0.52f, -0.05f), Pair(0.5f, 0.08f), Pair(0.08f, 0.3f), Pair(0.9f, 0.62f), Pair(0.7f, 0.5f), Pair(0.52f, -0.08f)),
        arrayOf(Pair(1.04f, 0.18f), Pair(0.95f, 0.35f), Pair(0.7f, 0.25f), Pair(0.5f, 0.5f), Pair(0.3f, 0.55f), Pair(1.06f, 0.48f)),
        arrayOf(Pair(-0.04f, 0.45f), Pair(0.85f, 0.25f), Pair(0.25f, 0.7f), Pair(0.2f, 0.5f), Pair(0.55f, 0.85f), Pair(-0.06f, 0.92f)),
        arrayOf(Pair(0.7f, -0.04f), Pair(0.5f, 0.4f), Pair(0.45f, 0.5f), Pair(0.35f, 0.5f), Pair(0.2f, 0.85f), Pair(0.72f, 1.06f)),
        arrayOf(Pair(-0.04f, 0.9f), Pair(0.5f, 0.75f), Pair(0.55f, 0.4f), Pair(0.18f, 0.75f), Pair(0.48f, 0.35f), Pair(-0.06f, 0.36f)),
        arrayOf(Pair(1.04f, 0.95f), Pair(0.7f, 0.5f), Pair(0.9f, 0.5f), Pair(0.7f, 0.2f), Pair(0.55f, -0.05f))
    )

    private val cursorPaint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val boxPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE; strokeWidth = dp(1.5f) }
    private val fillPaint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val textPaint = Paint(Paint.ANTI_ALIAS_FLAG)

    private var progress = 0f
    private var animator: ValueAnimator? = null

    init {
        setBackgroundColor(Color.BLACK)
        textPaint.textSize = dp(10f)
        textPaint.typeface = android.graphics.Typeface.MONOSPACE
    }

    fun start(onProgress: ((Float) -> Unit)? = null, onComplete: (() -> Unit)? = null) {
        animator?.cancel()
        val a = ValueAnimator.ofFloat(0f, 1f).apply {
            duration = 10000
            interpolator = LinearInterpolator()
            addUpdateListener { anim ->
                progress = anim.animatedValue as Float
                // Let MainActivity reveal its actual desktop children in step
                // with the construction cursors.
                onProgress?.invoke(progress)
                alpha = if (progress > 0.86f) ((1f - progress) / 0.14f).coerceIn(0f, 1f) else 1f
                invalidate()
            }
            addListener(object : android.animation.AnimatorListenerAdapter() {
                override fun onAnimationEnd(animation: android.animation.Animator) {
                    onComplete?.invoke()
                }
            })
        }
        animator = a
        a.start()
    }

    fun stop() {
        animator?.cancel()
        animator = null
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val w = width.toFloat()
        val h = height.toFloat()
        if (w <= 0 || h <= 0) return

        // dark base
        canvas.drawColor(Color.BLACK)

        // Reveal the actual AHIAN purple-to-teal wallpaper before assembling UI.
        val wallAlpha = (progress * 1.35f).coerceIn(0f, 1f)
        fillPaint.shader = LinearGradient(0f, 0f, w, h, purple, teal, Shader.TileMode.CLAMP)
        fillPaint.alpha = (wallAlpha * 210f).toInt().coerceIn(0, 210)
        canvas.drawRect(0f, 0f, w, h, fillPaint)
        fillPaint.shader = null
        fillPaint.alpha = 255
        val spacing = (minOf(w, h) / 24f).coerceAtLeast(20f)
        fillPaint.style = Paint.Style.FILL
        var y = spacing
        while (y < h - spacing) {
            var x = spacing
            while (x < w - spacing) {
                val hot = ((x / spacing).toInt() + (y / spacing).toInt()) % 9 == 0
                fillPaint.color = if (hot) adjustAlpha(teal, wallAlpha * 0.6f) else adjustAlpha(purple, wallAlpha * 0.08f)
                canvas.drawCircle(x, y, dp(1f), fillPaint)
                x += spacing
            }
            y += spacing
        }

        // selection boxes
        if (progress > 0.18f) {
            val boxes = listOf(
                Triple(0.02f, 0.88f, 0.96f to 0.08f), // status-ish bottom
            )
            // Draw a few guides
            val guideAlpha = (((0.88f - progress) / 0.14f).coerceIn(0f, 1f) * ((progress - 0.18f) / 0.4f).coerceIn(0f, 1f))
            boxPaint.color = adjustAlpha(teal, guideAlpha)
            // taskbar guide
            canvas.drawRect(dp(8f), h - dp(56f), w - dp(8f), h - dp(8f), boxPaint)
            // window guide
            val p2 = ((progress - 0.28f) / 0.4f).coerceIn(0f, 1f) * ((0.88f - progress) / 0.14f).coerceIn(0f, 1f)
            if (p2 > 0) {
                boxPaint.color = adjustAlpha(purple, p2)
                canvas.drawRect(w * 0.37f, h * 0.17f, w * 0.37f + w * 0.56f * p2, h * 0.17f + h * 0.58f * p2, boxPaint)
            }
            val p3 = ((progress - 0.22f) / 0.4f).coerceIn(0f, 1f) * ((0.88f - progress) / 0.14f).coerceIn(0f, 1f)
            if (p3 > 0) {
                boxPaint.color = adjustAlpha(teal, p3)
                canvas.drawRect(dp(44f), dp(44f), dp(44f) + (w * 0.32f) * p3, dp(44f) + (h - 210f) * p3, boxPaint)
            }
        }

        // panels wipe (simple rectangles)
        if (progress > 0.3f) {
            val pp = ((progress - 0.3f) / 0.5f).coerceIn(0f, 1f)
            fillPaint.style = Paint.Style.FILL
            fillPaint.color = adjustAlpha(Color.parseColor("#120A24"), 0.85f * pp)
            // window panel
            canvas.drawRoundRect(w * 0.37f, h * 0.17f, w * 0.37f + w * 0.56f, h * 0.17f + h * 0.58f, dp(4f), dp(4f), fillPaint)
            // grid panel
            canvas.drawRoundRect(dp(44f), dp(44f), dp(44f) + w * 0.32f, dp(44f) + h - 210f, dp(4f), dp(4f), fillPaint)
            // taskbar
            canvas.drawRoundRect(dp(8f), h - dp(56f), w - dp(8f), h - dp(8f), dp(12f), dp(12f), fillPaint)

            // The window is built as a real-looking app surface: titlebar,
            // controls, content cards and a small live chart appear in sequence.
            if (pp > 0.12f) {
                val reveal = ((pp - 0.12f) / 0.58f).coerceIn(0f, 1f)
                val left = w * 0.37f
                val top = h * 0.17f
                val right = left + w * 0.56f
                val bottom = top + h * 0.58f
                fillPaint.color = adjustAlpha(Color.parseColor("#21133D"), reveal)
                canvas.drawRoundRect(left, top, right, top + dp(34f), dp(7f), dp(7f), fillPaint)
                textPaint.color = adjustAlpha(white, reveal)
                textPaint.textSize = dp(9f)
                canvas.drawText("AHIAN / SPATIAL DESKTOP", left + dp(12f), top + dp(22f), textPaint)
                for (i in 0..2) {
                    fillPaint.color = adjustAlpha(if (i == 0) teal else purple, reveal)
                    canvas.drawCircle(right - dp(42f) + i * dp(13f), top + dp(17f), dp(3f), fillPaint)
                }
                // Content cards grow from left to right.
                for (i in 0..2) {
                    val cardTop = top + dp(48f) + i * dp(40f)
                    val cardRight = left + dp(110f) * reveal
                    fillPaint.color = adjustAlpha(Color.parseColor("#30234C"), reveal * 0.9f)
                    canvas.drawRoundRect(left + dp(12f), cardTop, cardRight, cardTop + dp(29f),
                        dp(5f), dp(5f), fillPaint)
                    if (reveal > 0.35f) {
                        fillPaint.color = adjustAlpha(if (i % 2 == 0) teal else softPurple, reveal)
                        canvas.drawCircle(left + dp(24f), cardTop + dp(14f), dp(4f), fillPaint)
                        fillPaint.color = adjustAlpha(white, reveal * 0.45f)
                        canvas.drawRect(left + dp(36f), cardTop + dp(10f),
                            left + dp(82f), cardTop + dp(12f), fillPaint)
                    }
                }
                // Spatial widget on the right, with a chart trace.
                if (reveal > 0.42f) {
                    val wx = left + w * 0.30f
                    val wy = top + dp(48f)
                    fillPaint.color = adjustAlpha(Color.parseColor("#17102B"), reveal)
                    canvas.drawRoundRect(wx, wy, right - dp(12f), bottom - dp(12f),
                        dp(8f), dp(8f), fillPaint)
                    boxPaint.color = adjustAlpha(teal, reveal)
                    val chart = Path().apply {
                        moveTo(wx + dp(10f), wy + dp(62f))
                        lineTo(wx + dp(30f), wy + dp(48f))
                        lineTo(wx + dp(48f), wy + dp(54f))
                        lineTo(wx + dp(70f), wy + dp(24f))
                        lineTo(wx + dp(88f), wy + dp(34f))
                    }
                    canvas.drawPath(chart, boxPaint)
                }
            }

            // App icons are placed individually by the moving cursors.
            if (pp > 0.22f) {
                val reveal = ((pp - 0.22f) / 0.52f).coerceIn(0f, 1f)
                for (i in 0..5) {
                    val col = i % 3
                    val row = i / 3
                    val x = dp(54f) + col * dp(48f)
                    val y = dp(62f) + row * dp(54f)
                    fillPaint.color = adjustAlpha(if (i % 2 == 0) purple else teal, reveal)
                    canvas.drawRoundRect(x, y, x + dp(24f), y + dp(24f),
                        dp(6f), dp(6f), fillPaint)
                    fillPaint.color = adjustAlpha(white, reveal * 0.8f)
                    canvas.drawCircle(x + dp(12f), y + dp(12f), dp(3f), fillPaint)
                }
            }

            // Taskbar controls and pinned app dots are assembled last.
            if (pp > 0.5f) {
                val reveal = ((pp - 0.5f) / 0.3f).coerceIn(0f, 1f)
                for (i in 0..5) {
                    fillPaint.color = adjustAlpha(if (i % 2 == 0) purple else teal, reveal)
                    canvas.drawRoundRect(dp(24f) + i * dp(25f), h - dp(42f),
                        dp(38f) + i * dp(25f), h - dp(24f), dp(4f), dp(4f), fillPaint)
                }
            }
        }

        // cursors
        val t = progress
        for (i in paths.indices) {
            val pts = paths[i]
            val start = 0.08f + i * 0.02f
            val end = 0.82f + i * 0.02f
            if (t < start || t > end + 0.08f) continue
            val p = ((t - start) / (end - start)).coerceIn(0f, 1f)
            val segCount = pts.size - 1
            val seg = (p * segCount).toInt().coerceIn(0, segCount - 1)
            val local = (p * segCount - seg).coerceIn(0f, 1f)
            val ax = pts[seg].first * w
            val ay = pts[seg].second * h
            val bx = pts[seg + 1].first * w
            val by = pts[seg + 1].second * h
            val x = ax + (bx - ax) * (1 - (1 - local) * (1 - local) * (1 - local))
            val y = ay + (by - ay) * (1 - (1 - local) * (1 - local) * (1 - local))
            val wobble = (sin(p * Math.PI * 2 * 2.2 + i * 0.37) * 3.2).toFloat()
            val cx = x + wobble
            val cy = y - wobble * 0.6f
            val alpha = ( (if (t < start + 0.05f) (t - start) / 0.05f else 1f) *
                          (if (t > end - 0.08f) (1f - (t - (end - 0.08f)) / 0.2f) else 1f) ).coerceIn(0f, 1f)
            // trail
            for (k in 0 until 3) {
                val ta = (alpha * (0.20f - k * 0.045f)).coerceAtLeast(0f)
                fillPaint.color = adjustAlpha(cursorColors[i], ta)
                canvas.drawCircle(cx - k * 4f, cy - k * 3f, dp(4f - k * 0.7f), fillPaint)
            }
            // cursor shape
            val path = Path()
            path.moveTo(cx, cy)
            path.lineTo(cx, cy + dp(22f))
            path.lineTo(cx + dp(5.8f), cy + dp(16.4f))
            path.lineTo(cx + dp(9.2f), cy + dp(24f))
            path.lineTo(cx + dp(12.2f), cy + dp(22f))
            path.lineTo(cx + dp(9.0f), cy + dp(15f))
            path.lineTo(cx + dp(17f), cy + dp(15f))
            path.close()
            cursorPaint.style = Paint.Style.STROKE
            cursorPaint.strokeWidth = dp(1.2f)
            cursorPaint.color = adjustAlpha(Color.WHITE, alpha * 0.9f)
            canvas.drawPath(path, cursorPaint)
            cursorPaint.style = Paint.Style.FILL
            cursorPaint.color = adjustAlpha(Color.BLACK, alpha * 0.92f)
            canvas.drawPath(path, cursorPaint)
            cursorPaint.color = adjustAlpha(cursorColors[i], alpha)
            canvas.drawPath(path, cursorPaint)
            textPaint.color = adjustAlpha(cursorColors[i], alpha)
            textPaint.setShadowLayer(dp(3f), 0f, dp(1f), Color.BLACK)
            canvas.drawText(arrayOf("AHIAN", "PURPLE", "TEAL", "SPATIAL", "DEPTH", "PANEL", "BUILD")[i],
                cx + dp(21f), cy + dp(22f), textPaint)
            textPaint.clearShadowLayer()
        }

        // click ripple occasionally
        // settle: outlines fade
        if (progress > 0.82f) {
            // nothing extra
        }
    }

    private fun adjustAlpha(color: Int, alpha: Float): Int {
        val a = (Color.alpha(color) * alpha).toInt().coerceIn(0, 255)
        return (color and 0x00FFFFFF) or (a shl 24)
    }

    private fun minOf(a: Float, b: Float) = if (a < b) a else b
}
