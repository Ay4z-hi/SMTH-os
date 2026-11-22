package os.smth.launcher

import android.animation.Animator
import android.animation.AnimatorListenerAdapter
import android.animation.TimeInterpolator
import android.animation.ValueAnimator
import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Path
import android.graphics.Rect
import android.graphics.RectF
import android.graphics.Shader
import android.graphics.Typeface
import android.graphics.drawable.Drawable
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.BatteryManager
import android.os.Bundle
import android.provider.Settings
import android.text.Editable
import android.text.TextUtils
import android.text.TextWatcher
import android.view.Gravity
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.PointerIcon
import android.view.View
import android.view.ViewGroup
import android.view.animation.DecelerateInterpolator
import android.view.animation.LinearInterpolator
import android.view.animation.OvershootInterpolator
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.GridLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import kotlin.math.roundToInt
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

// ---- SMTH design tokens -------------------------------------------------
private const val OBSIDIAN = 0xFF09090B.toInt()
private const val MAROON = 0xFF701B35.toInt()
private const val BLUSH = 0xFFF2C6D2.toInt()

private fun blush(alpha: Float) = (BLUSH and 0x00FFFFFF) or ((alpha * 255).toInt().coerceIn(0, 255) shl 24)
private fun maroon(alpha: Float) = (MAROON and 0x00FFFFFF) or ((alpha * 255).toInt().coerceIn(0, 255) shl 24)
private fun obsidian(alpha: Float) = (OBSIDIAN and 0x00FFFFFF) or ((alpha * 255).toInt().coerceIn(0, 255) shl 24)

private val EASE_OUT: TimeInterpolator = DecelerateInterpolator(1.9f)

    /** A launchable app discovered on the device (never a hard-coded package list). */
    private data class AppEntry(
        val label: String,
        val packageName: String,
        val icon: Drawable,
    )

class MainActivity : Activity() {
    /**
     * Built-in SMTH apps that live inside this launcher package. They are
     * distinct from externally installed apps and always available.
     */
    private val builtInApps: List<Pair<String, Int>> get() = listOf(
        "Terminal" to R.drawable.ic_smth_terminal,
    )

    private fun builtInAppEntries(): List<AppEntry> {
        return builtInApps.map { (label, iconRes) ->
            AppEntry(
                label = label,
                packageName = packageName,
                icon = getDrawable(iconRes)!!,
            )
        }
    }
    private lateinit var root: FrameLayout
    private lateinit var ahianTint: AhianWallpaperView
    private lateinit var desktop: FrameLayout
    private lateinit var taskbarView: View
    private lateinit var pinnedRow: LinearLayout
    private lateinit var startPanel: LinearLayout
    private lateinit var startGlass: GlassView
    private lateinit var pinnedBox: LinearLayout
    private lateinit var allGrid: GridLayout
    private lateinit var search: EditText
    private lateinit var empty: TextView
    private lateinit var clock: TextView
    private lateinit var dateLabel: TextView
    private lateinit var battery: TextView
    private lateinit var startGlyph: ImageView
    private var apps: List<AppEntry> = emptyList()
    private val launched = LinkedHashSet<String>()
    private var typefaceMono: Typeface? = null
    private var typefaceDot: Typeface? = null
    private var panelOpen = false
    private var animation: ValueAnimator? = null
    private var ahianIntro: AhianConstructionView? = null
    // True while the takeover is still showing the desktop you were using:
    // the AHIAN wallpaper is switched in behind the blue screen, not before.
    private var themeDeferred = false

    companion object {
        // The reconstruction belongs to desktop startup, not every resume.
        @Volatile private var ahianRevealPlayed = false
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = Color.TRANSPARENT
        window.navigationBarColor = Color.TRANSPARENT
        typefaceMono = loadFont("space_mono")
        typefaceDot = loadFont("doto") ?: typefaceMono
        build()
        refreshApps()
        startClock()
        val returningFromAhianCommand = intent.getBooleanExtra("show_ahian_construction", false)
        val ahianEnabled = getSharedPreferences("smth", MODE_PRIVATE)
            .getBoolean("ahian_mode", false)
        if (returningFromAhianCommand) themeDeferred = true
        applyAhianTheme()
        // AHIAN persists after first activation. Its takeover plays once per
        // launcher process, and again whenever `ahian` explicitly asks.
        when {
            returningFromAhianCommand -> {
                intent.removeExtra("show_ahian_construction")
                // The desktop stays on the wallpaper you were using for act 1;
                // showAhianConstruction switches it behind the blue screen.
                root.post { showAhianConstruction() }
            }
            ahianEnabled && !ahianRevealPlayed -> root.post { showAhianConstruction() }
            !ahianEnabled -> root.post { showStartupConstruction() }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        if (intent.getBooleanExtra("show_ahian_construction", false)) {
            intent.removeExtra("show_ahian_construction")
            themeDeferred = true
            applyAhianTheme()
            root.post { showAhianConstruction() }
        }
    }

    private fun showStartupConstruction() {
        val scale = try {
            Settings.Global.getFloat(contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f)
        } catch (_: Exception) { 1f }
        if (scale == 0f || isFinishing) return
        val intro = ConstructionView(this, typefaceDot, typefaceMono)
        root.addView(intro, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
    }

    private fun showAhianConstruction() {
        if (!::root.isInitialized || isFinishing) return
        ahianRevealPlayed = true
        ahianIntro?.let { root.removeView(it); it.stop() }
        // A transparent overlay over the live launcher desktop. The wallpaper,
        // tint, icons and taskbar stay exactly as they are; act 1 only adds the
        // error windows. At the countdown's zero the view is removed and the
        // real AHIAN desktop underneath is revealed.
        val intro = AhianConstructionView(this)
        intro.onBlueOpen = {
            if (themeDeferred) {
                themeDeferred = false
                applyAhianTheme()
            }
        }
        ahianIntro = intro
        root.addView(intro, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        intro.start {
            root.removeView(intro)
            if (ahianIntro === intro) ahianIntro = null
            themeDeferred = false
            applyAhianTheme()
        }
    }

    override fun onResume() {
        super.onResume()
        // Installed or removed apps must show up without restarting the launcher.
        refreshApps()
        applyAhianTheme()
    }

    /** AHIAN mode repaints the desktop purple-teal; `unahian` restores it. */
    private fun applyAhianTheme() {
        if (!::ahianTint.isInitialized || themeDeferred) return
        val on = getSharedPreferences("smth", MODE_PRIVATE).getBoolean("ahian_mode", false)
        ahianTint.visibility = if (on) View.VISIBLE else View.GONE
        if (on) ahianTint.resumeFlow() else ahianTint.pauseFlow()
    }

    override fun onBackPressed() {
        if (panelOpen) closeStart() else super.onBackPressed()
    }

    private fun loadFont(name: String): Typeface? = try {
        val id = resources.getIdentifier(name, "font", packageName)
        if (id == 0) null else resources.getFont(id)
    } catch (e: Exception) {
        null
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()
    private fun dpf(v: Float) = v * resources.displayMetrics.density

    private fun suppressPointer(view: View) {
        view.pointerIcon = PointerIcon.getSystemIcon(this, PointerIcon.TYPE_NULL)
        view.setOnHoverListener { v, _ ->
            v.pointerIcon = PointerIcon.getSystemIcon(this, PointerIcon.TYPE_NULL)
            true
        }
    }

    private fun label(text: String, size: Float, colour: Int, tracking: Float = 0.08f): TextView =
        TextView(this).apply {
            this.text = text
            setTextColor(colour)
            textSize = size
            typeface = typefaceMono
            letterSpacing = tracking
            includeFontPadding = false
        }

    private fun build() {
        root = FrameLayout(this)

        val art = BitmapFactory.decodeResource(resources, R.drawable.smth_wallpaper)
        val frostedArt = BitmapFactory.decodeResource(resources, R.drawable.smth_wallpaper_blur)
        val wallpaper = WallpaperView(this, art, frostedArt)
        root.addView(wallpaper, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT,
        ))

        // AHIAN improved-mode wallpaper: the same flowing gradient and dot
        // matrix the reconstruction ends on. Sits above the artwork and below
        // the desktop so shortcuts, taskbar and the Start menu keep working.
        ahianTint = AhianWallpaperView(this).apply {
            visibility = View.GONE
        }
        root.addView(ahianTint, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT,
        ))

        // Everything except the wallpaper respects the system insets.
        val surface = FrameLayout(this)
        root.addView(surface, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT,
        ))

        desktop = FrameLayout(this).apply {
            setPadding(dp(8), dp(8), dp(8), dp(8))
            isClickable = true
        }
        surface.addView(desktop, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT,
        ))

        // ---- taskbar -----------------------------------------------------
        val taskbar = GlassView(this, wallpaper, wallpaper.blurred).apply {
            setPadding(dp(8), 0, dp(8), 0)
            radius = dpf(22f)
        }
        val barRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        val startButton = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(10), 0, dp(12), 0)
            isClickable = true
            isFocusable = true
            // The logo is the search entry point: no separate Search button.
            setOnClickListener { openStart(focusSearch = true) }
            addView(ImageView(this@MainActivity).apply {
                setImageResource(R.drawable.ic_launcher_black)
                scaleType = ImageView.ScaleType.FIT_CENTER
            }, LinearLayout.LayoutParams(dp(28), dp(28)))
        }
        barRow.addView(startButton, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.MATCH_PARENT,
        ))

        pinnedRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(6), 0, dp(6), 0)
        }
        barRow.addView(pinnedRow, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.MATCH_PARENT, 1f))

        val tray = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(6), 0, dp(6), 0)
        }
        battery = label("", 9.5f, blush(0.78f), 0.04f)
        val trayColumn = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(4), 0, 0, 0)
            addView(label("", 10f, BLUSH, 0.02f).also { dateLabel = it })
            addView(label("", 8.5f, blush(0.55f), 0.08f).also { dateLabel = it })
        }
        // Clock stack: time over date, right aligned like a Windows tray.
        trayColumn.removeAllViews()
        clock = label("", 10.5f, BLUSH, 0.02f).apply { gravity = Gravity.END }
        dateLabel = label("", 8f, blush(0.55f), 0.08f).apply { gravity = Gravity.END }
        trayColumn.addView(clock, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT,
        ))
        trayColumn.addView(dateLabel, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT,
        ))
        tray.addView(battery, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT,
        ).apply { marginEnd = dp(12) })
        tray.addView(trayColumn)
        barRow.addView(tray, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.MATCH_PARENT,
        ))
        taskbar.addView(barRow, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT,
        ))
        taskbarView = taskbar
        surface.addView(taskbar, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, dp(46),
        ).apply {
            gravity = Gravity.BOTTOM
            marginStart = dp(12)
            marginEnd = dp(12)
            bottomMargin = dp(10)
        })

        // ---- start menu --------------------------------------------------
        startPanel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
        }
        startGlass = GlassView(this, wallpaper, wallpaper.blurred).apply {
            radius = dpf(22f)
            visibility = View.INVISIBLE
            alpha = 0f
            translationY = dpf(14f)
        }
        startGlass.addView(startPanel, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT,
        ))
        // Tall enough for the pinned row, the all-applications list and the
        // footer, but never taller than the space above the taskbar.
        val panelHeight = minOf(dp(560), resources.displayMetrics.heightPixels - dp(150))
        val startParams = FrameLayout.LayoutParams(dp(360), panelHeight).apply {
            gravity = Gravity.BOTTOM or Gravity.START
            marginStart = dp(12)
            bottomMargin = dp(64)
        }
        surface.addView(startGlass, startParams)

        val startContent = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(14), dp(16), dp(12))
        }
        val heading = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            addView(label("SMTH", 13f, BLUSH, 0.20f).apply {
                typeface = Typeface.create(typefaceDot ?: Typeface.DEFAULT, Typeface.BOLD)
            }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
            addView(label("START", 8f, blush(0.5f), 0.26f))
        }
        startContent.addView(heading)

        search = EditText(this).apply {
            hint = "Search applications"
            setHintTextColor(blush(0.5f))
            setTextColor(BLUSH)
            textSize = 11.5f
            typeface = typefaceMono
            setSingleLine(true)
            setPadding(dp(10), 0, dp(10), 0)
            background = glassPill()
            setOnFocusChangeListener { v, focused ->
                v.background = if (focused) focusedPill() else glassPill()
            }
            addTextChangedListener(object : TextWatcher {
                override fun beforeTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
                override fun onTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {
                    if (::allGrid.isInitialized) renderAll()
                }
                override fun afterTextChanged(s: Editable?) {}
            })
            setOnKeyListener { _, code, event ->
                if (event.action == KeyEvent.ACTION_DOWN && code == KeyEvent.KEYCODE_ENTER) {
                    submitFirst(); true
                } else false
            }
        }
        startContent.addView(search, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, dp(38),
        ).apply { topMargin = dp(12) })
        suppressPointer(search)

        pinnedLabel = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(0, dp(14), 0, dp(6))
            addView(label("PINNED", 7.5f, MAROON.let { blush(0.85f) }, 0.24f), LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT,
            ))
        }
        startContent.addView(pinnedLabel)
        pinnedBox = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.START
        }
        startContent.addView(pinnedBox, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, dp(58),
        ))

        val allLabel = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(0, dp(10), 0, dp(4))
            addView(label("ALL APPLICATIONS", 7.5f, blush(0.85f), 0.22f), LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
            allCount = label("", 7.5f, blush(0.45f), 0.12f)
            addView(allCount, LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT,
            ))
        }
        startContent.addView(allLabel)

        val scroll = ScrollView(this).apply {
            isFillViewport = true
            isVerticalScrollBarEnabled = false
            clipToPadding = false
        }
        allGrid = GridLayout(this).apply { columnCount = 5 }
        scroll.addView(allGrid, ViewGroup.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT,
        ))
        startContent.addView(scroll, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f,
        ))

        empty = label("No applications match", 9.5f, blush(0.55f), 0.04f).apply {
            gravity = Gravity.CENTER
            visibility = View.GONE
        }
        startContent.addView(empty)

        val footer = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(0, dp(10), 0, 0)
        }
        footer.addView(toolButton(R.drawable.ic_smth_settings, "SETTINGS") {
            startActivitySafely(Intent(Settings.ACTION_SETTINGS)); closeStart()
        }, LinearLayout.LayoutParams(0, dp(30), 1f).apply { marginEnd = dp(6) })
        footer.addView(toolButton(R.drawable.ic_smth_wallpaper, "WALLPAPER") {
            startActivitySafely(Intent(Intent.ACTION_SET_WALLPAPER)); closeStart()
        }, LinearLayout.LayoutParams(0, dp(30), 1f))
        startContent.addView(footer)

        startPanel.addView(startContent, LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT,
        ))

        // Tap the desktop to dismiss the Start panel, like a real shell.
        wallpaper.setOnClickListener { if (panelOpen) closeStart() }
        desktop.setOnClickListener { if (panelOpen) closeStart() }

        // Padding only: mutating layout params here would request another
        // layout, dispatch insets again and starve the first frame.
        root.setOnApplyWindowInsetsListener { _, insets ->
            surface.setPadding(0, insets.systemWindowInsetTop, 0, insets.systemWindowInsetBottom)
            desktop.setPadding(dp(8), dp(8), dp(8), dp(8))
            insets
        }
        setContentView(root)
        root.requestApplyInsets()
        applyPanelGeometry(startGlass)
    }

    private var allCount: TextView? = null
    private var pinnedLabel: LinearLayout? = null

    private fun applyPanelGeometry(panel: View) {
        val screen = resources.displayMetrics
        val params = panel.layoutParams as FrameLayout.LayoutParams
        params.width = minOf(dp(380), (screen.widthPixels * 0.56f).toInt())
        // Use the space above the taskbar rather than a fixed fraction, so the
        // all-applications list and search results are never clipped away.
        params.height = minOf(dp(560), screen.heightPixels - dp(96))
        panel.layoutParams = params
    }

    private fun glassPill(): GradientDrawable =
        GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM,
            intArrayOf(blush(0.11f), blush(0.03f))).apply {
            shape = GradientDrawable.RECTANGLE
            cornerRadius = dpf(999f)
            setStroke(dp(1), blush(0.18f))
        }

    private fun focusedPill(): GradientDrawable =
        GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM,
            intArrayOf(blush(0.18f), maroon(0.42f))).apply {
            shape = GradientDrawable.RECTANGLE
            cornerRadius = dpf(999f)
            setStroke(dp(1), blush(0.50f))
        }

    /** Rounded glass tile behind an app icon. */
    private fun glassTile(radius: Float = 14f): GradientDrawable =
        GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM,
            intArrayOf(blush(0.11f), maroon(0.13f))).apply {
            shape = GradientDrawable.RECTANGLE
            cornerRadius = dpf(radius)
            setStroke(dp(1), blush(0.17f))
        }

    private fun toolButton(icon: Int, text: String, onClick: () -> Unit): LinearLayout =
        LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            background = glassPill()
            isClickable = true
            isFocusable = true
            addView(ImageView(this@MainActivity).apply {
                setImageResource(icon)
                alpha = 0.85f
            }, LinearLayout.LayoutParams(dp(13), dp(13)))
            addView(label(text, 8.5f, BLUSH, 0.12f), LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT,
            ).apply { marginStart = dp(7) })
            setOnClickListener { onClick() }
        }

    // ---- layout content -------------------------------------------------
    private fun desktopShortcuts(): List<AppEntry> {
        val preferred = listOf(
            "com.android.chrome", "com.google.android.dialer", "com.google.android.apps.messaging",
            "com.android.camera2", "com.android.settings", "com.google.android.apps.photos",
        )
        val found = preferred.mapNotNull { pkg -> apps.firstOrNull { it.packageName == pkg } }
        // Only fill the column with shortcuts that actually fit above the
        // taskbar on this display; the rest live in the Start menu.
        val available = resources.configuration.screenHeightDp - 46 - 40
        val fits = (available / 62).coerceIn(3, 6)
        // Put the Terminal on the desktop when there's room for it.
        val terminalEntry = apps.firstOrNull { it.label == "Terminal" }
        return (listOfNotNull(terminalEntry) + found + apps).distinctBy { it.packageName }.take(fits)
    }

    private fun rebuildDesktop() {
        desktop.removeAllViews()
        // Invisible 96 x 82 cells. A shortcut always lands in one cell, and a
        // cell already holding another shortcut is skipped.
        // 88 x 78 cells holding an 80 x 70 glass tile: a 4 dp gutter on every
        // side, so shortcuts never overlap on any aspect ratio.
        val cellW = dp(88)
        val cellH = dp(78)
        val originX = dp(12)
        val originY = dp(12)
        val width = resources.displayMetrics.widthPixels
        val height = resources.displayMetrics.heightPixels - dp(56)
        val cols = maxOf(1, (width - originX) / cellW)
        val rows = maxOf(1, (height - originY - dp(64)) / cellH)
        val prefs = getSharedPreferences("smth_desktop", MODE_PRIVATE)
        val occupied = mutableSetOf<Pair<Int, Int>>()
        for ((index, entry) in desktopShortcuts().withIndex()) {
            val storedX = prefs.getInt(entry.packageName + "_x", originX)
            val storedY = prefs.getInt(entry.packageName + "_y", originY + index * cellH)
            var col = ((storedX - originX).toFloat() / cellW).roundToInt().coerceIn(0, cols - 1)
            var row = ((storedY - originY).toFloat() / cellH).roundToInt().coerceIn(0, rows - 1)
            val start = row * cols + col
            for (offset in 0 until cols * rows) {
                val cell = (start + offset) % (cols * rows)
                val candidate = cell % cols to cell / cols
                if (candidate !in occupied) {
                    col = candidate.first
                    row = candidate.second
                    break
                }
            }
            occupied.add(col to row)
            val left = originX + col * cellW
            val top = originY + row * cellH
            prefs.edit().putInt(entry.packageName + "_x", left)
                .putInt(entry.packageName + "_y", top).apply()
            val icon = desktopIcon(entry, index)
            val params = FrameLayout.LayoutParams(dp(80), dp(70)).apply {
                gravity = Gravity.TOP or Gravity.START
                leftMargin = left
                topMargin = top
            }
            desktop.addView(icon, params)
        }
    }

    private fun desktopIcon(entry: AppEntry, index: Int): LinearLayout =
        LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            isClickable = true
            isFocusable = true
            background = glassTile(13f)
            setPadding(dp(3), dp(3), dp(3), dp(2))
            addView(ImageView(this@MainActivity).apply {
                setImageDrawable(entry.icon)
                scaleType = ImageView.ScaleType.FIT_CENTER
                setPadding(dp(2), dp(2), dp(2), dp(2))
            }, LinearLayout.LayoutParams(dp(28), dp(28)))
            addView(label(entry.label, 8.5f, BLUSH, 0.02f).apply {
                maxLines = 1
                ellipsize = TextUtils.TruncateAt.END
                gravity = Gravity.CENTER
                setShadowLayer(4f, 0f, 1f, OBSIDIAN)
            }, LinearLayout.LayoutParams(dp(72), ViewGroup.LayoutParams.WRAP_CONTENT).apply {
                topMargin = dp(3)
            })
            setOnClickListener {
                pressFeedback(this)
                launch(entry)
            }
            setOnLongClickListener { openInfo(entry); true }
            var downX = 0f
            var downY = 0f
            var originX = 0f
            var originY = 0f
            var moved = false
            setOnTouchListener { view, event ->
                when (event.actionMasked) {
                    MotionEvent.ACTION_DOWN -> {
                        downX = event.rawX
                        downY = event.rawY
                        originX = view.x
                        originY = view.y
                        moved = false
                        true
                    }
                    MotionEvent.ACTION_MOVE -> {
                        val dx = event.rawX - downX
                        val dy = event.rawY - downY
                        if (kotlin.math.abs(dx) + kotlin.math.abs(dy) > dp(7)) moved = true
                        if (moved) {
                            val lp = view.layoutParams as FrameLayout.LayoutParams
                            lp.leftMargin = (originX + dx).toInt().coerceIn(0, (desktop.width - view.width).coerceAtLeast(0))
                            lp.topMargin = (originY + dy).toInt().coerceIn(0, (desktop.height - view.height).coerceAtLeast(0))
                            view.layoutParams = lp
                        }
                        true
                    }
                    MotionEvent.ACTION_UP -> {
                        if (moved) {
                            val (cellX, cellY) = snapDesktopCell(view)
                            val lp = view.layoutParams as FrameLayout.LayoutParams
                            lp.leftMargin = cellX
                            lp.topMargin = cellY
                            view.layoutParams = lp
                            val prefs = getSharedPreferences("smth_desktop", MODE_PRIVATE)
                            prefs.edit()
                                .putInt(entry.packageName + "_x", cellX)
                                .putInt(entry.packageName + "_y", cellY)
                                .apply()
                        } else {
                            view.performClick()
                        }
                        true
                    }
                    MotionEvent.ACTION_CANCEL -> true
                    else -> true
                }
            }
            suppressPointer(this)
        }

    /** Resolve a dropped shortcut to the nearest free 96 x 82 cell. */
    private fun snapDesktopCell(moving: View): Pair<Int, Int> {
        val cellW = dp(88)
        val cellH = dp(78)
        val originX = dp(12)
        val originY = dp(12)
        val cols = maxOf(1, (desktop.width - originX) / cellW)
        val rows = maxOf(1, (desktop.height - originY - dp(64)) / cellH)
        val lp = moving.layoutParams as FrameLayout.LayoutParams
        var col = ((lp.leftMargin - originX).toFloat() / cellW).roundToInt().coerceIn(0, cols - 1)
        var row = ((lp.topMargin - originY).toFloat() / cellH).roundToInt().coerceIn(0, rows - 1)
        val occupied = mutableSetOf<Pair<Int, Int>>()
        for (i in 0 until desktop.childCount) {
            val child = desktop.getChildAt(i)
            if (child === moving) continue
            val other = child.layoutParams as FrameLayout.LayoutParams
            occupied.add(
                ((other.leftMargin - originX).toFloat() / cellW).roundToInt() to
                    ((other.topMargin - originY).toFloat() / cellH).roundToInt(),
            )
        }
        val start = row * cols + col
        for (offset in 0 until cols * rows) {
            val cell = (start + offset) % (cols * rows)
            val candidate = cell % cols to cell / cols
            if (candidate !in occupied) {
                col = candidate.first
                row = candidate.second
                break
            }
        }
        return originX + col * cellW to originY + row * cellH
    }

    private fun pressFeedback(view: View) {
        view.animate().scaleX(0.96f).scaleY(0.96f).setDuration(90).withEndAction {
            view.animate().scaleX(1f).scaleY(1f).setDuration(120).start()
        }.start()
    }

    private fun rebuildPinned() {
        pinnedRow.removeAllViews()
        val limit = when {
            resources.configuration.screenWidthDp >= 800 -> 6
            resources.configuration.screenWidthDp >= 600 -> 5
            else -> 3
        }
        val pinned = pinnedApps().take(limit)
        for (entry in pinned) {
            val item = FrameLayout(this).apply {
                isClickable = true
                isFocusable = true
                background = glassTile(11f)
                addView(ImageView(this@MainActivity).apply {
                    setImageDrawable(entry.icon)
                    scaleType = ImageView.ScaleType.FIT_CENTER
                }, FrameLayout.LayoutParams(dp(20), dp(20)).apply { gravity = Gravity.CENTER })
                val dot = View(this@MainActivity).apply {
                    background = GradientDrawable().apply {
                        shape = GradientDrawable.OVAL
                        setColor(BLUSH)
                    }
                    visibility = if (launched.contains(entry.packageName)) View.VISIBLE else View.INVISIBLE
                }
                addView(dot, FrameLayout.LayoutParams(dp(3), dp(3)).apply {
                    gravity = Gravity.BOTTOM or Gravity.CENTER_HORIZONTAL
                    bottomMargin = dp(5)
                })
                setOnClickListener { pressFeedback(this); launch(entry) }
                setOnLongClickListener { openInfo(entry); true }
            }
            pinnedRow.addView(item, LinearLayout.LayoutParams(dp(34), ViewGroup.LayoutParams.MATCH_PARENT))
        }
    }

    private fun pinnedApps(): List<AppEntry> {
        val preferred = listOf(
            "com.android.chrome", "com.google.android.dialer", "com.google.android.apps.messaging",
            "com.android.camera2", "com.google.android.apps.photos", "com.android.settings",
        )
        val found = preferred.mapNotNull { pkg -> apps.firstOrNull { it.packageName == pkg } }
        return (found + apps).distinctBy { it.packageName }
    }

    private fun startPinned(): List<AppEntry> {
        // Built-in apps (the Terminal) always lead the Start menu pinned row.
        val base = pinnedApps()
        val builtIns = base.filter { it.packageName == packageName }
        return (builtIns + base).distinctBy { it.packageName }.take(5)
    }

    private fun rebuildStartPinned() {
        if (!::pinnedBox.isInitialized) return
        pinnedBox.removeAllViews()
        for (entry in startPinned()) {
            val item = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                gravity = Gravity.CENTER
                isClickable = true
                isFocusable = true
                background = glassTile(13f)
                setPadding(dp(3), dp(3), dp(3), dp(2))
                addView(ImageView(this@MainActivity).apply { setImageDrawable(entry.icon) },
                    LinearLayout.LayoutParams(dp(20), dp(20)))
                addView(label(entry.label, 7.5f, blush(0.72f), 0.0f).apply {
                    maxLines = 1
                    ellipsize = TextUtils.TruncateAt.END
                }, LinearLayout.LayoutParams(dp(50), ViewGroup.LayoutParams.WRAP_CONTENT).apply { topMargin = dp(3) })
                setOnClickListener { pressFeedback(this); launch(entry); closeStart() }
            }
            pinnedBox.addView(item, LinearLayout.LayoutParams(dp(56), dp(54)))
        }
    }

    private fun gridColumns(): Int = if (resources.configuration.screenWidthDp >= 700) 5 else 4

    private fun renderAll() {
        allGrid.removeAllViews()
        val query = search.text?.toString()?.trim()?.lowercase(Locale.getDefault()) ?: ""
        val shown = if (query.isEmpty()) apps else apps.filter {
            it.label.lowercase(Locale.getDefault()).contains(query)
        }
        // While searching, hide the pinned row so results sit at the top of
        // the panel and are visible without scrolling.
        val startInner = pinnedBox.parent as? View
        pinnedLabel?.visibility = if (query.isEmpty()) View.VISIBLE else View.GONE
        pinnedBox.visibility = if (query.isEmpty()) View.VISIBLE else View.GONE
        startInner?.requestLayout()
        allGrid.columnCount = gridColumns()
        val columns = allGrid.columnCount
        val width = dp(56)
        shown.forEachIndexed { index, entry ->
            val tile = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                gravity = Gravity.CENTER
                isClickable = true
                isFocusable = true
                background = glassTile(13f)
                setPadding(dp(3), dp(3), dp(3), dp(2))
                addView(ImageView(this@MainActivity).apply { setImageDrawable(entry.icon) },
                    LinearLayout.LayoutParams(dp(20), dp(20)))
                addView(label(entry.label, 7.5f, BLUSH, 0.0f).apply {
                    maxLines = 1
                    ellipsize = TextUtils.TruncateAt.END
                    gravity = Gravity.CENTER
                }, LinearLayout.LayoutParams(dp(48), ViewGroup.LayoutParams.WRAP_CONTENT).apply { topMargin = dp(3) })
                setOnClickListener { pressFeedback(this); launch(entry); closeStart() }
                setOnLongClickListener { openInfo(entry); true }
            }
            allGrid.addView(tile, GridLayout.LayoutParams().apply {
                this.width = width
                height = dp(54)
                columnSpec = GridLayout.spec(index % columns)
                setMargins(dp(2), dp(2), dp(2), dp(2))
            })
        }
        empty.visibility = if (shown.isEmpty()) View.VISIBLE else View.GONE
        allCount?.text = if (query.isEmpty()) "${apps.size} INSTALLED" else "${shown.size} OF ${apps.size}"
    }

    // ---- data -----------------------------------------------------------
    private fun refreshApps() {
        val pm = packageManager
        val intent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val installed = pm.queryIntentActivities(intent, 0)
            .asSequence()
            .filter { it.activityInfo.packageName != packageName }
            .mapNotNull { info ->
                try {
                    AppEntry(
                        label = info.loadLabel(pm).toString(),
                        packageName = info.activityInfo.packageName,
                        icon = try {
                            info.loadIcon(pm)
                        } catch (e: Exception) {
                            getDrawable(R.drawable.ic_smth_fallback)!!
                        },
                    )
                } catch (e: Exception) {
                    null
                }
            }
            .distinctBy { it.packageName }
            .sortedBy { it.label.lowercase(Locale.getDefault()) }
            .toList()
        // Merge built-in apps with installed apps; built-ins first so they
        // always appear even when no other terminal is installed. Installed
        // apps that duplicate a built-in label are dropped so the Terminal is
        // not listed twice when a third-party terminal is present.
        val builtIns = builtInAppEntries()
        apps = builtIns + installed.filterNot { inst ->
            builtIns.any { it.label.equals(inst.label, ignoreCase = true) }
        }
        rebuildDesktop()
        rebuildPinned()
        renderAll()
        rebuildStartPinned()
    }

    private fun submitFirst() {
        val query = search.text?.toString()?.trim()?.lowercase(Locale.getDefault()) ?: ""
        val first = apps.firstOrNull { it.label.lowercase(Locale.getDefault()).contains(query) }
        if (first != null) {
            launch(first)
            closeStart()
        }
    }

    // ---- start menu motion ----------------------------------------------
    private fun toggleStart() = if (panelOpen) closeStart() else openStart()

    private fun openStart(focusSearch: Boolean = false) {
        if (panelOpen) {
            if (focusSearch) search.requestFocus()
            return
        }
        panelOpen = true
        val panel = startGlass as View
        panel.visibility = View.VISIBLE
        panel.animate().cancel()
        panel.translationY = dpf(14f)
        panel.alpha = 0f
        panel.animate().translationY(0f).alpha(1f).setDuration(190).setInterpolator(EASE_OUT).start()
        if (focusSearch) search.postDelayed({ search.requestFocus() }, 120)
    }

    private fun closeStart() {
        if (!panelOpen) return
        panelOpen = false
        val panel = startGlass as View
        panel.animate().cancel()
        panel.animate().translationY(dpf(10f)).alpha(0f).setDuration(130)
            .setInterpolator(DecelerateInterpolator(1.4f))
            .withEndAction { panel.visibility = View.INVISIBLE }.start()
        search.clearFocus()
    }

    // ---- launching ------------------------------------------------------
    private fun launch(entry: AppEntry) {
        // Built-in apps are launched by explicit Intent; external apps via
        // launch intent so their real entry point is honoured.
        if (entry.packageName == packageName && entry.label == "Terminal") {
            startActivitySafely(Intent(this, TerminalActivity::class.java))
            return
        }
        val intent = packageManager.getLaunchIntentForPackage(entry.packageName)
        if (intent == null) {
            Toast.makeText(this, "${entry.label} cannot be launched", Toast.LENGTH_SHORT).show()
            return
        }
        launched.add(entry.packageName)
        rebuildPinned()
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
                val now = Date()
                clock.text = SimpleDateFormat("HH:mm", Locale.getDefault()).format(now)
                dateLabel.text = SimpleDateFormat("EEE dd MMM", Locale.getDefault()).format(now).uppercase(Locale.getDefault())
                val level = readBattery()
                battery.text = level
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
}

/**
 * Full-bleed wallpaper. Centre-crops the bundled art, then lays a soft obsidian
 * scrim over it so labels and glass panels stay readable at every screen size.
 */
private class WallpaperView(context: Context, val bitmap: Bitmap?, val blurred: Bitmap?) : View(context) {
    private val paint = Paint(Paint.FILTER_BITMAP_FLAG or Paint.ANTI_ALIAS_FLAG)
    private val scrim = Paint(Paint.ANTI_ALIAS_FLAG)

    init {
        scrim.shader = LinearGradient(
            0f, 0f, 0f, 1f,
            intArrayOf(obsidian(0.55f), obsidian(0.15f), obsidian(0.62f)),
            floatArrayOf(0f, 0.45f, 1f),
            Shader.TileMode.CLAMP,
        )
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        canvas.drawColor(OBSIDIAN)
        val bmp = bitmap ?: return
        val scale = maxOf(width.toFloat() / bmp.width, height.toFloat() / bmp.height)
        val w = bmp.width * scale
        val h = bmp.height * scale
        val dst = RectF((width - w) / 2f, (height - h) / 2f, (width + w) / 2f, (height + h) / 2f)
        canvas.drawBitmap(bmp, null, dst, paint)
        scrim.shader = LinearGradient(
            0f, 0f, 0f, height.toFloat(),
            intArrayOf(obsidian(0.58f), obsidian(0.18f), obsidian(0.66f)),
            floatArrayOf(0f, 0.45f, 1f),
            Shader.TileMode.CLAMP,
        )
        canvas.drawRect(0f, 0f, width.toFloat(), height.toFloat(), scrim)
    }
}

/**
 * Simulated liquid glass: the wallpaper visible through a blurred, tinted pane
 * with a thin blush edge and a top sheen. Real backdrop blur on API 31+, a
 * translucent tint on older releases.
 */
private class GlassView(context: Context, private val wallpaper: View, private val frosted: Bitmap?) : FrameLayout(context) {
    var radius = 0f
    private val pane = Paint(Paint.ANTI_ALIAS_FLAG)
    private val edge = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = resources.displayMetrics.density * 1f
        color = blush(0.16f)
    }
    private val sheen = Paint(Paint.ANTI_ALIAS_FLAG)
    private val path = Path()
    private val rect = RectF()
    private val src = Rect()
    private val wallpaperPaint = Paint(Paint.FILTER_BITMAP_FLAG or Paint.ANTI_ALIAS_FLAG)
    private val location = IntArray(2)
    private val rootLocation = IntArray(2)

    init {
        setWillNotDraw(false)
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        rect.set(0f, 0f, width.toFloat(), height.toFloat())
        path.reset()
        path.addRoundRect(rect, radius, radius, Path.Direction.CW)
        canvas.save()
        canvas.clipPath(path)

        // Backdrop: sample the wallpaper behind this pane and blur it.
        val art = (wallpaper as? WallpaperView)?.bitmap
        if (art != null && wallpaper.width > 0) {
            // Same centre-crop geometry as the sharp wallpaper, sampled from the
            // pre-blurred copy: real frosted glass at a fraction of the cost.
            val scale = maxOf(wallpaper.width.toFloat() / art.width, wallpaper.height.toFloat() / art.height)
            val drawnW = art.width * scale
            val drawnH = art.height * scale
            val offsetX = (wallpaper.width - drawnW) / 2f
            val offsetY = (wallpaper.height - drawnH) / 2f
            getLocationInWindow(location)
            wallpaper.getLocationInWindow(rootLocation)
            canvas.translate(-(location[0] - rootLocation[0]) - offsetX, -(location[1] - rootLocation[1]) - offsetY)
            val dst = RectF(0f, 0f, drawnW, drawnH)
            val source = frosted
            if (source != null) canvas.drawBitmap(source, null, dst, wallpaperPaint)
            else canvas.drawBitmap(art, null, dst, wallpaperPaint)
        }

        // Tinted obsidian and maroon wash, denser at the bottom edge.
        pane.shader = LinearGradient(
            0f, 0f, 0f, height.toFloat(),
            intArrayOf(obsidian(0.72f), obsidian(0.60f), maroon(0.34f)),
            floatArrayOf(0f, 0.55f, 1f),
            Shader.TileMode.CLAMP,
        )
        canvas.drawRect(rect, pane)

        // Blush reflection along the top edge only.
        sheen.shader = LinearGradient(
            0f, 0f, 0f, height * 0.6f,
            intArrayOf(blush(0.07f), blush(0.0f)),
            floatArrayOf(0f, 1f),
            Shader.TileMode.CLAMP,
        )
        canvas.drawRect(rect, sheen)
        canvas.restore()

        canvas.drawPath(path, edge)
    }
}


/**
 * Android adaptation of the SMTH construction intro, recoloured to the three
 * palette inks. It is a real drawn View over the live launcher and fades away
 * to reveal it; tapping anywhere or a zero animator scale skips it.
 */
private class ConstructionView(
    context: Context,
    private val dot: Typeface?,
    private val mono: Typeface?,
) : View(context) {
    /** The startup gesture: the SMTH logo fades in, holds, then fades out.
     *
     * There is no desktop reconstruction, no cursor choreography and no other
     * element. When the logo is gone the view is removed and the live launcher
     * underneath - which was always there - is simply visible.
     */
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val logoBitmap: Bitmap? = try {
        BitmapFactory.decodeResource(resources, R.drawable.ic_launcher_smth)
    } catch (e: Exception) {
        null
    }
    private val animator = ValueAnimator.ofFloat(0f, 1f)
    private var progress = 0f
    private var closed = false

    init {
        setBackgroundColor(OBSIDIAN)
        isClickable = true
        contentDescription = "SMTH startup logo; tap to skip"
        setOnClickListener { finishIntro() }
        animator.duration = 1_600
        animator.interpolator = LinearInterpolator()
        animator.addUpdateListener { animation ->
            progress = animation.animatedValue as Float
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
        // No outro: the logo has already faded out, so the live desktop shows.
        (parent as? ViewGroup)?.removeView(this)
    }

    private fun dpf(value: Float): Float = value * resources.displayMetrics.density

    private fun logoAlpha(elapsedMs: Float): Float = when {
        elapsedMs < 620f -> {
            val x = (elapsedMs / 620f).coerceIn(0f, 1f)
            1f - (1f - x) * (1f - x) * (1f - x)
        }
        elapsedMs < 980f -> 1f
        else -> (1f - (elapsedMs - 980f) / 580f).coerceIn(0f, 1f)
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val w = width.toFloat()
        val h = height.toFloat()
        if (w <= 0f || h <= 0f) return
        canvas.drawColor(OBSIDIAN)
        val alpha = logoAlpha(progress.coerceIn(0f, 1f) * 1_600f)
        if (alpha <= 0.001f) return
        paint.style = Paint.Style.FILL
        paint.alpha = (alpha * 255).toInt()
        val bmp = logoBitmap
        if (bmp != null) {
            val size = dpf(72f)
            val dst = RectF(w / 2f - size / 2f, h / 2f - size / 2f,
                w / 2f + size / 2f, h / 2f + size / 2f)
            canvas.drawBitmap(bmp, null, dst, paint)
        }
        paint.alpha = 255
    }
}
