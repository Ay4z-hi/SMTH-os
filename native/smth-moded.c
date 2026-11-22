/* smth-moded — re-apply the SMTH layout when a display is added or removed.
 *
 * The shell implementation was `bash + udevadm monitor + a `while read`
 * subshell`: three resident processes (~8 MB RSS measured) to run one command
 * per DRM hotplug. This version subscribes to the kernel uevent netlink group
 * directly (no libudev, no fork except the one `smth-mode auto` it must run)
 * and debounces a burst of events into a single reconfiguration.
 *
 * Behaviour preserved from the script:
 *   - `smth-mode auto` runs once at startup,
 *   - every DRM uevent triggers a reconfiguration after a short settle time,
 *   - the process is supervised by smthd from /etc/smth/services.json.
 *
 * If the uevent socket cannot be opened (hardened kernel, restricted seccomp)
 * the startup reconfiguration has still happened; the daemon reports the reason
 * once and exits 0 instead of being restarted in a loop by smthd.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <linux/netlink.h>
#include <sys/socket.h>

#define DEBOUNCE_MS 1000
#define UEVENT_CAP 8192

static volatile sig_atomic_t stop_requested = 0;

static void on_signal(int sig)
{
    (void)sig;
    stop_requested = 1;
}

static void run_layout(void)
{
    const pid_t pid = fork();
    if (pid == 0) {
        signal(SIGTERM, SIG_DFL);
        signal(SIGINT, SIG_DFL);
        execl("/usr/local/bin/smth-mode", "smth-mode", "auto", (char *)NULL);
        execlp("smth-mode", "smth-mode", "auto", (char *)NULL);
        _exit(127);
    }
}

/* uevents are a run of NUL-terminated KEY=VALUE fields; the first field is
 * "action@devpath". Only DRM subsystem events affect the layout. */
static int is_drm_event(const char *buf, size_t len)
{
    static const char key[] = "SUBSYSTEM=drm";
    const size_t key_len = sizeof key - 1;
    for (size_t i = 0; i < len;) {
        const char *field = buf + i;
        const size_t field_len = strnlen(field, len - i);
        if (field_len == key_len && memcmp(field, key, key_len) == 0)
            return 1;
        i += field_len + 1;
    }
    return 0;
}

static long long monotonic_ms(void)
{
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0)
        return 0;
    return (long long)ts.tv_sec * 1000LL + ts.tv_nsec / 1000000LL;
}

static void usage(FILE *stream)
{
    fputs("usage: smth-moded [--once]\n"
          "  --once  apply the layout once and exit (no hotplug monitor)\n", stream);
}

int main(int argc, char **argv)
{
    int once = 0;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--once") == 0)
            once = 1;
        else if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0) {
            usage(stdout);
            return 0;
        } else {
            usage(stderr);
            return 2;
        }
    }

    struct sigaction sa;
    memset(&sa, 0, sizeof sa);
    sa.sa_handler = on_signal;
    sigaction(SIGTERM, &sa, NULL);
    sigaction(SIGINT, &sa, NULL);
    signal(SIGCHLD, SIG_IGN); /* `smth-mode` is fire-and-forget */

    run_layout();
    if (once)
        return 0;

    const int fd = socket(AF_NETLINK, SOCK_DGRAM | SOCK_CLOEXEC, NETLINK_KOBJECT_UEVENT);
    if (fd < 0) {
        fprintf(stderr, "smth-moded: uevent socket unavailable: %s\n", strerror(errno));
        return 0;
    }
    struct sockaddr_nl addr;
    memset(&addr, 0, sizeof addr);
    addr.nl_family = AF_NETLINK;
    addr.nl_groups = 1; /* kernel uevents */
    if (bind(fd, (struct sockaddr *)&addr, sizeof addr) < 0) {
        fprintf(stderr, "smth-moded: cannot subscribe to uevents: %s\n", strerror(errno));
        close(fd);
        return 0;
    }

    char buf[UEVENT_CAP];
    int pending = 0;
    long long due = 0;

    while (!stop_requested) {
        int timeout = -1;
        if (pending) {
            const long long wait = due - monotonic_ms();
            timeout = wait <= 0 ? 0 : (int)wait;
        }
        struct pollfd pfd = {.fd = fd, .events = POLLIN, .revents = 0};
        const int ready = poll(&pfd, 1, timeout);
        if (ready < 0) {
            if (errno == EINTR)
                continue;
            perror("smth-moded: poll");
            break;
        }
        if (ready > 0 && (pfd.revents & POLLIN)) {
            /* Drain the socket; a burst of events still debounces to one run. */
            for (;;) {
                const ssize_t n = recv(fd, buf, sizeof buf, MSG_DONTWAIT);
                if (n < 0) {
                    if (errno == EINTR)
                        continue;
                    break;
                }
                if (n == 0)
                    break;
                if (is_drm_event(buf, (size_t)n)) {
                    pending = 1;
                    due = monotonic_ms() + DEBOUNCE_MS;
                }
            }
        }
        if (pending && monotonic_ms() >= due) {
            pending = 0;
            run_layout();
        }
    }

    close(fd);
    return 0;
}
