/*
 * Minimal Odessa audit image entry point.
 *
 * This is a CPU/DTB handoff probe, not an XNU loader. Odessa builds link a
 * no-op console because the ABL splash layout is not verified.
 */
#include <stdint.h>
#include "console.h"

#define rsr(r) ({ uint64_t value; __asm__ volatile("mrs %0, " r : "=r"(value)); value; })

void exc_handler(uint64_t slot, uint64_t *regs)
{
	(void)regs;
	con_clear(BLUE);
	con_hex("EXCEPTION SLOT", slot);
	con_hex("ESR", rsr("esr_el1"));
	con_hex("ELR", rsr("elr_el1"));
	con_hex("FAR", rsr("far_el1"));
	for (;;)
		__asm__ volatile("wfe");
}

void shim_main(uint64_t dtb)
{
	con_clear(BLUE);
	con_str("ODESSA", "CPU / DTB diagnostic only");
	con_str("STATUS", "not iOS; no storage writes");
	con_str("TARGET", "Moto G9 Plus XT2087-1");
	con_hex2("DTB", "at=", (uint32_t)dtb,
		 "magic=", dtb ? __builtin_bswap32(*(volatile uint32_t *)dtb) : 0);
	con_hex("MPIDR", rsr("mpidr_el1"));
	con_hex("MIDR", rsr("midr_el1"));
	con_hex("MMFR0", rsr("id_aa64mmfr0_el1"));
	con_hex("CNTFRQ", rsr("cntfrq_el0"));
	con_str("HARDWARE", "inherited probes disabled");
	con_str("SECONDARIES", "held in WFE loop");
	for (;;)
		__asm__ volatile("wfe");
}
