package os.smth.launcher

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.IntentFilter
import android.content.res.ColorStateList
import android.graphics.Canvas
import android.graphics.Paint
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
        suppressPointer(root)
        setContentView(root)
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
