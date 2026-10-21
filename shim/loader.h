#pragma once
#include <stdint.h>

/* Boot the target-specific XNU payload found in the ABL ramdisk. */
const char *loader_boot(uintptr_t dtb);
