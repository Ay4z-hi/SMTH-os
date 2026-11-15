package os.smth.launcher

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.provider.Settings
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.*
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

private val BLACK = 0xFF000000.toInt()
private val ORANGE = 0xFFFF7A00.toInt()
private val BLUE = 0xFF2F6BFF.toInt()
private val WHITE = 0xFFFFFFFF.toInt()

class MainActivity : Activity() {
    private val apps = listOf(
        "Phone" to "com.google.android.dialer",
        "Messages" to "com.google.android.apps.messaging",
        "Camera" to "com.android.camera2",
        "Photos" to "com.google.android.apps.photos",
        "Chrome" to "com.android.chrome",
        "Settings" to "com.android.settings",
        "Files" to "com.google.android.documentsui",
        "Play Store" to "com.android.vending"
    )
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = BLACK
        window.navigationBarColor = BLACK
        window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LAYOUT_STABLE
        render()
    }
    private fun render() {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(22), dp(20), dp(22), dp(16))
            background = DotBackground()
        }
        val top = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        val brand = TextView(this).apply { text = "△ SMTH"; textSize = 23f; setTextColor(WHITE); typeface = Typeface.create("sans-serif-medium", Typeface.BOLD) }
        top.addView(brand, LinearLayout.LayoutParams(0, -2, 1f))
        val clock = TextView(this).apply { textSize = 14f; setTextColor(ORANGE); typeface = Typeface.MONOSPACE }
        top.addView(clock)
        root.addView(top)
        val date = TextView(this).apply { text = SimpleDateFormat("EEEE, d MMMM", Locale.getDefault()).format(Date()); setTextColor(WHITE); textSize = 13f; setPadding(0, dp(6), 0, dp(24)) }
        root.addView(date)
        val search = EditText(this).apply {
            hint = "Search apps"; setHintTextColor(0xFF999999.toInt()); setTextColor(WHITE)
            textSize = 15f; singleLine = true; setPadding(dp(14), dp(10), dp(14), dp(10))
            background = rounded(BLACK, BLUE)
        }
        root.addView(search, LinearLayout.LayoutParams(-1, dp(48)))
        val title = TextView(this).apply { text = "YOUR APPS"; setTextColor(ORANGE); textSize = 11f; letterSpacing = .16f; setPadding(0, dp(22), 0, dp(12)) }
        root.addView(title)
        val grid = GridLayout(this).apply { columnCount = 4 }
        val items = mutableListOf<View>()
        apps.forEachIndexed { index, item ->
            val cell = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER; setPadding(dp(4), dp(10), dp(4), dp(10))
                background = rounded(BLACK, if (index % 2 == 0) BLUE else ORANGE)
                isClickable = true; isFocusable = true
                setOnClickListener { launch(item.second) }
            }
            val glyph = TextView(this).apply {
                text = listOf("⌕", "▤", "◉", "▧", "◎", "⚙", "▣", "＋")[index]
                textSize = 26f; gravity = Gravity.CENTER; setTextColor(if (index % 2 == 0) ORANGE else BLUE)
            }
            val label = TextView(this).apply { text = item.first; textSize = 11f; setTextColor(WHITE); gravity = Gravity.CENTER; setPadding(0, dp(5), 0, 0) }
            cell.addView(glyph); cell.addView(label)
            val params = GridLayout.LayoutParams().apply { width = 0; height = dp(90); columnSpec = GridLayout.spec(index % 4, 1f); setMargins(dp(4), dp(4), dp(4), dp(4)) }
            grid.addView(cell, params); items.add(cell)
        }
        root.addView(grid)
        search.addTextChangedListener(object : android.text.TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {
                apps.forEachIndexed { i, a -> items[i].visibility = if (a.first.contains(s.toString(), true)) View.VISIBLE else View.GONE }
            }
            override fun afterTextChanged(s: android.text.Editable?) {}
        })
        val spacer = Space(this); root.addView(spacer, LinearLayout.LayoutParams(1, 0, 1f))
        val dock = TextView(this).apply {
            text = "●       ●       ●       ●"; textSize = 18f; gravity = Gravity.CENTER
            setTextColor(BLUE); background = rounded(BLACK, ORANGE); setPadding(0, dp(14), 0, dp(14))
        }
        root.addView(dock, LinearLayout.LayoutParams(-1, dp(54)))
        val quick = Button(this).apply { text = "QUICK SETTINGS"; setTextColor(WHITE); backgroundTintList = android.content.res.ColorStateList.valueOf(BLACK); setOnClickListener { startActivity(Intent(Settings.ACTION_SETTINGS)) } }
        root.addView(quick)
        setContentView(root)
        val tick = object : Runnable {
            override fun run() {
                clock.text = SimpleDateFormat("HH:mm", Locale.getDefault()).format(Date())
                clock.postDelayed(this, 1000)
            }
        }
        clock.post(tick)
    }
    private fun launch(pkg: String) {
        val intent = packageManager.getLaunchIntentForPackage(pkg)
        if (intent != null) startActivity(intent) else Toast.makeText(this, "App not installed", Toast.LENGTH_SHORT).show()
    }
    private fun rounded(fill: Int, stroke: Int) = GradientDrawable().apply { setColor(fill); setStroke(dp(1), stroke); cornerRadius = dp(4).toFloat() }
    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()
    private inner class DotBackground : View(this@MainActivity) {
        private val p = Paint(Paint.ANTI_ALIAS_FLAG)
        override fun onDraw(c: Canvas) {
            super.onDraw(c); c.drawColor(BLACK)
            val step = dp(23).toFloat()
            var y = dp(20).toFloat(); var row = 0
            while (y < height) {
                var x = dp(12).toFloat(); var col = 0
                while (x < width) {
                    p.color = if ((row + col) % 2 == 0) 0x22FF7A00.toInt() else 0x222F6BFF.toInt()
                    c.drawCircle(x, y, dp(1).toFloat(), p); x += step; col++
                }
                y += step; row++
            }
        }
    }
}
