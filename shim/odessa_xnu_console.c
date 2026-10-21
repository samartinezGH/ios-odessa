/* The Odessa XNU loader must not write to the unverified ABL splash buffer. */
#include "console.h"

volatile uint32_t *con_fb;

void con_clear(uint32_t bg) { (void)bg; }
void con_skip(void) { }
void con_str(const char *label, const char *text) { (void)label; (void)text; }
void con_hex(const char *label, uint64_t value) { (void)label; (void)value; }
void con_hex2(const char *label, const char *a, uint32_t va,
	      const char *b, uint32_t vb)
{
	(void)label;
	(void)a;
	(void)va;
	(void)b;
	(void)vb;
}
