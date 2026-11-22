/* smth-glance — taskbar system meters and the shared SMTH sampler.
 *
 * This replaces the bash implementation that chained bash + nproc + awk +
 * coreutils for every Waybar poll (measured: 8-9 execve calls, 9 processes and
 * ~11 MB peak RSS per CPU tick, every 3 s). The native version is one process,
 * allocates nothing on the heap, reads /proc and statvfs directly, and emits
 * the identical Waybar JSON contract with a single write(2).
 *
 * Contract (do not change without updating waybar-*.jsonc):
 *   smth-glance cpu    {"text":"CPU ●●○○○","tooltip":"load 1.23 on 8 cores","class":""}
 *   smth-glance mem    {"text":"RAM ●○○○○","tooltip":"42% used","class":""}
 *   smth-glance disk   {"text":"SSD ●○○○○","tooltip":"24% of / used"}
 *   smth-glance all    one JSON snapshot of every sampler
 *
 * `fmt` exposes the pure formatters so the dot/threshold rules can be tested
 * without racing the live machine:
 *   smth-glance fmt cpu  LOAD CORES
 *   smth-glance fmt mem  USED_KIB TOTAL_KIB
 *   smth-glance fmt disk USED_BLOCKS AVAIL_BLOCKS
 *
 * Exit status: 0 ok, 1 a sampler could not be read, 2 usage error.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/statvfs.h>
#include <unistd.h>

#define HOT_PERCENT 85
#define LINE_CAP 384

/* U+25CF / U+25CB, the same glyphs the shell taskbar used. */
static const char GLYPH_FILLED[] = "\xe2\x97\x8f";
static const char GLYPH_EMPTY[] = "\xe2\x97\x8b";

/* Five-slot dot meter: n = (pct*5+50)/100 rounded to the nearest slot. */
static void dots(int pct, char *out, size_t cap)
{
    if (pct < 0)
        pct = 0;
    if (pct > 100)
        pct = 100;
    const int filled = (pct * 5 + 50) / 100;
    size_t used = 0;
    for (int i = 0; i < 5; i++) {
        const char *glyph = i < filled ? GLYPH_FILLED : GLYPH_EMPTY;
        const size_t len = strlen(glyph);
        if (used + len + 1 > cap)
            break;
        memcpy(out + used, glyph, len);
        used += len;
    }
    out[used] = '\0';
}

static int percent_cpu(double load, long cores)
{
    if (cores < 1)
        cores = 1;
    if (load < 0.0)
        load = 0.0;
    const double pct = load * 100.0 / (double)cores;
    if (pct > 100.0)
        return 100;
    return (int)pct; /* truncation, matching the shell's printf %d */
}

static int percent_of(unsigned long long used, unsigned long long total)
{
    if (total == 0)
        return 0;
    unsigned long long pct = used * 100ULL / total;
    return pct > 100ULL ? 100 : (int)pct;
}

/* df(1) capacity = ceil(used * 100 / (used + available)); the shell sourced
 * its SSD figure from `df --output=pcent /`, so this keeps the numbers equal. */
static int percent_disk(unsigned long long used, unsigned long long available)
{
    const unsigned long long denom = used + available;
    if (denom == 0)
        return 0;
    const unsigned long long pct = (used * 100ULL + denom - 1ULL) / denom;
    return pct > 100ULL ? 100 : (int)pct;
}

static int format_cpu(const char *load, long cores, char *out, size_t cap)
{
    char meter[32];
    const int pct = percent_cpu(strtod(load, NULL), cores);
    dots(pct, meter, sizeof meter);
    return snprintf(out, cap,
                    "{\"text\":\"CPU %s\",\"tooltip\":\"load %s on %ld cores\",\"class\":\"%s\"}",
                    meter, load, cores, pct > HOT_PERCENT ? "hot" : "");
}

static int format_mem(unsigned long long used_kib, unsigned long long total_kib, char *out, size_t cap)
{
    char meter[32];
    const int pct = percent_of(used_kib, total_kib);
    dots(pct, meter, sizeof meter);
    return snprintf(out, cap,
                    "{\"text\":\"RAM %s\",\"tooltip\":\"%d%% used\",\"class\":\"%s\"}",
                    meter, pct, pct > HOT_PERCENT ? "hot" : "");
}

static int format_disk(unsigned long long used_blocks, unsigned long long avail_blocks, char *out, size_t cap)
{
    char meter[32];
    const int pct = percent_disk(used_blocks, avail_blocks);
    dots(pct, meter, sizeof meter);
    return snprintf(out, cap, "{\"text\":\"SSD %s\",\"tooltip\":\"%d%% of / used\"}", meter, pct);
}

static int read_all(const char *path, char *buf, size_t cap, size_t *len)
{
    const int fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0)
        return -1;
    ssize_t total = 0;
    while ((size_t)total + 1 < cap) {
        const ssize_t n = read(fd, buf + total, cap - 1 - (size_t)total);
        if (n < 0) {
            if (errno == EINTR)
                continue;
            close(fd);
            return -1;
        }
        if (n == 0)
            break;
        total += n;
    }
    close(fd);
    buf[total] = '\0';
    *len = (size_t)total;
    return 0;
}

static unsigned long long meminfo_kib(const char *buf, const char *key)
{
    const char *p = strstr(buf, key);
    if (p == NULL)
        return 0;
    p += strlen(key);
    while (*p == ' ' || *p == '\t')
        p++;
    return strtoull(p, NULL, 10);
}

static int sample_cpu(char *load, size_t cap, long *cores)
{
    char buf[256];
    size_t len = 0;
    if (read_all("/proc/loadavg", buf, sizeof buf, &len) != 0)
        return -1;
    size_t i = 0;
    while (i < len && buf[i] != ' ' && buf[i] != '\n' && i + 1 < cap) {
        load[i] = buf[i];
        i++;
    }
    load[i] = '\0';
    *cores = sysconf(_SC_NPROCESSORS_ONLN);
    if (*cores < 1)
        *cores = 1;
    return 0;
}

static int sample_mem(unsigned long long *used_kib, unsigned long long *total_kib)
{
    char buf[4096];
    size_t len = 0;
    if (read_all("/proc/meminfo", buf, sizeof buf, &len) != 0)
        return -1;
    const unsigned long long total = meminfo_kib(buf, "MemTotal:");
    const unsigned long long available = meminfo_kib(buf, "MemAvailable:");
    if (total == 0)
        return -1;
    *total_kib = total;
    /* `free` reports used = MemTotal - MemAvailable; keep the same definition. */
    *used_kib = total > available ? total - available : 0;
    return 0;
}

static int sample_disk(unsigned long long *used_blocks, unsigned long long *avail_blocks)
{
    struct statvfs fs;
    if (statvfs("/", &fs) != 0)
        return -1;
    *used_blocks = (unsigned long long)(fs.f_blocks - fs.f_bfree);
    *avail_blocks = (unsigned long long)fs.f_bavail;
    return 0;
}

static void usage(FILE *stream)
{
    fputs("usage: smth-glance cpu|mem|disk|all\n"
          "       smth-glance fmt cpu LOAD CORES\n"
          "       smth-glance fmt mem USED_KIB TOTAL_KIB\n"
          "       smth-glance fmt disk USED_BLOCKS AVAIL_BLOCKS\n", stream);
}

static int emit(const char *line, int len)
{
    if (len < 0)
        return 1;
    char out[LINE_CAP + 2];
    if ((size_t)len > sizeof out - 2)
        return 1;
    memcpy(out, line, (size_t)len);
    out[len++] = '\n';
    ssize_t written = 0;
    while (written < len) {
        const ssize_t n = write(STDOUT_FILENO, out + written, (size_t)(len - written));
        if (n < 0) {
            if (errno == EINTR)
                continue;
            return 1;
        }
        written += n;
    }
    return 0;
}

int main(int argc, char **argv)
{
    char line[LINE_CAP];
    const char *command = argc > 1 ? argv[1] : "";

    if (strcmp(command, "--help") == 0 || strcmp(command, "-h") == 0) {
        usage(stdout);
        return 0;
    }

    if (strcmp(command, "fmt") == 0) {
        if (argc != 5) {
            usage(stderr);
            return 2;
        }
        int len = -1;
        if (strcmp(argv[2], "cpu") == 0) {
            const long cores = strtol(argv[4], NULL, 10);
            len = format_cpu(argv[3], cores < 1 ? 1 : cores, line, sizeof line);
        } else if (strcmp(argv[2], "mem") == 0) {
            len = format_mem(strtoull(argv[3], NULL, 10), strtoull(argv[4], NULL, 10), line, sizeof line);
        } else if (strcmp(argv[2], "disk") == 0) {
            len = format_disk(strtoull(argv[3], NULL, 10), strtoull(argv[4], NULL, 10), line, sizeof line);
        } else {
            usage(stderr);
            return 2;
        }
        return emit(line, len);
    }

    if (strcmp(command, "cpu") == 0) {
        char load[32];
        long cores = 1;
        if (sample_cpu(load, sizeof load, &cores) != 0) {
            perror("smth-glance: /proc/loadavg");
            return 1;
        }
        return emit(line, format_cpu(load, cores, line, sizeof line));
    }

    if (strcmp(command, "mem") == 0) {
        unsigned long long used = 0, total = 0;
        if (sample_mem(&used, &total) != 0) {
            perror("smth-glance: /proc/meminfo");
            return 1;
        }
        return emit(line, format_mem(used, total, line, sizeof line));
    }

    if (strcmp(command, "disk") == 0) {
        unsigned long long used = 0, avail = 0;
        if (sample_disk(&used, &avail) != 0) {
            perror("smth-glance: statvfs /");
            return 1;
        }
        return emit(line, format_disk(used, avail, line, sizeof line));
    }

    if (strcmp(command, "all") == 0) {
        char load[32];
        long cores = 1;
        unsigned long long mem_used = 0, mem_total = 0, disk_used = 0, disk_avail = 0;
        if (sample_cpu(load, sizeof load, &cores) != 0 || sample_mem(&mem_used, &mem_total) != 0 ||
            sample_disk(&disk_used, &disk_avail) != 0) {
            perror("smth-glance: sampler");
            return 1;
        }
        const int len = snprintf(
            line, sizeof line,
            "{\"cpu\":{\"percent\":%d,\"load\":\"%s\",\"cores\":%ld},"
            "\"mem\":{\"percent\":%d,\"used_kib\":%llu,\"total_kib\":%llu},"
            "\"disk\":{\"percent\":%d,\"used_blocks\":%llu,\"avail_blocks\":%llu}}",
            percent_cpu(strtod(load, NULL), cores), load, cores, percent_of(mem_used, mem_total),
            mem_used, mem_total, percent_disk(disk_used, disk_avail), disk_used, disk_avail);
        return emit(line, len);
    }

    usage(stderr);
    return 2;
}
