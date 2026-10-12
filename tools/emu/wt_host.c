/* Banc HOST du moteur Wave (tools/emu/test_wavetable.py) : la table posee par le chargeur (wt_base / wt_count),
 * la voix, la chaine d'ampli remplacee par rien. */
typedef int s32;
typedef unsigned int u32;
s32 host_wt_base[6], host_wt_count[6];
char *host_mem;
u32 host_clock;
void host_amp(s32 *out, char *v) { (void)out; (void)v; }
