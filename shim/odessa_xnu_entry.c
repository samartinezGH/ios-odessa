/* Early entry for the experimental Odessa XNU handoff image. */
#include "loader.h"

void exc_handler(unsigned long slot, unsigned long *regs)
{
	(void)slot;
	(void)regs;
	for (;;)
		__asm__ volatile("wfe");
}

void shim_main(unsigned long dtb)
{
	(void)loader_boot(dtb);
	/* No verified early console exists yet; stop safely if the loader returns. */
	for (;;)
		__asm__ volatile("wfe");
}
