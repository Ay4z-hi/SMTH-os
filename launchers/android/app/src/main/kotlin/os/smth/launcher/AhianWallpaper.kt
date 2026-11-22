package os.smth.launcher

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Shader
import android.view.View
import kotlin.math.sin

/**
 * The AHIAN flowing gradient.  One slow diagonal wave and one narrow light
 * band bend a deep purple → teal ramp.  Phase 1.0 is exactly one cycle, so the
 * reconstruction's final frame (phase 1) is the live wallpaper (phase 0).
 */
internal object AhianFlow {
    private const val PURPLE = 0xFF07080B.toInt()   // glass void (was wall purple)
    private const val TEAL = 0xFF141822.toInt()     // glass panel (was wall teal)
    private const val PURPLE_SOFT = 0xFF4FB0E0.toInt() // cold blue (was purple soft)
    private const val TEAL_BRIGHT = 0xFFF0A85A.toInt() // amber (was teal bright)

    fun color(u: Float, v: Float, phase: Float): Int {
        val x = u.coerceIn(0f, 1f)
        val y = v.coerceIn(0f, 1f)
        var wave = sin((x + y * 0.62f) * TAU + phase * TAU) * 0.075f
        wave += sin((x * 1.7f - y * 1.1f) * TAU - phase * TAU * 2f) * 0.035f
        val band = 0.5f + 0.5f * sin((x * 0.8f - y * 0.55f) * TAU - phase * TAU)
        var d = (x * 0.58f + y * 0.42f + wave).coerceIn(0f, 1f)
        d = d * d * (3f - 2f * d)
        val wall = blend(PURPLE, TEAL, d)
        val accent = blend(PURPLE_SOFT, TEAL_BRIGHT, (x * 0.7f + y * 0.3f).coerceIn(0f, 1f))
        return blend(wall, accent, 0.035f + 0.075f * band)
    }

    private const val TAU = 6.2831855f

    private fun blend(a: Int, b: Int, t: Float): Int {
        val k = t.coerceIn(0f, 1f)
        return Color.rgb(
            (Color.red(a) + (Color.red(b) - Color.red(a)) * k).toInt(),
            (Color.green(a) + (Color.green(b) - Color.green(a)) * k).toInt(),
            (Color.blue(a) + (Color.blue(b) - Color.blue(a)) * k).toInt(),
        )
    }
}

/**
 * Full-bleed live AHIAN wallpaper.  It keeps the same dot-matrix detail as the
 * reveal and can be frozen on the reveal's final phase so the fade uncovers an
 * identical frame, then resumed for a barely perceptible flow.
 */
internal class AhianWallpaperView(context: Context) : View(context) {
    private companion object {
        const val TAU = 6.2831855f
    }

    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val bandPaint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val dotPaint = Paint(Paint.ANTI_ALIAS_FLAG)
    private var phase = 0f
    private var flowing = false
    private val ticker = object : Runnable {
        override fun run() {
            if (!flowing) return
            phase = (phase + 0.0009f) % 1f
            invalidate()
            postDelayed(this, 40L)
        }
    }

    fun resumeFlow() {
        if (flowing || visibility != VISIBLE) return
        flowing = true
        removeCallbacks(ticker)
        postDelayed(ticker, 40L)
    }

    fun pauseFlow() {
        flowing = false
        removeCallbacks(ticker)
    }

    override fun onVisibilityChanged(changedView: View, visibility: Int) {
        super.onVisibilityChanged(changedView, visibility)
        if (visibility == VISIBLE) resumeFlow() else pauseFlow()
    }

    override fun onDetachedFromWindow() {
        pauseFlow()
        super.onDetachedFromWindow()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val w = width.toFloat()
        val h = height.toFloat()
        if (w <= 0f || h <= 0f) return
        val stops = IntArray(9) { i ->
            val k = i / 8f
            AhianFlow.color(k, k * 0.62f, phase)
        }
        paint.shader = LinearGradient(0f, 0f, w, h, stops, null, Shader.TileMode.CLAMP)
        canvas.drawRect(0f, 0f, w, h, paint)

        // Two wide translucent bands drifting across the sheet.
        for (i in 0 until 2) {
            val centre = h * (0.32f + 0.30f * i) + sin(phase * TAU + i * 2.1f) * h * 0.06f
            val tint = if (i == 0) 0x334FB0E0 else 0x22F0A85A
            bandPaint.shader = LinearGradient(
                0f, centre - h * 0.24f, w, centre + h * 0.24f,
                intArrayOf(Color.TRANSPARENT, tint, Color.TRANSPARENT),
                floatArrayOf(0f, 0.5f, 1f), Shader.TileMode.CLAMP,
            )
            canvas.drawRect(0f, 0f, w, h, bandPaint)
        }

        // Quiet dot matrix, aligned with the reveal's tile detail.
        val cols = 20
        val rows = maxOf(8, (cols * h / w).toInt())
        val sx = w / (cols + 1)
        val sy = h / (rows + 1)
        val radius = resources.displayMetrics.density * 0.9f
        dotPaint.color = 0x24E7ECF5
        for (r in 1..rows) {
            for (c in 1..cols) {
                canvas.drawCircle(sx * c, sy * r, radius, dotPaint)
            }
        }
    }
}
