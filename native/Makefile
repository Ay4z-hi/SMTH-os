# SMTH OS native shell helpers.
#
# These are small, dependency-free C programs for the hot paths of the live
# desktop: the taskbar sampler that runs every few seconds and the display
# layout watcher that used to be a three-process bash pipeline.
#
#   make -C native            build build/smth-glance and build/smth-moded
#   make -C native check      build with warnings as errors (CI)
#   make -C native bench      build and run the C-vs-assembly benchmark
#   make -C native install    install into $(DESTDIR)$(PREFIX)/bin
#   make -C native clean

CC ?= cc
CFLAGS ?= -O2 -std=c11 -Wall -Wextra -Werror -pedantic
PREFIX ?= /usr/local
DESTDIR ?=
BUILD := build
BINS := $(BUILD)/smth-glance $(BUILD)/smth-moded
BENCH := $(BUILD)/dots_bench
TOOLS := $(BUILD)/one_shot

.PHONY: all check bench bench-tool install clean

all: $(BINS)

check: $(BINS)

bench-tool: $(TOOLS)

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/%: %.c | $(BUILD)
	$(CC) $(CFLAGS) -o $@ $<

$(BUILD)/one_shot: bench/one_shot.c | $(BUILD)
	$(CC) $(CFLAGS) -o $@ $<

# Assembly is investigated, not shipped: this target compares the compiler's
# output with a hand-written AMD64 routine for the only per-poll inner loop.
bench: $(BENCH)
	./$(BENCH)

$(BENCH): bench/dots_bench.c bench/dots_asm_amd64.S | $(BUILD)
	@if [ "$$(uname -m)" != "x86_64" ]; then \
		echo "bench: AMD64 assembly benchmark skipped on $$(uname -m)"; \
		printf '#!/bin/sh\necho "bench: skipped (not x86_64)"\n' > $@; chmod +x $@; \
	else \
		$(CC) $(CFLAGS) -o $@ bench/dots_bench.c bench/dots_asm_amd64.S; \
	fi

install: all
	install -D -m755 $(BUILD)/smth-glance $(DESTDIR)$(PREFIX)/bin/smth-glance
	install -D -m755 $(BUILD)/smth-moded $(DESTDIR)$(PREFIX)/bin/smth-moded

clean:
	rm -rf $(BUILD)
