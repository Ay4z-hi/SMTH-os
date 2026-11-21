package os.smth.launcher

import android.content.Intent
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.PopupWindow
import android.widget.ScrollView
import android.widget.TextView
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

// ---- SMTH design tokens (shared with MainActivity) ----

private const val OBSIDIAN = 0xFF09090B.toInt()
private const val MAROON = 0xFF701B35.toInt()
private const val BLUSH = 0xFFF2C6D2.toInt()

private fun blush(alpha: Float) = (BLUSH and 0x00FFFFFF) or ((alpha * 255).toInt().coerceIn(0, 255) shl 24)
private fun maroon(alpha: Float) = (MAROON and 0x00FFFFFF) or ((alpha * 255).toInt().coerceIn(0, 255) shl 24)
private fun obsidian(alpha: Float) = (OBSIDIAN and 0x00FFFFFF) or ((alpha * 255).toInt().coerceIn(0, 255) shl 24)

// ---- Terminal Activity ----

class TerminalActivity : android.app.Activity() {
    private lateinit var root: FrameLayout
    private lateinit var terminalView: TerminalView
    private lateinit var titleBar: LinearLayout
    private lateinit var titleText: TextView
    private lateinit var closeButton: View
    private var mono: Typeface? = null
    private var dot: Typeface? = null
    private var ahianActive = false
    private var ahianOverlay: AhianConstructionView? = null
    private var maximized = false
    private var normalWidth = 0
    private var normalHeight = 0
    private val density by lazy { resources.displayMetrics.density }

    /** Close the terminal before handing AHIAN activation back to the desktop. */
    fun transitionToAhian() {
        val imm = getSystemService(INPUT_METHOD_SERVICE) as android.view.inputmethod.InputMethodManager
        imm.hideSoftInputFromWindow(terminalView.commandInput.windowToken, 0)
        terminalView.commandInput.clearFocus()
        val home = Intent(this, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
            .putExtra("show_ahian_construction", true)
        startActivity(home)
        finish()
    }

    private fun dp(v: Int) = (v * density).toInt()
    private fun dpf(v: Float) = v * density

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = Color.TRANSPARENT
        window.navigationBarColor = Color.TRANSPARENT
        mono = loadFont("space_mono")
        dot = loadFont("doto") ?: mono
        build()
    }

    private fun loadFont(name: String): Typeface? = try {
        val id = resources.getIdentifier(name, "font", packageName)
        if (id == 0) null else resources.getFont(id)
    } catch (e: Exception) { null
    }

    private fun build() {
        root = FrameLayout(this).apply {
            // Translucent smoked-glass terminal surface. Android 12+ supplies
            // the real backdrop blur; older versions retain the glass tint.
            background = android.graphics.drawable.GradientDrawable().apply {
                setColor(Color.argb(222, 8, 8, 12))
                cornerRadius = dp(14).toFloat()
                setStroke(dp(1), Color.argb(150, 190, 178, 210))
            }
            clipToOutline = true
        }
        setContentView(root)
        // Present Terminal as a floating desktop-style window, not a fullscreen Activity.
        val screen = resources.displayMetrics
        normalWidth = (screen.widthPixels * 0.82f).toInt().coerceAtLeast(dp(320))
        normalHeight = (screen.heightPixels * 0.78f).toInt().coerceAtLeast(dp(260))
        window.setBackgroundDrawableResource(android.R.color.transparent)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_DIM_BEHIND)
        if (android.os.Build.VERSION.SDK_INT >= 31) {
            window.setBackgroundBlurRadius(dp(30))
        }
        window.attributes = window.attributes.apply {
            dimAmount = 0.24f
            gravity = android.view.Gravity.TOP or android.view.Gravity.START
            x = (screen.widthPixels - normalWidth) / 2
            y = (screen.heightPixels - normalHeight) / 2
        }
        window.setLayout(normalWidth, normalHeight)

        // Title bar
        titleBar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(dp(12), dp(8), dp(8), dp(8))
            setBackgroundColor(Color.argb(204, 12, 10, 16))
        }
        titleText = TextView(this).apply {
            text = "Terminal"
            setTextColor(BLUSH)
            textSize = 11f
            typeface = dot ?: Typeface.DEFAULT
            letterSpacing = 0.15f
            setShadowLayer(2f, 0f, 1f, OBSIDIAN)
        }
        titleBar.addView(titleText, LinearLayout.LayoutParams(
            0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f
        ).apply { marginEnd = dp(8) })

        fun control(glyph: String, action: () -> Unit, colour: Int = blush(0.72f)): TextView =
            TextView(this).apply {
                text = glyph
                setTextColor(colour)
                textSize = 17f
                gravity = android.view.Gravity.CENTER
                isClickable = true
                setOnClickListener { action() }
            }
        val minimize = control("—", { moveTaskToBack(true) })
        val keyboard = control("⌨", {
            terminalView.commandInput.requestFocus()
            val imm = getSystemService(INPUT_METHOD_SERVICE) as android.view.inputmethod.InputMethodManager
            imm.showSoftInput(terminalView.commandInput, android.view.inputmethod.InputMethodManager.SHOW_IMPLICIT)
        })
        val maximize = control("□", {
            maximized = !maximized
            if (maximized) {
                window.setLayout(screen.widthPixels - dp(20), screen.heightPixels - dp(40))
            } else {
                window.setLayout(normalWidth, normalHeight)
            }
        })
        closeButton = control("×", { finish() }, Color.parseColor("#FF7185"))
        titleBar.addView(minimize, LinearLayout.LayoutParams(dp(34), dp(28)))
        titleBar.addView(keyboard, LinearLayout.LayoutParams(dp(34), dp(28)))
        titleBar.addView(maximize, LinearLayout.LayoutParams(dp(34), dp(28)))
        titleBar.addView(closeButton, LinearLayout.LayoutParams(dp(34), dp(28)))

        // Drag the floating window by its title bar.
        var dragX = 0f
        var dragY = 0f
        titleBar.setOnTouchListener { _, event ->
            val attrs = window.attributes
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> { dragX = event.rawX; dragY = event.rawY; true }
                MotionEvent.ACTION_MOVE -> {
                    if (!maximized) {
                        attrs.gravity = android.view.Gravity.TOP or android.view.Gravity.START
                        attrs.x += (event.rawX - dragX).toInt()
                        attrs.y += (event.rawY - dragY).toInt()
                        dragX = event.rawX; dragY = event.rawY
                        window.attributes = attrs
                    }
                    true
                }
                else -> false
            }
        }
        root.addView(titleBar, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, dp(36)
        ).apply { gravity = android.view.Gravity.TOP })

        // Terminal view
        terminalView = TerminalView(this, resources.displayMetrics.density, dot, mono).apply {
            setBackgroundColor(Color.argb(218, 8, 8, 12))
        }
        root.addView(terminalView, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT
        ).apply {
            topMargin = dp(36)
            bottomMargin = dp(22)
        })

        // Visible resize grip: drag its corner to resize the floating app window.
        val resizeGrip = TextView(this).apply {
            text = "◢"
            textSize = 16f
            gravity = android.view.Gravity.CENTER
            setTextColor(blush(0.65f))
            setBackgroundColor(obsidian(0.7f))
            var lastX = 0f
            var lastY = 0f
            setOnTouchListener { _, event ->
                when (event.actionMasked) {
                    MotionEvent.ACTION_DOWN -> { lastX = event.rawX; lastY = event.rawY; true }
                    MotionEvent.ACTION_MOVE -> {
                        if (!maximized) {
                            normalWidth = (normalWidth + (event.rawX - lastX).toInt())
                                .coerceIn(dp(320), screen.widthPixels - dp(20))
                            normalHeight = (normalHeight + (event.rawY - lastY).toInt())
                                .coerceIn(dp(260), screen.heightPixels - dp(40))
                            window.setLayout(normalWidth, normalHeight)
                        }
                        lastX = event.rawX; lastY = event.rawY
                        true
                    }
                    else -> false
                }
            }
        }
        root.addView(resizeGrip, FrameLayout.LayoutParams(dp(28), dp(28)).apply {
            gravity = android.view.Gravity.BOTTOM or android.view.Gravity.END
        })

        // Keyboard handling
        val editText = terminalView.commandInput
        editText.setOnKeyListener { _, keyCode, event ->
            if (event.action == KeyEvent.ACTION_DOWN &&
                (keyCode == KeyEvent.KEYCODE_ENTER || keyCode == KeyEvent.KEYCODE_NUMPAD_ENTER)
            ) {
                submitCommand()
                true
            } else false
        }
        editText.setOnEditorActionListener { _, _, _ ->
            submitCommand()
            true
        }
        editText.post {
            editText.requestFocus()
            val imm = getSystemService(INPUT_METHOD_SERVICE) as android.view.inputmethod.InputMethodManager
            imm.showSoftInput(editText, android.view.inputmethod.InputMethodManager.SHOW_IMPLICIT)
        }
    }

    private fun submitCommand() {
        val input = terminalView.commandInput
        val text = input.text.toString().trim()
        android.util.Log.i("SMTHTerminal", "submit: '$text'")
        if (text.isNotEmpty()) {
            terminalView.executeCommand(text)
            input.text.clear()
            // Keep focus for rapid typing
            input.post { input.requestFocus() }
        }
    }

    override fun onKeyUp(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_BACK && terminalView.ahianMode) {
            // In ahian mode, back should exit ahian via unahian
            terminalView.executeCommand("unahian")
            return true
        }
        return super.onKeyUp(keyCode, event)
    }
}

// ---- Terminal View ----

class TerminalView(
    context: android.content.Context,
    private val density: Float,
    private val dotFont: Typeface?,
    private val monoFont: Typeface?
) : LinearLayout(context) {
    private fun dp(v: Int) = (v * density).toInt()
    private fun dpf(v: Float) = v * density
    private val commandColor = blush(0.9f)
    private val outputColor = blush(0.8f)
    private val errorColor = maroon(0.9f)
    private val hintColor = blush(0.4f)

    private val output: TextView = TextView(context).apply {
        setTextColor(outputColor)
        textSize = 12f
        typeface = monoFont ?: Typeface.MONOSPACE
        letterSpacing = 0.02f
        setPadding(dp(16), dp(14), dp(16), dp(12))
        setShadowLayer(2f, 0f, 1f, OBSIDIAN)
    }

    val commandInput: EditText = EditText(context).apply {
        hint = "type a command…"
        setHintTextColor(hintColor)
        setTextColor(commandColor)
        textSize = 12.5f
        typeface = monoFont ?: Typeface.MONOSPACE
        setSingleLine(true)
        background = null
        setPadding(dp(12), dp(8), dp(12), dp(8))
        setShadowLayer(2f, 0f, 1f, OBSIDIAN)
        setSelection(0)
    }

    private var commandHistory = mutableListOf<String>()
    private var historyIndex = -1
    var ahianMode = false

    private val outputScroll = ScrollView(context).apply {
        isFillViewport = true
        addView(output, LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        ))
    }

    init {
        orientation = LinearLayout.VERTICAL
        addView(outputScroll, LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f
        ))

        val inputRow = LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            setBackgroundColor(obsidian(0.85f))
            setPadding(dp(8), dp(6), dp(8), dp(8))
            setOnTouchListener { _, _ ->
                commandInput.requestFocus()
                false
            }
        }

        val prefix = TextView(context).apply {
            text = "❯"
            setTextColor(blush(0.7f))
            textSize = 12.5f
            typeface = monoFont ?: Typeface.MONOSPACE
            setPadding(dp(4), 0, dp(8), 0)
        }

        inputRow.addView(prefix, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.MATCH_PARENT
        ))

        inputRow.addView(commandInput, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT
        ))

        addView(inputRow, LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        ))

    }

    fun executeCommand(cmd: String) {
        val trimmed = cmd.trim()
        if (trimmed.isEmpty()) return
        android.util.Log.i("SMTHTerminal", "command: $trimmed")

        // Add to history
        commandHistory.add(trimmed)
        historyIndex = commandHistory.size

        // Display the command
        appendOutput("❯ $trimmed", commandColor)

        when (trimmed.lowercase(Locale.getDefault())) {
            "help" -> showHelp()
            "clear" -> clearTerminal()
            "date" -> showDate()
            "version" -> showVersion()
            "about" -> showAbout()
            "ahian" -> enterAhian()
            "unahian" -> exitAhian()
            "exit", "quit" -> appendOutput("Type 'ahian' for the SMTH easter egg, or close the terminal.", hintColor)
            else -> appendOutput("command not found: $trimmed", errorColor)
        }

        scrollToBottom()
    }

    internal fun appendOutput(text: String, color: Int) {
        val spannable = android.text.SpannableStringBuilder()
        spannable.append(text)
        spannable.setSpan(android.text.style.ForegroundColorSpan(color), 0, spannable.length, 0)
        output.append(spannable)
        output.append("\n")
    }

    private fun clearTerminal() {
        output.text = ""
        appendOutput("terminal cleared", hintColor)
    }

    private fun showHelp() {
        appendOutput("SMTH Terminal — built-in commands", blush(0.9f))
        appendOutput("  help       show this message", outputColor)
        appendOutput("  clear      clear the terminal", outputColor)
        appendOutput("  date       show current date and time", outputColor)
        appendOutput("  version    show SMTH OS version", outputColor)
        appendOutput("  about      about this terminal", outputColor)
        appendOutput("  ahian      activate AHIAN mode (easter egg)", outputColor)
        appendOutput("  unahian    exit AHIAN mode", outputColor)
        appendOutput("", outputColor)
        appendOutput("AHIAN is a hidden experience. Type 'ahian' and press Enter.", hintColor)
    }

    private fun showDate() {
        val now = Date()
        val fmt = SimpleDateFormat("EEEE, dd MMMM yyyy | HH:mm:ss", Locale.getDefault())
        appendOutput(fmt.format(now), outputColor)
    }

    private fun showVersion() {
        appendOutput("SMTH OS Launcher v1.0.0", outputColor)
        appendOutput("Terminal v1.0.0 | Android", outputColor)
        appendOutput("Ahian mode v1.0.0", outputColor)
        appendOutput("", outputColor)
        appendOutput("Approximate build: 2026-11", hintColor)
    }

    private fun showAbout() {
        appendOutput("SMTH Terminal", blush(0.9f))
        appendOutput("A built-in terminal for SMTH OS.", outputColor)
        appendOutput("", outputColor)
        appendOutput("This terminal runs on Android, Linux (ISO) and Windows.", outputColor)
        appendOutput("It understands a small set of SMTH commands including the", outputColor)
        appendOutput("AHIAN easter egg. It does not expose the Android shell.", outputColor)
        appendOutput("", outputColor)
        appendOutput("Type 'help' for available commands.", hintColor)
    }

    private fun enterAhian() {
        val prefs = context.getSharedPreferences("smth", android.content.Context.MODE_PRIVATE)
        if (prefs.getBoolean("ahian_mode", false)) {
            appendOutput("AHIAN mode already active. Type 'unahian' to exit.", errorColor)
            return
        }
        prefs.edit().putBoolean("ahian_mode", true).apply()
        ahianMode = true
        setBackgroundColor(Color.parseColor("#7C4DFF"))
        // The keyboard and Terminal window must disappear before the desktop
        // reconstruction begins. MainActivity waits 2.5 seconds before drawing it.
        commandInput.text?.clear()
        (context as? TerminalActivity)?.transitionToAhian()
    }

    private fun exitAhian() {
        val prefs = context.getSharedPreferences("smth", android.content.Context.MODE_PRIVATE)
        if (!prefs.getBoolean("ahian_mode", false)) {
            appendOutput("Not in AHIAN mode. Type 'ahian' to enter.", hintColor)
            return
        }
        prefs.edit().putBoolean("ahian_mode", false).apply()
        ahianMode = false
        setBackgroundColor(OBSIDIAN)
        appendOutput("AHIAN mode off — normal experience restored", blush(0.9f))
        commandInput.text?.clear()
        commandInput.post { commandInput.requestFocus() }
    }

    private fun scrollToBottom() {
        outputScroll.post { outputScroll.fullScroll(android.widget.ScrollView.FOCUS_DOWN) }
    }
}
