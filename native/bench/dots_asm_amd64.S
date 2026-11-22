# Hand-written AMD64 variant of the taskbar dot meter, for measurement only.
#
# void dots_asm(int pct, char *out)
#   rdi = percent (clamped to 0..100), rsi = 5-glyph buffer (16 bytes usable)
#
# Same output as dots_c in dots_bench.c: five U+25CF/U+25CB glyphs, NUL
# terminated. This file is not installed in the image.

    .text
    .globl dots_asm
    .type dots_asm, @function
dots_asm:
    movl    %edi, %eax
    testl   %eax, %eax
    jns     .Lclamp_high
    xorl    %eax, %eax
.Lclamp_high:
    cmpl    $100, %eax
    jle     .Lrounded
    movl    $100, %eax
.Lrounded:
    imull   $5, %eax, %eax
    addl    $50, %eax
    xorl    %edx, %edx
    movl    $100, %ecx
    divl    %ecx                  # eax = filled slots, edx = remainder
    xorl    %ecx, %ecx
.Lwrite:
    movw    $0x97e2, (%rsi)       # U+25xx prefix, bytes E2 97
    cmpl    %eax, %ecx
    jge     .Lempty
    movb    $0x8f, 2(%rsi)        # U+25CF ●
    jmp     .Lnext
.Lempty:
    movb    $0x8b, 2(%rsi)        # U+25CB ○
.Lnext:
    addq    $3, %rsi
    incl    %ecx
    cmpl    $5, %ecx
    jl      .Lwrite
    movb    $0, (%rsi)
    ret
    .size dots_asm, .-dots_asm

    .section .note.GNU-stack,"",@progbits
