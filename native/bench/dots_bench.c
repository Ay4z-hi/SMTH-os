/* Assembly investigation for the SMTH taskbar sampler (AMD64 only, not shipped).
 *
 * The only inner loop that runs on every Waybar poll is the five-slot dot
 * meter. This benchmark compares the shipping C implementation with a
 * hand-written AMD64 routine to answer one question with numbers rather than
 * opinion: is there anything for assembly to win here?
 *
 * Build and run: make -C native bench
 */
#define _GNU_SOURCE
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

static const char FILLED[] = "\xe2\x97\x8f";
static const char EMPTY[] = "\xe2\x97\x8b";

/* Copy of native/smth-glance.c:dots(), kept in sync deliberately: if this
 * drifts the benchmark is measuring something that is not shipped. */
static void dots_c(int pct, char *out)
{
    if (pct < 0)
        pct = 0;
    if (pct > 100)
        pct = 100;
    const int filled = (pct * 5 + 50) / 100;
    size_t used = 0;
    for (int i = 0; i < 5; i++) {
        const char *glyph = i < filled ? FILLED : EMPTY;
        const size_t len = strlen(glyph);
        memcpy(out + used, glyph, len);
        used += len;
    }
    out[used] = '\0';
}

void dots_asm(int pct, char *out);

#define ITERATIONS 20000000
#define MAX_PCT 100

static double now_ns(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec * 1e9 + (double)ts.tv_nsec;
}

int main(void)
{
    char a[32], b[32];

    /* Correctness first: the assembly must agree for every value, including
     * the out-of-range ones the clamp exists for. */
    for (int pct = -20; pct <= 120; pct++) {
        dots_c(pct, a);
        dots_asm(pct, b);
        if (strcmp(a, b) != 0) {
            fprintf(stderr, "MISMATCH at %d: c=%s asm=%s\n", pct, a, b);
            return 1;
        }
    }
    printf("dots: asm matches C for -20..120 (5 glyphs each)\n");

    volatile unsigned sink = 0;
    char out[32];

    /* Measure both orders: whichever routine runs second has the warmer
     * branch predictor and caches, which matters at this scale. */
    double c_ns[2], asm_ns[2];
    for (int order = 0; order < 2; order++) {
        for (int pass = 0; pass < 2; pass++) {
            const int run_c = (order == 0) == (pass == 0);
            const double t0 = now_ns();
            for (int i = 0; i < ITERATIONS; i++) {
                if (run_c)
                    dots_c(i % MAX_PCT, out);
                else
                    dots_asm(i % MAX_PCT, out);
                sink += (unsigned)out[0] + (unsigned)out[15];
            }
            const double t1 = now_ns();
            if (run_c)
                c_ns[order] = (t1 - t0) / ITERATIONS;
            else
                asm_ns[order] = (t1 - t0) / ITERATIONS;
        }
    }

    const double c_avg = (c_ns[0] + c_ns[1]) / 2.0;
    const double asm_avg = (asm_ns[0] + asm_ns[1]) / 2.0;
    printf("dots_c   : %.2f / %.2f ns/call (C first / asm first)\n", c_ns[0], c_ns[1]);
    printf("dots_asm : %.2f / %.2f ns/call (C first / asm first)\n", asm_ns[0], asm_ns[1]);
    printf("average  : C %.2f ns  asm %.2f ns  delta %+.2f ns (%+.1f%%)\n", c_avg, asm_avg,
           asm_avg - c_avg, c_avg > 0 ? (asm_avg - c_avg) / c_avg * 100.0 : 0.0);
    printf("sink     : %u\n", sink);
    printf("\nOne `smth-glance cpu` process costs ~1050000 ns end to end\n"
           "(exec, /proc read, write; measured by tools/bench_native.py).\n"
           "A difference of a few ns in this loop is noise at that scale, and\n"
           "the compiler's output already wins, which is why no assembly ships.\n");
    return 0;
}
