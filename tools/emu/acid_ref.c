/* Référence de la preuve de la machine Acid (tools/emu/test_acid.py) : tools/machines/acid/acid.c compilé pour
 * l'ordinateur (HOST, même calcul en entiers), rejoué bloc par bloc avec ce que le moteur reçoit dans l'OS émulé.
 *
 * Entrée (stdin), un enregistrement par bloc, petit-boutiste : pmod, puis les champs de la voix lus par le moteur
 * (+0x2c marque, +0x34, +0x38, +0x230, +0x234), int32 ; puis les 9 mots 8.8 des paramètres p+0x14..p+0x24, int16.
 * Sortie (stdout) : par bloc, 1 si la voix a été calculée (sinon 0), puis les 32 échantillons avant la chaîne
 * d'ampli, int32.
 */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef int s32;
void acid_update(s32 pmod, char *v, const char *p);
void acid_render(s32 *out, char *v);

static int rendered;

void host_amp(s32 *out, char *v)
{
	(void)out;
	(void)v;
	rendered = 1;                 /* appelée seulement quand la voix est calculée */
}

int main(void)
{
	static char v[0x31c], p[0x30];
	int32_t rec[6], out[33];
	int16_t prm[9];
	static const int VOFF[5] = {0x2c, 0x34, 0x38, 0x230, 0x234};

	while (fread(rec, 4, 6, stdin) == 6 && fread(prm, 2, 9, stdin) == 9) {
		for (int k = 0; k < 5; k++)
			memcpy(v + VOFF[k], &rec[1 + k], 4);
		memcpy(p + 0x14, prm, sizeof prm);
		rendered = 0;
		acid_update(rec[0], v, p);
		acid_render(out + 1, v);
		out[0] = rendered;
		fwrite(out, 4, 33, stdout);
	}
	return 0;
}
