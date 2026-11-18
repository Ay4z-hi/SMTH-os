package os.smth.launcher

import android.animation.Animator
import android.animation.AnimatorListenerAdapter
import android.animation.ValueAnimator
import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.res.ColorStateList
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.RippleDrawable
import android.net.Uri
import android.os.BatteryManager
import android.os.Bundle
import android.provider.Settings
import android.text.Editable
import android.text.TextWatcher
import android.view.Gravity
import android.view.PointerIcon
import android.view.View
import android.view.ViewGroup
import android.view.animation.DecelerateInterpolator
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.GridLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

// SMTH palette: black surfaces, white text, grey neutral, red accent.
private const val BLACK = 0xFF000000.toInt()
private const val WHITE = 0xFFFFFFFF.toInt()
private const val GREY = 0xFF8C8C8C.toInt()
private const val RED = 0xFFD71921.toInt()

/** A launchable app discovered on the device (never a hard-coded package list). */
private data class AppEntry(
    val label: String,
    val packageName: String,
    val icon: android.graphics.drawable.Drawable,
)

class MainActivity : Activity() {
    private lateinit var grid: GridLayout
    private lateinit var clock: TextView
    private lateinit var battery: TextView
    private lateinit var empty: TextView
    private lateinit var search: EditText
    private lateinit var dock: LinearLayout
    private var apps: List<AppEntry> = emptyList()
    private var typefaceMono: Typeface? = null
    private var typefaceDot: Typeface? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = BLACK
        window.navigationBarColor = BLACK
        typefaceMono = loadFont("space_mono")
        typefaceDot = loadFont("doto") ?: typefaceMono
        build()
        refreshApps()
        startClock()
    }

    override fun onResume() {
        super.onResume()
        // Installed or removed apps must show up without restarting the launcher.
        refreshApps()
    }

    /** The launcher never shows a mouse pointer, even when a mouse is attached. */
    private fun suppressPointer(view: View) {
        view.pointerIcon = PointerIcon.getSystemIcon(this, PointerIcon.TYPE_NULL)
        view.setOnHoverListener { v, _ ->
            v.pointerIcon = PointerIcon.getSystemIcon(this, PointerIcon.TYPE_NULL)
            true
        }
    }

    private fun loadFont(name: String): Typeface? = try {
        val id = resources.getIdentifier(name, "font", packageName)
        if (id == 0) null else resources.getFont(id)
    } catch (e: Exception) {
        null
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    private fun panel(fill: Int, stroke: Int, radius: Int = 4): GradientDrawable =
        GradientDrawable().apply {
            setColor(fill)
            cornerRadius = dp(radius).toFloat()
            if (stroke != 0) setStroke(dp(1), stroke)
        }

    private fun build() {
        val root = DotField(this).apply { setBackgroundColor(BLACK) }
        val column = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(18), dp(20), dp(10))
        }

        // ---- header: brand, battery, live clock ----
        val header = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        header.addView(TextView(this).apply {
            text = "SMTH"
            setTextColor(WHITE)
            textSize = 22f
            typeface = Typeface.create(typefaceDot ?: Typeface.DEFAULT, Typeface.BOLD)
            letterSpacing = 0.22f
        }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        battery = TextView(this).apply {
            setTextColor(GREY)
            textSize = 11f
            typeface = typefaceMono
            setPadding(0, 0, dp(12), 0)
        }
        clock = TextView(this).apply {
            setTextColor(RED)
            textSize = 15f
            typeface = typefaceMono
        }
        header.addView(battery)
        header.addView(clock)
        column.addView(header)

        column.addView(TextView(this).apply {
            text = SimpleDateFormat("EEEE, d MMMM", Locale.getDefault()).format(Date())
            setTextColor(GREY)
            textSize = 11f
            typeface = typefaceMono
            setPadding(0, dp(4), 0, dp(18))
        })

        // ---- search ----
        search = EditText(this).apply {
            hint = "Search apps"
            setHintTextColor(GREY)
            setTextColor(WHITE)
            textSize = 14f
            typeface = typefaceMono
            setSingleLine(true)
            setPadding(dp(14), dp(10), dp(14), dp(10))
            background = panel(BLACK, GREY)
            setOnFocusChangeListener { v, focused ->
                v.background = panel(BLACK, if (focused) RED else GREY)
            }
            addTextChangedListener(object : TextWatcher {
                override fun beforeTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
                override fun onTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {
                    if (::grid.isInitialized) render()
                }
                override fun afterTextChanged(s: Editable?) {}
            })
        }
        column.addView(search, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(46)))
        suppressPointer(search)

        column.addView(TextView(this).apply {
            text = "YOUR APPS"
            setTextColor(RED)
            textSize = 10f
            typeface = typefaceMono
            letterSpacing = 0.18f
            setPadding(0, dp(18), 0, dp(10))
        })

        // ---- app grid: rebuilt on every filter change, so no invisible gaps ----
        grid = GridLayout(this).apply { columnCount = columnsForWidth() }
        val scroll = ScrollView(this).apply { isFillViewport = true }
        scroll.addView(grid, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        column.addView(scroll, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))

        empty = TextView(this).apply {
            text = "No apps match"
            setTextColor(GREY)
            textSize = 12f
            typeface = typefaceMono
            gravity = Gravity.CENTER
            visibility = View.GONE
        }
        column.addView(empty)

        // ---- dock: four real shortcuts, resolved at runtime ----
        dock = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            background = panel(BLACK, GREY, 18)
            setPadding(dp(10), dp(8), dp(10), dp(8))
        }
        column.addView(dock, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply {
            topMargin = dp(8)
        })

        // ---- quick actions ----
        val actions = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(0, dp(8), 0, 0)
        }
        actions.addView(actionButton("SETTINGS") { startActivitySafely(Intent(Settings.ACTION_SETTINGS)) },
            LinearLayout.LayoutParams(0, dp(42), 1f))
        actions.addView(actionButton("WALLPAPER") { startActivitySafely(Intent(Intent.ACTION_SET_WALLPAPER)) },
            LinearLayout.LayoutParams(0, dp(42), 1f))
        column.addView(actions)

        root.addView(column)
        if (animationsEnabled()) {
            root.addView(
                ConstructionView(this, typefaceDot, typefaceMono),
                FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.MATCH_PARENT,
                ),
            )
        }
        suppressPointer(root)
        setContentView(root)
    }

    private fun animationsEnabled(): Boolean = try {
        Settings.Global.getFloat(
            contentResolver,
            Settings.Global.ANIMATOR_DURATION_SCALE,
            1f,
        ) != 0f
    } catch (e: Exception) {
        true
    }

    private fun columnsForWidth(): Int = when {
        resources.configuration.screenWidthDp >= 900 -> 6
        resources.configuration.screenWidthDp >= 600 -> 5
        else -> 4
    }

    private fun actionButton(label: String, onClick: () -> Unit): TextView =
        TextView(this).apply {
            text = label
            setTextColor(WHITE)
            textSize = 10f
            typeface = typefaceMono
            letterSpacing = 0.14f
            gravity = Gravity.CENTER
            isClickable = true
            isFocusable = true
            background = panel(BLACK, GREY)
            setOnClickListener { onClick() }
        }

    private fun dockButton(entry: AppEntry): LinearLayout =
        LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            isClickable = true
            isFocusable = true
            addView(ImageView(this@MainActivity).apply {
                setImageDrawable(entry.icon)
                scaleType = ImageView.ScaleType.FIT_CENTER
            }, LinearLayout.LayoutParams(dp(24), dp(24)))
            addView(TextView(this@MainActivity).apply {
                text = entry.label
                setTextColor(WHITE)
                textSize = 9f
                maxLines = 1
                typeface = typefaceMono
                gravity = Gravity.CENTER
            })
            setOnClickListener { launch(entry) }
            setOnLongClickListener { openInfo(entry); true }
        }

    private fun refreshApps() {
        val pm = packageManager
        val intent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        apps = pm.queryIntentActivities(intent, 0)
            .asSequence()
            .filter { it.activityInfo.packageName != packageName }
            .mapNotNull { info ->
                try {
                    AppEntry(
                        label = info.loadLabel(pm).toString(),
                        packageName = info.activityInfo.packageName,
                        icon = info.loadIcon(pm),
                    )
                } catch (e: Exception) {
                    null
                }
            }
            .distinctBy { it.packageName }
            .sortedBy { it.label.lowercase(Locale.getDefault()) }
            .toList()
        render()
        rebuildDock()
    }

    private fun rebuildDock() {
        dock.removeAllViews()
        var added = 0
        for (pkg in DOCK_PACKAGES) {
            val entry = apps.firstOrNull { it.packageName == pkg } ?: continue
            dock.addView(dockButton(entry), LinearLayout.LayoutParams(0, dp(52), 1f))
            added++
        }
        if (added == 0) {
            dock.addView(TextView(this).apply {
                text = "Open the app grid to begin"
                setTextColor(GREY)
                textSize = 10f
                typeface = typefaceMono
                gravity = Gravity.CENTER
            }, LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, dp(52)))
        }
    }

    private fun render() {
        grid.removeAllViews()
        val query = search.text?.toString()?.trim()?.lowercase(Locale.getDefault()) ?: ""
        val shown = if (query.isEmpty()) apps else apps.filter { it.label.lowercase(Locale.getDefault()).contains(query) }
        grid.columnCount = columnsForWidth()
        shown.forEachIndexed { index, entry ->
            val params = GridLayout.LayoutParams().apply {
                width = 0
                height = dp(88)
                columnSpec = GridLayout.spec(index % grid.columnCount, 1f)
                setMargins(dp(4), dp(4), dp(4), dp(4))
            }
            grid.addView(appTile(entry), params)
        }
        empty.visibility = if (shown.isEmpty()) View.VISIBLE else View.GONE
    }

    private fun appTile(entry: AppEntry): LinearLayout =
        LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(dp(6), dp(10), dp(6), dp(8))
            background = RippleDrawable(
                ColorStateList.valueOf(GREY),
                panel(BLACK, GREY),
                GradientDrawable().apply { setColor(WHITE); cornerRadius = dp(4).toFloat() },
            )
            isClickable = true
            isFocusable = true
            addView(ImageView(this@MainActivity).apply {
                setImageDrawable(entry.icon)
                scaleType = ImageView.ScaleType.FIT_CENTER
            }, LinearLayout.LayoutParams(dp(30), dp(30)))
            addView(TextView(this@MainActivity).apply {
                text = entry.label
                setTextColor(WHITE)
                textSize = 10f
                maxLines = 2
                gravity = Gravity.CENTER
                setPadding(0, dp(6), 0, 0)
                typeface = typefaceMono
            })
            setOnClickListener { launch(entry) }
            setOnLongClickListener { openInfo(entry); true }
            suppressPointer(this)
        }

    private fun launch(entry: AppEntry) {
        val intent = packageManager.getLaunchIntentForPackage(entry.packageName)
        if (intent == null) {
            Toast.makeText(this, "${entry.label} cannot be launched", Toast.LENGTH_SHORT).show()
            return
        }
        startActivitySafely(intent)
    }

    private fun openInfo(entry: AppEntry) {
        startActivitySafely(
            Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS)
                .setData(Uri.parse("package:${entry.packageName}"))
        )
    }

    private fun startActivitySafely(intent: Intent) {
        try {
            startActivity(intent)
        } catch (e: ActivityNotFoundException) {
            Toast.makeText(this, "Not available on this device", Toast.LENGTH_SHORT).show()
        } catch (e: SecurityException) {
            Toast.makeText(this, "Not permitted on this device", Toast.LENGTH_SHORT).show()
        }
    }

    private fun startClock() {
        val tick = object : Runnable {
            override fun run() {
                clock.text = SimpleDateFormat("HH:mm", Locale.getDefault()).format(Date())
                battery.text = readBattery()
                clock.postDelayed(this, 15_000)
            }
        }
        clock.post(tick)
    }

    private fun readBattery(): String {
        val status = registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val level = status?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
        return if (level >= 0) "$level%" else ""
    }

    private companion object {
        // Preferred dock entries; only installed apps are shown.
        val DOCK_PACKAGES = listOf(
            "com.google.android.dialer",
            "com.google.android.apps.messaging",
            "com.android.chrome",
            "com.android.camera2",
        )
    }
}

/** Flat dot-grid background, drawn rather than shipped as an image. */
private class DotField(context: android.content.Context) : FrameLayout(context) {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)

    override fun dispatchDraw(canvas: Canvas) {
        val step = 22f * resources.displayMetrics.density
        val radius = 1.1f * resources.displayMetrics.density
        var y = step
        var row = 0
        while (y < height) {
            var x = step
            var col = 0
            while (x < width) {
                paint.color = if ((row + col) % 7 == 0) 0x33D71921 else 0x228C8C8C
                canvas.drawCircle(x, y, radius, paint)
                x += step
                col++
            }
            y += step
            row++
        }
        super.dispatchDraw(canvas)
    }
}

/**
 * Android adaptation of the SMTH construction intro.  It is a real animated
 * View over the already-built launcher: cursors, selection boxes and panels are
 * drawn each frame, then the overlay fades to reveal the live app grid.  Tapping
 * anywhere skips it.  It is also skipped when the system animator scale is zero.
 */
private class ConstructionView(
    context: Context,
    private val dot: Typeface?,
    private val mono: Typeface?,
) : View(context) {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val logoBitmap: Bitmap? = try {
        BitmapFactory.decodeResource(resources, R.drawable.ic_launcher_smth)
    } catch (_: Exception) { null }
    private val colours = intArrayOf(
        0xFFD71921.toInt(), 0xFF2F6BFF.toInt(), 0xFF00C2A8.toInt(),
        0xFF7C4DFF.toInt(), 0xFFFFFFFF.toInt(), 0xFFFFAD29.toInt(),
    )
    private val animator = ValueAnimator.ofFloat(0f, 1f)
    private var progress = 0f
    private var closed = false

    private data class Box(
        val rect: RectF,
        val start: Float,
        val colour: Int,
        val label: String,
    )

    init {
        setBackgroundColor(BLACK)
        isClickable = true
        contentDescription = "SMTH startup construction; tap to skip"
        setOnClickListener { finishIntro() }
        animator.duration = 5_600
        animator.interpolator = DecelerateInterpolator()
        animator.addUpdateListener { animation ->
            progress = animation.animatedValue as Float
            alpha = if (progress > 0.90f) (1f - progress) / 0.10f else 1f
            invalidate()
        }
        animator.addListener(object : AnimatorListenerAdapter() {
            override fun onAnimationEnd(animation: Animator) {
                if (!closed) finishIntro()
            }
        })
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        if (!animator.isStarted) animator.start()
    }

    override fun onDetachedFromWindow() {
        animator.cancel()
        super.onDetachedFromWindow()
    }

    private fun finishIntro() {
        if (closed) return
        closed = true
        animator.cancel()
        animate().alpha(0f).setDuration(300).withEndAction {
            (parent as? ViewGroup)?.removeView(this)
        }.start()
    }

    private fun dp(value: Float): Float = value * resources.displayMetrics.density

    private fun lerp(a: Float, b: Float, t: Float): Float = a + (b - a) * t

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val w = width.toFloat()
        val h = height.toFloat()
        if (w <= 0f || h <= 0f) return
        val p = progress.coerceIn(0f, 1f)
        canvas.drawColor(BLACK)
        drawDotField(canvas, w, h)
        drawLogo(canvas, w, h, p)
        if (p >= 0.14f) {
            drawPanels(canvas, w, h, p)
            drawBoxes(canvas, w, h, p)
        }
        if (p in 0.12f..0.88f) drawCursors(canvas, w, h, p)
        paint.style = Paint.Style.FILL
        paint.typeface = mono
        paint.textSize = dp(8f)
        paint.textAlign = Paint.Align.RIGHT
        paint.color = GREY
        canvas.drawText("TAP TO SKIP", w - dp(14f), h - dp(12f), paint)
    }

    private fun drawDotField(canvas: Canvas, w: Float, h: Float) {
        paint.style = Paint.Style.FILL
        val step = dp(26f)
        var y = step
        var row = 0
        while (y < h) {
            var x = step
            var col = 0
            while (x < w) {
                paint.color = if ((row + col) % 11 == 0) 0x22D71921 else 0x188C8C8C
                canvas.drawCircle(x, y, dp(1f), paint)
                x += step
                col++
            }
            y += step
            row++
        }
    }

    private fun drawLogo(canvas: Canvas, w: Float, h: Float, p: Float) {
        val fade = when {
            p < 0.10f -> p / 0.10f
            p < 0.16f -> 1f
            p < 0.22f -> 1f - (p - 0.16f) / 0.06f
            else -> 0f
        }
        if (fade <= 0f) return
        val bmp = logoBitmap
        if (bmp != null) {
            val size = dp(96f)
            val dst = RectF(w / 2f - size / 2f, h / 2f - size / 2f,
                w / 2f + size / 2f, h / 2f + size / 2f)
            paint.alpha = (fade * 255).toInt()
            canvas.drawBitmap(bmp, null, dst, paint)
        } else {
            paint.style = Paint.Style.FILL
            paint.typeface = dot ?: Typeface.DEFAULT
            paint.textSize = dp(44f)
            paint.textAlign = Paint.Align.CENTER
            paint.color = Color.argb((fade * 255).toInt(), 255, 255, 255)
            canvas.drawText("SMTH", w / 2f, h / 2f - dp(4f), paint)
        }
        // Logo only: no text or extra marks during the logo phase.
    }

    private fun panel(canvas: Canvas, rect: RectF, q: Float, accent: Int = GREY) {
        if (q <= 0f) return
        val visible = RectF(rect.left, rect.top, rect.left + rect.width() * q.coerceIn(0f, 1f), rect.bottom)
        paint.style = Paint.Style.FILL
        paint.color = BLACK
        canvas.drawRect(visible, paint)
        paint.style = Paint.Style.STROKE
        paint.strokeWidth = dp(1f)
        paint.color = accent
        canvas.drawRoundRect(visible, dp(3f), dp(3f), paint)
    }

    private fun drawPanels(canvas: Canvas, w: Float, h: Float, p: Float) {
        panel(canvas, RectF(w * .05f, h * .03f, w * .95f, h * .095f),
            (p - 0.18f) / 0.18f)
        paint.style = Paint.Style.FILL
        paint.typeface = dot ?: Typeface.DEFAULT
        paint.textSize = dp(14f)
        paint.textAlign = Paint.Align.LEFT
        paint.color = WHITE
        if (p > 0.24f) canvas.drawText("SMTH", w * .075f, h * .073f, paint)
        paint.typeface = mono
        paint.textSize = dp(10f)
        paint.textAlign = Paint.Align.RIGHT
        paint.color = RED
        if (p > 0.24f) canvas.drawText("00:00", w * .925f, h * .073f, paint)
        panel(canvas, RectF(w * .05f, h * .15f, w * .95f, h * .215f),
            (p - 0.22f) / 0.18f)
        panel(canvas, RectF(w * .05f, h * .26f, w * .95f, h * .73f),
            (p - 0.28f) / 0.26f)
        for (row in 0..1) {
            for (col in 0..3) {
                val start = 0.31f + (row * 4 + col) * 0.018f
                panel(canvas, RectF(
                    w * (0.075f + col * 0.215f), h * (0.285f + row * 0.21f),
                    w * (0.255f + col * 0.215f), h * (0.445f + row * 0.21f),
                ), (p - start) / 0.16f, 0xFF00C2A8.toInt())
            }
        }
        panel(canvas, RectF(w * .30f, h * .82f, w * .70f, h * .895f),
            (p - 0.38f) / 0.18f, RED)
    }

    private fun drawBoxes(canvas: Canvas, w: Float, h: Float, p: Float) {
        if (p >= 0.86f) return
        val boxes = arrayOf(
            Box(RectF(w * .05f, h * .025f, w * .95f, h * .10f), 0.16f, 0xFF2F6BFF.toInt(), "TASKBAR"),
            Box(RectF(w * .05f, h * .14f, w * .95f, h * .225f), 0.23f, 0xFF00C2A8.toInt(), "SEARCH"),
            Box(RectF(w * .05f, h * .25f, w * .95f, h * .74f), 0.30f, 0xFF7C4DFF.toInt(), "APP GRID"),
            Box(RectF(w * .26f, h * .815f, w * .74f, h * .91f), 0.38f, RED, "DOCK"),
        )
        for (box in boxes) {
            drawSelection(canvas, box, p)
        }
    }

    private fun drawSelection(canvas: Canvas, box: Box, p: Float) {
        val q = ((p - box.start) / 0.16f).coerceIn(0f, 1f)
        if (q <= 0f) return
        val r = box.rect
        paint.style = Paint.Style.STROKE
        paint.strokeWidth = dp(1.4f)
        paint.color = box.colour
        canvas.drawRect(r, paint)
        val perimeter = 2f * (r.width() + r.height())
        var drawn = perimeter * q
        fun segment(x1: Float, y1: Float, x2: Float, y2: Float) {
            if (drawn <= 0f) return
            val length = kotlin.math.abs(x2 - x1) + kotlin.math.abs(y2 - y1)
            val f = (drawn / length).coerceAtMost(1f)
            canvas.drawLine(x1, y1, x1 + (x2 - x1) * f, y1 + (y2 - y1) * f, paint)
            drawn -= length
        }
        segment(r.left, r.top, r.right, r.top)
        segment(r.right, r.top, r.right, r.bottom)
        segment(r.right, r.bottom, r.left, r.bottom)
        segment(r.left, r.bottom, r.left, r.top)
        paint.style = Paint.Style.FILL
        paint.typeface = mono
        paint.textSize = dp(8f)
        paint.textAlign = Paint.Align.LEFT
        paint.color = box.colour
        canvas.drawText(box.label, r.left, (r.top - dp(4f)).coerceAtLeast(dp(9f)), paint)
    }

    private fun drawCursors(canvas: Canvas, w: Float, h: Float, p: Float) {
        val paths = arrayOf(
            floatArrayOf(0.08f, 0.02f, 0.24f, 0.06f, 0.44f, 0.16f, 0.62f, 0.30f),
            floatArrayOf(0.55f, 0.00f, 0.40f, 0.12f, 0.55f, 0.34f, 0.78f, 0.26f),
            floatArrayOf(1.00f, 0.18f, 0.78f, 0.24f, 0.62f, 0.44f, 0.38f, 0.36f),
            floatArrayOf(0.02f, 0.58f, 0.20f, 0.52f, 0.34f, 0.68f, 0.58f, 0.60f),
            floatArrayOf(0.88f, 0.90f, 0.68f, 0.76f, 0.46f, 0.86f, 0.24f, 0.78f),
        )
        val labels = arrayOf("ARCH", "UI", "LAYOUT", "TYPE", "SYNC")
        for (i in paths.indices) {
            val q = ((p - 0.12f - i * 0.025f) / 0.72f).coerceIn(0f, 1f)
            val path = paths[i]
            val seg = q * (path.size / 2 - 1)
            val index = seg.toInt().coerceAtMost(path.size / 2 - 2)
            val local = seg - index
            val x = lerp(path[index * 2], path[(index + 1) * 2], local) * w
            val y = lerp(path[index * 2 + 1], path[(index + 1) * 2 + 1], local) * h
            paint.style = Paint.Style.FILL
            paint.color = colours[i]
            val arrow = Path().apply {
                moveTo(x, y)
                lineTo(x, y + dp(17f))
                lineTo(x + dp(4.5f), y + dp(13f))
                lineTo(x + dp(7.2f), y + dp(19f))
                lineTo(x + dp(10f), y + dp(17.8f))
                lineTo(x + dp(7.2f), y + dp(11.6f))
                lineTo(x + dp(13f), y + dp(11.6f))
                close()
            }
            canvas.drawPath(arrow, paint)
            paint.strokeWidth = dp(1f)
            paint.style = Paint.Style.STROKE
            paint.color = BLACK
            canvas.drawPath(arrow, paint)
            paint.style = Paint.Style.FILL
            paint.typeface = mono
            paint.textSize = dp(7f)
            paint.textAlign = Paint.Align.LEFT
            paint.color = colours[i]
            canvas.drawText(labels[i], x + dp(16f), y + dp(15f), paint)
        }
    }
}
