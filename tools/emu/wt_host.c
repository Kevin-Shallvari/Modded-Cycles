/* Banc HOST du moteur Wave (tools/emu/test_wavetable.py) : les variables de Model-TG, la voix, la chaine d'ampli
 * remplacee par rien. */
typedef int s32;
typedef unsigned int u32;
s32 host_track_slot[6], host_track_pend[6], host_slot[3 * 64];
char *host_copies, *host_scratch, *host_mem;
u32 host_clock;
void host_amp(s32 *out, char *v) { (void)out; (void)v; }
s32 host_load_slot = -1;
s32 host_load(u32 hash) { (void)hash; return host_load_slot; }
