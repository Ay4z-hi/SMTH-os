/* one_shot — benchmark instrumentation, not shipped.
 *
 * Runs one command, redirects its output, and reports wall time, CPU time,
 * peak RSS and exit status from wait4(2) as a single line:
 *
 *   WALL_MS CPU_MS PEAK_RSS_KIB EXIT_STATUS
 *
 * Why this exists: a one-shot peak RSS read from a Python parent is useless,
 * because a forked child inherits the parent's high-water mark (~11 MiB for
 * CPython) before it execs. Forking from a 16 KiB C binary makes the floor the
 * launcher's own ~1.1 MiB, which is small enough to measure the helpers.
 */
#define _GNU_SOURCE
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static double now_ms(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec * 1000.0 + (double)ts.tv_nsec / 1e6;
}

int main(int argc, char **argv)
{
    int first = 1;
    if (argc > 1 && strcmp(argv[1], "--") == 0)
        first = 2;
    if (argc <= first) {
        fputs("usage: one_shot -- command [args...]\n", stderr);
        return 2;
    }

    const double start = now_ms();
    const pid_t pid = fork();
    if (pid == 0) {
        const int devnull = open("/dev/null", O_WRONLY);
        if (devnull >= 0) {
            dup2(devnull, STDOUT_FILENO);
            dup2(devnull, STDERR_FILENO);
        }
        execvp(argv[first], argv + first);
        _exit(127);
    }
    if (pid < 0) {
        perror("one_shot: fork");
        return 1;
    }

    int status = 0;
    struct rusage usage;
    memset(&usage, 0, sizeof usage);
    if (wait4(pid, &status, 0, &usage) < 0) {
        perror("one_shot: wait4");
        return 1;
    }
    const double wall = now_ms() - start;
    const double cpu = (double)usage.ru_utime.tv_sec * 1000.0 + (double)usage.ru_utime.tv_usec / 1000.0 +
                       (double)usage.ru_stime.tv_sec * 1000.0 + (double)usage.ru_stime.tv_usec / 1000.0;
    printf("%.3f %.3f %ld %d\n", wall, cpu, usage.ru_maxrss,
           WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status));
    return 0;
}
