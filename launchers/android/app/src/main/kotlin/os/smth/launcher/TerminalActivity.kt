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
    private val density by lazy { resources.displayMetrics.density }

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
            setBackgroundColor(OBSIDIAN)
        }
        setContentView(root)

        // Title bar
        titleBar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(dp(12), dp(8), dp(8), dp(8))
            setBackgroundColor(obsidian(0.85f))
            setOnClickListener { finish() }
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
            ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT
        ).apply { marginEnd = dp(8) })

        closeButton = View(this).apply {
            setBackgroundColor(maroon(0.6f))
            setOnClickListener { finish() }
        }
        titleBar.addView(closeButton, FrameLayout.LayoutParams(dp(24), dp(24)).apply {
            gravity = android.view.Gravity.CENTER
        })
        root.addView(titleBar, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, dp(36)
        ).apply { gravity = android.view.Gravity.TOP })

        // Terminal view
        terminalView = TerminalView(this, resources.displayMetrics.density, dot, mono).apply {
            setBackgroundColor(OBSIDIAN)
        }
        root.addView(terminalView, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT
        ).apply {
            topMargin = dp(36)
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
        editText.requestFocus()
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
    private var ahianState: AhianState? = null
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
        ahianMode = true
        if (ahianState != null) {
            appendOutput("AHIAN mode already active. Type 'unahian' to exit.", errorColor)
            return
        }

        ahianState = AhianState(this, density)
        ahianState?.start()
    }

    private fun exitAhian() {
        ahianMode = false
        if (ahianState == null) {
            appendOutput("Not in AHIAN mode. Type 'ahian' to enter.", hintColor)
            return
        }

        ahianState?.exit()
        ahianState = null
        appendOutput("AHIAN mode exited. Normal terminal restored.", outputColor)
    }

    private fun scrollToBottom() {
        outputScroll.post { outputScroll.fullScroll(android.widget.ScrollView.FOCUS_DOWN) }
    }
}

// ---- Ahian State Machine ----

private class AhianState(
    private val terminal: TerminalView,
    private val density: Float
) {
    private fun dp(v: Int) = (v * density).toInt()
    private fun dpf(v: Float) = v * density
    private var active = false
    private var dialogs = mutableListOf<AhianDialog>()
    private var bsodView: AhianBsodView? = null
    private val handler = Handler(Looper.getMainLooper())

    // Timing constants (matching the documented sequence)
    private val TERMINAL_CORRUPT_DURATION = 1500L  // Stage 1
    private val DIALOG_STORM_DURATION = 10000L     // Stage 2 (~10s)
    private val BSOD_DELAY = 500L                  // Small delay before BSOD

    fun start() {
        if (active) return
        active = true
        android.util.Log.i("SMTHTerminal", "ahian stage 1: terminal failure")
        terminal.commandInput.isEnabled = false
        terminal.commandInput.alpha = 0.5f

        // Stage 1: Terminal appears to crash
        terminal.appendOutput("KERNEL PANIC: terminal subsystem failure", maroon(0.9f))
        terminal.appendOutput("stack trace: 0x701B35 -> 0xF2C6D2 -> 0x09090B", maroon(0.7f))
        terminal.appendOutput("memory: corrupted", maroon(0.7f))
        terminal.appendOutput("last command: ahian", maroon(0.7f))

        // Corrupt the terminal view visually
        terminal.post {
            terminal.animate().alpha(0.3f).setDuration(300).start()
            terminal.postDelayed({
                terminal.animate().alpha(0f).setDuration(400).withEndAction {
                    terminal.visibility = View.INVISIBLE
                }.start()
            }, TERMINAL_CORRUPT_DURATION - 400)
        }

        // Stage 2: Error dialog cascade
        terminal.postDelayed({
            spawnErrorCascade()
        }, TERMINAL_CORRUPT_DURATION)

        // Stage 3: BSOD
        terminal.postDelayed({
            showBsod()
        }, TERMINAL_CORRUPT_DURATION + DIALOG_STORM_DURATION + BSOD_DELAY)
    }

    private fun spawnErrorCascade() {
        android.util.Log.i("SMTHTerminal", "ahian stage 2: error cascade (24 dialogs over 10s)")
        val displayMetrics = terminal.context.resources.displayMetrics
        val screenWidth = displayMetrics.widthPixels
        val screenHeight = displayMetrics.heightPixels

        val dialogCount = 24
        val dialogMessages = listOf(
            "smth-core has stopped working",
            "AHIAN subsystem error",
            "Kernel panic: dot mismatch",
            "System alert: memory corruption",
            "Critical process terminated",
            "SMTH OS fatal error",
            "Window manager failure",
            "Surface composer crash"
        )
        val dialogBodies = listOf(
            "A problem caused the program to stop working correctly. Reboot recommended.",
            "The dot engine could not keep up with the current state.",
            "0x000000A1: attempted to divide beauty by zero.",
            "The window manager would like to apologise for this error.",
            "Something is trying to make your life beautiful.",
            "This dialog will close itself. Probably.",
            "FatalError: the void looked back.",
            "Error 0x701B35: invalid aesthetic operation."
        )

        for (i in 0 until dialogCount) {
            val delay = (i * 400L) // Stagger across ~10s (24 dialogs)
            val x = ((screenWidth * 0.1f) + (screenWidth * 0.8f * (i % 6) / 5f)).toInt()
            val y = ((screenHeight * 0.1f) + (screenHeight * 0.8f * (i / 6))).toInt()
            val width = ((screenWidth * 0.25f) + (Math.random() * screenWidth * 0.2f)).toInt().coerceIn(dp(200), dp(400))
            val height = ((screenHeight * 0.15f) + (Math.random() * screenHeight * 0.1f)).toInt().coerceIn(dp(100), dp(200))

            terminal.postDelayed({
                if (!active) return@postDelayed
                val dialog = AhianDialog(
                    terminal.context, x, y, width, height,
                    dialogMessages[i % dialogMessages.size],
                    dialogBodies[i % dialogBodies.size]
                )
                dialog.showDialog()
                dialogs.add(dialog)
            }, delay)
        }
    }

    private fun showBsod() {
        android.util.Log.i("SMTHTerminal", "ahian stage 3: bsod")
        // Close all error dialogs first
        dialogs.forEach { it.dismiss() }
        dialogs.clear()

        bsodView = AhianBsodView(terminal.context, density)
        bsodView?.addToWindow(terminal.context as? android.app.Activity)

        // Stage 4: Countdown
        var count = 9
        bsodView?.setCountdown(count)

        val countdownRunnable = object : Runnable {
            override fun run() {
                if (!active) return
                count--
                if (count > 0) {
                    android.util.Log.i("SMTHTerminal", "ahian stage 4: countdown $count")
                    bsodView?.setCountdown(count)
                    handler.postDelayed(this, 1000)
                } else {
                    // Stage 5: Improved mode
                    enterImprovedMode()
                }
            }
        }
        handler.postDelayed(countdownRunnable, 1000)
    }

    private var improvedOverlay: AhianImprovedOverlay? = null

    private fun enterImprovedMode() {
        android.util.Log.i("SMTHTerminal", "ahian stage 5: improved mode")
        // Close BSOD
        bsodView?.dismiss()
        bsodView = null

        // Show improved mode overlay (purple-teal)
        val overlay = AhianImprovedOverlay(terminal.context, density)
        overlay.addToWindow(terminal.context as? android.app.Activity)
        improvedOverlay = overlay
        // The launcher paints its desktop purple-teal while AHIAN is active.
        terminal.context.getSharedPreferences("smth", android.content.Context.MODE_PRIVATE).edit().putBoolean("ahian_mode", true).apply()

        // After a brief moment, reveal the terminal again with purple-teal theme
        terminal.postDelayed({
            overlay.dismiss()
            improvedOverlay = null
            terminal.post {
                terminal.visibility = View.VISIBLE
                terminal.animate().alpha(1f).setDuration(300).start()
                terminal.setBackgroundColor(Color.parseColor("#7C4DFF"))
            }
            terminal.commandInput.isEnabled = true
            terminal.commandInput.alpha = 1f
            terminal.commandInput.text?.clear()
            terminal.appendOutput("AHIAN mode activated", blush(0.9f))
            terminal.appendOutput("Welcome to the beautiful experience", blush(0.7f))
            terminal.appendOutput("Type 'unahian' to exit.", blush(0.4f))
            terminal.commandInput.post { terminal.commandInput.requestFocus() }
        }, 2000L)

        active = false
    }

    fun exit() {
        android.util.Log.i("SMTHTerminal", "ahian exit: red screen")
        active = false
        dialogs.forEach { it.dismiss() }
        dialogs.clear()
        bsodView?.dismiss()
        bsodView = null
        improvedOverlay?.dismiss()
        improvedOverlay = null

        // Angry red exit screen
        val exitOverlay = AhianExitOverlay(terminal.context, density)
        exitOverlay.addToWindow(terminal.context as? android.app.Activity)

        terminal.context.getSharedPreferences("smth", android.content.Context.MODE_PRIVATE).edit().putBoolean("ahian_mode", false).apply()

        terminal.postDelayed({
            exitOverlay.dismiss()
            // Restore terminal
            terminal.post {
                terminal.visibility = View.VISIBLE
                terminal.animate().alpha(1f).setDuration(300).start()
                terminal.setBackgroundColor(OBSIDIAN)
            }
            terminal.commandInput.isEnabled = true
            terminal.commandInput.alpha = 1f
            terminal.commandInput.text?.clear()
            terminal.commandInput.post { terminal.commandInput.requestFocus() }
        }, 3000L)
    }
}

// ---- Ahian Error Dialog ----

class AhianDialog(
    private val context: android.content.Context,
    private val x: Int,
    private val y: Int,
    width: Int,
    height: Int,
    private val title: String,
    private val message: String
) : PopupWindow(context) {
    private fun dp(v: Int): Int = (v * context.resources.displayMetrics.density).toInt()
    private fun dpf(v: Float): Float = v * context.resources.displayMetrics.density

    private val contentView = LinearLayout(context).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(dp(16), dp(14), dp(16), dp(12))
        setBackgroundColor(OBSIDIAN)
        setOnClickListener { dismiss() }
    }

    init {
        val icon = TextView(context).apply {
            text = "⚠"
            setTextColor(blush(0.8f))
            textSize = 24f
            setPadding(0, 0, dp(8), dp(4))
        }

        val titleView = TextView(context).apply {
            text = title
            setTextColor(BLUSH)
            textSize = 11f
            typeface = Typeface.MONOSPACE
            setPadding(0, 0, 0, dp(4))
        }

        val messageView = TextView(context).apply {
            text = message
            setTextColor(blush(0.6f))
            textSize = 10f
            typeface = Typeface.MONOSPACE
        }

        val okButton = TextView(context).apply {
            text = "OK"
            setTextColor(maroon(0.9f))
            textSize = 9f
            typeface = Typeface.MONOSPACE
            setPadding(dp(12), dp(4), dp(12), dp(4))
            setBackgroundColor(blush(0.1f))
            setOnClickListener { dismiss() }
        }

        contentView.addView(icon)
        contentView.addView(titleView)
        contentView.addView(messageView)
        contentView.addView(okButton)

        setContentView(contentView)
        setWidth(width)
        setHeight(height)
        isFocusable = true
        isOutsideTouchable = true
        setBackgroundDrawable(android.graphics.drawable.ColorDrawable(OBSIDIAN))
    }

    fun showDialog() {
        showAtLocation(contentView, android.view.Gravity.NO_GRAVITY, x, y)
    }
}

// ---- BSOD View ----

class AhianBsodView(
    context: android.content.Context,
    private val density: Float
) : FrameLayout(context) {
    private fun dp(v: Int) = (v * density).toInt()
    private fun dpf(v: Float) = v * density

    private val messagePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.WHITE
        textAlign = Paint.Align.CENTER
        textSize = 28f
        typeface = Typeface.create(Typeface.MONOSPACE, Typeface.BOLD)
    }
    private val countdownPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = blush(0.9f)
        textAlign = Paint.Align.CENTER
        textSize = 36f
        typeface = Typeface.create(Typeface.MONOSPACE, Typeface.BOLD)
    }
    private val accentPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = MAROON
        textAlign = Paint.Align.LEFT
        textSize = 16f
    }
    private var countdown = 9

    init {
        setBackgroundColor(Color.parseColor("#12245b"))
        setMinimumHeight(dp(400))
        setMinimumWidth(dp(600))
    }

    fun setCountdown(value: Int) {
        countdown = value
        invalidate()
    }

    fun dismiss() {
        parent?.let { (it as? ViewGroup)?.removeView(this) }
    }

    fun addToWindow(activity: android.app.Activity?) {
        val decorView = activity?.window?.decorView ?: return
        if (decorView is ViewGroup) {
            decorView.addView(this, FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            ))
        }
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)

        // Blue screen background
        canvas.drawColor(Color.parseColor("#12245b"))

        // Accent line at top
        canvas.drawRect(0f, 0f, width.toFloat(), dpf(4f), accentPaint)

        // SMTH OS heading
        canvas.drawText("SMTH OS", width / 2f, dpf(120f), messagePaint)

        // Main message
        canvas.drawText("wants to make your life beautiful", width / 2f, dpf(180f), messagePaint)

        // Stop code
        canvas.drawText("Stop code: AHIAN_BEAUTY_ATTEMPTED", width / 2f, dpf(220f), accentPaint)

        // Countdown
        canvas.drawText("making your life beautiful in $countdown…", width / 2f, dpf(280f), countdownPaint)
    }
}

// ---- Improved Mode Overlay ----

class AhianImprovedOverlay(
    context: android.content.Context,
    private val density: Float
) : FrameLayout(context) {
    private fun dp(v: Int) = (v * density).toInt()
    private fun dpf(v: Float) = v * density

    init {
        setBackgroundColor(Color.parseColor("#7C4DFF"))
        setMinimumHeight(dp(200))
        setMinimumWidth(dp(400))

        val message = TextView(context).apply {
            text = "AHIAN mode activated"
            setTextColor(Color.WHITE)
            textSize = 20f
            typeface = Typeface.create(Typeface.MONOSPACE, Typeface.BOLD)
            setPadding(dp(16), dp(24), dp(16), dp(8))
            setGravity(android.view.Gravity.CENTER)
        }

        val submessage = TextView(context).apply {
            text = "Welcome to the beautiful experience"
            setTextColor(blush(0.8f))
            textSize = 14f
            typeface = Typeface.MONOSPACE
            setPadding(dp(16), 0, dp(16), dp(16))
            setGravity(android.view.Gravity.CENTER)
        }

        addView(message)
        addView(submessage)
    }

    fun addToWindow(activity: android.app.Activity?) {
        val decorView = activity?.window?.decorView ?: return
        if (decorView is ViewGroup) {
            decorView.addView(this, FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            ))
        }
    }

    fun dismiss() {
        parent?.let { (it as? ViewGroup)?.removeView(this) }
    }
}

// ---- Ahian Exit Overlay (angry red) ----

class AhianExitOverlay(
    context: android.content.Context,
    private val density: Float
) : FrameLayout(context) {
    private fun dp(v: Int) = (v * density).toInt()
    private fun dpf(v: Float) = v * density

    init {
        setBackgroundColor(0xFFFF0000.toInt())

        val message = TextView(context).apply {
            text = "looks like you dont like ahian"
            setTextColor(0xFFFFFFFF.toInt())
            textSize = 22f
            typeface = Typeface.create(Typeface.MONOSPACE, Typeface.BOLD)
            setPadding(dp(16), dp(24), dp(16), dp(16))
            setGravity(android.view.Gravity.CENTER)
        }
        addView(message, FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        ).apply { gravity = android.view.Gravity.CENTER })
    }

    fun addToWindow(activity: android.app.Activity?) {
        val decorView = activity?.window?.decorView ?: return
        if (decorView is ViewGroup) {
            decorView.addView(this, FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            ))
        }
    }

    fun dismiss() {
        parent?.let { (it as? ViewGroup)?.removeView(this) }
    }
}
