/*
 * Acid : machine ajoutee du Model:Cycles (OS 1.13), une basse facon 303 (notes/44). Moteur en virgule fixe.
 *
 * Contrat de la boucle des voix (notes/14) : update(pmod, v, p) puis render(out, v), une fois par bloc de 32
 * trames a 48 kHz. pmod = note du trig (demi-tons << 16) ; v = voix du Cycles (0x31c o) ; p = parametres de la
 * piste (mots 8.8 : +0x14 PITCH, +0x16 COLOR, +0x18 SHAPE, +0x1a SWEEP, +0x1c CONTOUR, +0x1e PUNCH, +0x22 FINE,
 * +0x24 DECAY) ; v+0x34 / v+0x38 : trig de ce bloc / du bloc precedent ; out : 32 x int32 (Q31).
 *
 * Potards : COLOR = filtre facon DJ (0..63 passe-bas 20 Hz -> 20 kHz, 64 ouvert, 64..127 passe-haut 10 Hz ->
 * 20 kHz, lu en 8.8 pour des balayages sans marches) ; SHAPE = dent de scie -> carre (fondu continu) ; SWEEP =
 * resonance (auto-oscillation en haut de course) ; CONTOUR = enveloppe du filtre, bipolaire (64 : rien,
 * +-6 octaves) ; DECAY = duree de l'enveloppe du filtre (30 ms .. 2 s) et chaine d'ampli d'origine, reglee comme
 * TONE (enveloppe 0x400a9252, VCA 0x400a9430, PUNCH 0x400a967a), comme MACRO ; PUNCH = accent (plus d'attaque
 * dans le filtre, d'enveloppe et de resonance, decroissance du filtre bornee a ~200 ms, +3,5 dB) ; PITCH, FINE
 * et les touches : la note, comme les machines d'origine.
 *
 * Filtre : 4 etages passe-bas a un pole (TPT), contre-reaction globale k * f(y4), sans retard (ZDF). f est un coude
 * a 3 segments (lineaire jusqu'a T1, pente S jusqu'a T2, plat ensuite) : lineaire par morceaux, donc l'equation
 * sans retard se resout exactement en essayant un segment apres l'autre ; ses divisions ne dependent que des
 * coefficients du bloc (calcules dans update). Sur le segment plat, la contre-reaction est une constante : la
 * solution n'est pas calculee. Passe-haut : melange des etages (u - 4 y1 + 6 y2 - 4 y3 + y4), sans multiplication.
 * Oscillateur : dent de scie a polyBLEP ; carre = scie - scie decalee d'une demi-periode, d'ou le fondu
 * scie - m * scie decalee.
 *
 * Formats : signaux Q27 (marge +-16), coefficients Q31 ; qmul = multiplication fractionnaire de l'EMAC, saturee
 * (MACSR = 0xa0 pendant la boucle des voix). Compile avec HOST pour l'ordinateur : meme calcul en entiers
 * (tools/emu/acid_ref.c, la reference de la preuve tools/emu/test_acid.py). Tables : acid_tables.h, ecrit par
 * tools/gen_acid.py.
 *
 * Etat : un par piste (BSS de la charge utile, mis a zero au demarrage), remis a zero a la premiere note apres un
 * changement de machine (marque en v+0x2c, effacee par la remise a zero de la voix 0x400a7ab8). Une voix muette
 * (enveloppe d'ampli eteinte, pas de trig) n'est pas calculee.
 */
typedef signed char s8;
typedef short s16;
typedef int s32;
typedef unsigned int u32;

#include "acid_tables.h"

#define Q31MAX 0x7fffffff

#ifdef HOST
/* l'EMAC en mode fractionnaire : chaque produit entre dans l'accumulateur tronque a 8 bits sous le LSB du resultat
 * (unite 2^-62 : produit >> 23), la lecture tronque (>> 8) puis sature (OMC), comme tools/emu/emac.py */
#include <stdint.h>
static inline int64_t prod(s32 a, s32 b) { return ((int64_t)a * b) >> 23; }
static inline s32 rd(int64_t acc)
{
	acc >>= 8;
	return acc > Q31MAX ? Q31MAX : acc < -(int64_t)Q31MAX - 1 ? (s32)0x80000000 : (s32)acc;
}
static inline s32 qmul(s32 a, s32 b) { return rd(prod(a, b)); }
static inline s32 qmac2(s32 a, s32 b, s32 c, s32 d) { return rd(prod(a, b) + prod(c, d)); }
static inline s32 qmac4(s32 a, s32 b, s32 c, s32 d, s32 e, s32 f, s32 g, s32 h)
{
	return rd(prod(a, b) + prod(c, d) + prod(e, f) + prod(g, h));
}
#else
/* ACC0 rendu vide, comme l'exige l'OS (movclr) */
static inline s32 qmul(s32 a, s32 b)
{
	s32 r;
	__asm__ volatile("mac.l %1,%2,%%acc0\n\tmovclr.l %%acc0,%0" : "=d"(r) : "r"(a), "r"(b));
	return r;
}
static inline s32 qmac2(s32 a, s32 b, s32 c, s32 d)
{
	s32 r;
	__asm__ volatile("mac.l %1,%2,%%acc0\n\tmac.l %3,%4,%%acc0\n\tmovclr.l %%acc0,%0"
			 : "=d"(r) : "r"(a), "r"(b), "r"(c), "r"(d));
	return r;
}
static inline s32 qmac4(s32 a, s32 b, s32 c, s32 d, s32 e, s32 f, s32 g, s32 h)
{
	s32 r;
	__asm__ volatile("mac.l %1,%2,%%acc0\n\tmac.l %3,%4,%%acc0\n\tmac.l %5,%6,%%acc0\n\tmac.l %7,%8,%%acc0\n\t"
			 "movclr.l %%acc0,%0"
			 : "=d"(r) : "r"(a), "r"(b), "r"(c), "r"(d), "r"(e), "r"(f), "r"(g), "r"(h));
	return r;
}
#endif

#define V32(o) (*(s32 *)(v + (o)))
#define P16(o) (*(const s16 *)(p + (o)))

#ifdef HOST
void host_amp(s32 *out, char *v);                 /* la reference : rien (sortie avant la chaine d'ampli) */
#define AMP_DECAY(d) (0)
#else
#define CYC_VOICE0   0x42308828
#define CYC_VSTRIDE  0x31c
#define AMP_ENV(v)   ((void (*)(char *))0x400a9252)(v)
#define VCA(o, v)    ((void (*)(s32 *, char *))0x400a9430)(o, v)
#define PUNCH(o, v)  ((void (*)(s32 *, char *))0x400a967a)(o, v)
#define AMP_DECAY(d) (((const s32 *)0x4011d84c)[d])   /* DECAY -> multiplicateur par bloc (celui de TONE) */
#endif
#ifdef SLD_BASE
/* slide trigs de Model-TG, joues en slide 303 (notes/44 §10.5) ; SLD_BASE, SLD_INIT : symboles de model-tg-st */
#define SL_ON      (*(volatile s32 *)SLD_INIT)
#define SL(f, t)   (*(volatile s32 *)(SLD_BASE + (f) + 4 * (t)))
#define SL_W(t, k) (*(volatile s16 *)(SLD_BASE + 1024 + 64 * (t) + 2 * (k)))   /* SL_AST : valeurs de depart */
#define SL_ACT     96
#define SL_MSK     168
#define GLIDE      1074                             /* 1 - exp(-1/30) par bloc, Q15 : 20 ms, 95 % en ~60 ms */
#endif
#define MARK_OFF   0x2c
#define MARK       0x41434431                       /* 'ACD1' */
#define IDLE_LEVEL (1 << 14)                        /* enveloppe d'ampli sous -102 dB : voix muette */

/* coude, niveaux Q27 ; B2/B3 = decalages des segments 2 et 3 */
#define T1       16106127                           /* 0,12 */
#define T2       53687091                           /* 0,40 */
#define KNEE_S   751619277                          /* pente 0,35 (Q31) */
#define B2_Q27   10468982                           /* T1 - S T1 = 0,078 */
#define B3_Q27   29259839                           /* T1 + S (T2 - T1) = 0,218 */
#define B2_Q31   167503724
#define OUT_GAIN 751619277                          /* 0,35 */
#define OUT_ACC  1127428915                         /* 0,525 : accent +3,5 dB */

enum { BYPASS, LP, HP };

struct acid {
	u32 ph, dt, invdt;
	s32 m, xg, fenv;
	s32 s0, s1, s2, s3;                             /* etats du filtre, Q27 */
	s32 mode, G, c1, c2, c3, c4, P1, D1, Ps, Ds, Qs, kq8, og;
#ifdef SLD_BASE
	s32 ncur, was, in, glide;                       /* hauteur courante, glissait, blocs sans trig, slide en cours */
#endif
};

#ifdef HOST
static struct acid tracks[1];
static inline struct acid *track_of(const char *v) { (void)v; return &tracks[0]; }
#else
static struct acid tracks[6];
static inline struct acid *track_of(const char *v) { return &tracks[((u32)v - CYC_VOICE0) / CYC_VSTRIDE]; }
#endif

static inline s32 knob(s16 x) { s32 k = x >> 8; return k < 0 ? 0 : k > 127 ? 127 : k; }
static inline u32 mag(s32 x) { return x < 0 ? -(u32)x : (u32)x; }
static inline s32 shl_sat(s32 x, int sh)
{
	s32 lim = Q31MAX >> sh;
	return x > lim ? Q31MAX : x < -lim ? -Q31MAX : x << sh;
}

/* 1/D pour D dans [1, 8) en Q28, resultat Q31 (sature a 1) : Newton, 3 tours, une fois par bloc */
static s32 recip_q28(s32 d)
{
	int sh = 0;
	s32 r, e;
	while (d < 0x40000000) {                        /* d lu en Q31 = D/8, ramene dans [0,5, 1) */
		d <<= 1;
		sh++;
	}
	r = 1515870810 - (qmul(d, 2021161080) >> 1);    /* Q29 : 48/17 - 32/17 d */
	for (int i = 0; i < 3; i++) {
		e = (1 << 30) - qmul(d, r);             /* 2 - d r */
		r = qmul(r, e) << 2;
	}
	if (sh == 0)
		return r >> 1;
	return r >= (Q31MAX >> (sh - 1)) ? Q31MAX : r << (sh - 1);
}

/* dent de scie a bande limitee (polyBLEP), Q27 dans [-1, 1) */
static inline s32 saw(u32 ph, u32 dt, u32 invdt)
{
	s32 x = (s32)(ph >> 4) - (1 << 27);
	if (ph < dt) {
		s32 w = (s32)(~(ph * invdt) >> 1);      /* 1 - t */
		x += qmul(w, w) >> 4;
	} else if (-ph < dt) {
		s32 w = (s32)(~((-ph) * invdt) >> 1);   /* 1 - r */
		x -= qmul(w, w) >> 4;
	}
	return x;
}

void acid_update(s32 pmod, char *v, const char *p)
{
	struct acid *a = track_of(v);
#ifdef SLD_BASE
	s16 pw[19];
	int t = ((u32)v - CYC_VOICE0) / CYC_VSTRIDE, sliding = SL_ON && SL(SL_ACT, t);

	if (sliding) {                                  /* la note glissee reste fixe : valeurs de depart */
		u32 m = SL(SL_MSK, t);
		for (int k = 0; k < 19; k++)
			pw[k] = m >> k & 1 ? SL_W(t, k) : P16(2 * k);
		p = (const char *)pw;
	}
#endif
	s32 acc = P16(0x1e) != 0, dec = knob(P16(0x24));
	s32 col8 = P16(0x16), sweep = knob(P16(0x1a)), cont = knob(P16(0x1c));
	s32 n, oct, r, i, fr, idx, amt, mod, top = 0;
	u32 d;

	if (V32(MARK_OFF) != MARK) {                    /* 1re note sur cette machine */
		char *z = (char *)a;
		for (u32 k = 0; k < sizeof *a; k++)
			z[k] = 0;
		V32(MARK_OFF) = MARK;
	}
#ifdef SLD_BASE
	if (V32(0x34) && a->was) {                      /* slide trig : pas de nouvelle attaque */
		a->in = 2;
		a->glide = 1;
		if (!P16(0x20))
			V32(0x244) = 1;                 /* GATE a 0 : la note glissee decroit ensuite */
	}
	a->was = sliding;
	if (sliding) {                                  /* tenue au plein jusqu'au slide trig */
		V32(0x24c) = 1;
		V32(0x3c) = 0;
	}
#endif
	/* chaine d'ampli d'origine, reglee comme TONE (0x400aa7b8), comme MACRO */
	V32(0x250) = AMP_DECAY(dec);
	if (V32(0x38)) {
		V32(0x274) = V32(0x278) = 0x012c0f26;
		V32(0x280) = V32(0x284) = 0x001f7c5c;
		V32(0x290) = V32(0x294) = 0x7fffffff;
		V32(0x27c) = 0x82581e4b;
		V32(0x288) = 0x803ef8b8;
		if (acc) {
			V32(0x29c) = 0x20000000; V32(0x2a0) = 0x60000000; V32(0x2a4) = 0x20000000;
			V32(0x48) = 1;
		} else {
			V32(0x29c) = 0x7fffffff; V32(0x2a0) = 0x20000000; V32(0x2a4) = 0x20000000;
			V32(0x48) = 0;
		}
#ifdef SLD_BASE
		if (!a->in)
#endif
		a->fenv = Q31MAX;
	}

	/* note = PITCH - 64 + note du trig + FINE (+-2 demi-tons), comme toutes les machines ; 440 Hz a 69 */
	n = ((s32)P16(0x14) << 8) + (((s32)P16(0x22) - 0x4000) << 3) - (64 << 16) + pmod;
	n = n < 0 ? 0 : n > (127 << 16) ? (127 << 16) : n;
#ifdef SLD_BASE
	if (a->glide) {                                 /* vers la nouvelle note, exponentiel */
		s32 d = n - a->ncur;
		if (d > -64 && d < 64)
			a->glide = 0;
		else
			n = a->ncur += ((d >> 3) * GLIDE) >> 12;
	}
	a->ncur = n;
#endif
	oct = n / (12 << 16);
	r = n - oct * (12 << 16);
	i = r >> 12;
	fr = r & 0xfff;
	d = (PITCH_TAB[i] + (((PITCH_TAB[i + 1] - PITCH_TAB[i]) * (u32)fr) >> 12)) << oct;
	a->dt = d;
	a->invdt = 0xffffffffu / d;

	a->m = knob(P16(0x18)) * 16909320;              /* SHAPE / 127, Q31 */
	a->xg = acc ? 1932735283 : 1073741824;          /* attaque du filtre : 0,9 / 0,5 */

	/* coupure en pas de table (1/16 d'octave au-dessus de 10 Hz) Q8 : 10 octaves = 40832 ; + 6 octaves d'enveloppe */
	amt = (cont - 64) * 32768 / 63;
	if (acc)
		amt = amt * 13 / 8;
	mod = (24576 * amt) >> 15;
	mod = (mod * (a->fenv >> 16)) >> 15;
	a->fenv = qmul(a->fenv, FDEC_TAB[acc && dec > FDEC_ACCENT_MAX ? FDEC_ACCENT_MAX : dec]);
	col8 = col8 < 0 ? 0 : col8 > (127 << 8) ? (127 << 8) : col8;
	if (col8 < (64 << 8)) {
		a->mode = LP;
		idx = col8 * 40832 / (63 << 8);
		top = idx - (40832 - 4096);             /* derniere octave de COLOR : 0 .. 4096 */
		top = top < 0 ? 0 : top > 4096 ? 4096 : top;
		idx += 4096 + mod;
	} else if (col8 > (64 << 8)) {
		a->mode = HP;
		/* depuis 10 Hz (notes/44 §3.2) */
		idx = (col8 - (64 << 8)) * 44928 / (63 << 8) + mod;
	} else {
		a->mode = BYPASS;
		a->og = acc ? OUT_ACC : OUT_GAIN;
		return;
	}
	idx = idx < 0 ? 0 : idx > (G_TAB_N - 1) * 256 - 1 ? (G_TAB_N - 1) * 256 - 1 : idx;
	i = idx >> 8;
	{
		s32 G = G_TAB[i] + qmul(G_TAB[i + 1] - G_TAB[i], (idx & 255) << 23);
		s32 i1g = Q31MAX - G, G2 = qmul(G, G), G3 = qmul(G2, G), G4 = qmul(G3, G);
		s32 kq8 = sweep * 9089028, kG4;     /* k / 8, k = 4,3 SWEEP / 127 (+10 % avec l'accent) */
		if (acc)
			kq8 += kq8 / 10;
		kG4 = qmul(kq8, G4);                    /* k G4, Q28 */
		a->G = G;
		a->c1 = qmul(G3, i1g);
		a->c2 = qmul(G2, i1g);
		a->c3 = qmul(G, i1g);
		a->c4 = i1g;
		a->D1 = recip_q28((1 << 28) + kG4);
		a->Ds = recip_q28((1 << 28) + qmul(KNEE_S, kG4));
		a->P1 = qmul(G4, a->D1);
		a->Ps = qmul(G4, a->Ds);
		a->Qs = qmul(qmul(kG4, B2_Q31), a->Ds) >> 1;
		a->kq8 = kq8;
		/* passe-bas : (1 + k/2 + t k/2) / 8, t de 0 a 1 (1/2 avec l'accent) sur la derniere octave (notes/44 §3.2) */
		a->og = acc ? OUT_ACC : OUT_GAIN;
		if (a->mode == LP)
			a->og = qmul((1 << 28) + (kq8 >> 1) + qmul(kq8 >> 1, (top == 4096 ? Q31MAX : top << 19) >> acc),
				     a->og);
	}
}

void acid_render(s32 *out, char *v)
{
	struct acid *a = track_of(v);
	u32 ph = a->ph, dt = a->dt, invdt = a->invdt;
	s32 m = a->m, xg = a->xg, og = a->og, mode = a->mode;
	s32 s0 = a->s0, s1 = a->s1, s2 = a->s2, s3 = a->s3;
	s32 G = a->G, c1 = a->c1, c2 = a->c2, c3 = a->c3, c4 = a->c4;
	s32 P1 = a->P1, D1 = a->D1, Ps = a->Ps, Ds = a->Ds, Qs = a->Qs, kq8 = a->kq8;
	int sh = mode == LP ? 7 : 4;

	if (!V32(0x34) && !V32(0x38) && mag(V32(0x230)) < IDLE_LEVEL && mag(V32(0x234)) < IDLE_LEVEL) {
		for (int j = 0; j < 32; j++)            /* voix muette : pas calculee */
			out[j] = 0;
		return;
	}
	for (int j = 0; j < 32; j++) {
		s32 x = saw(ph, dt, invdt);
		s32 o;
		x = qmul(x - qmul(m, saw(ph + 0x80000000u, dt, invdt)), xg);   /* scie - m * scie decalee */
		ph += dt;
		if (mode == BYPASS) {
			o = x;
		} else {
			s32 S = qmac4(c1, s0, c2, s1, c3, s2, c4, s3);
			s32 y = qmac2(P1, x, D1, S), fb, u, w, y0, y1, y2;
			if (y >= T1 || y <= -T1) {              /* au-dela du coude : segment suivant, puis le plat */
				int neg = y < 0;
				y = qmac2(Ps, x, Ds, S) + (neg ? Qs : -Qs);
				if (mag(y) < T2)
					fb = qmul(KNEE_S, y) + (neg ? -B2_Q27 : B2_Q27);
				else                    /* segment plat : contre-reaction constante, y inutile */
					fb = neg ? -B3_Q27 : B3_Q27;
			} else {
				fb = y;
			}
			u = x - (qmul(kq8, fb) << 3);
			w = qmul(u - s0, G);  y0 = w + s0;  s0 = y0 + w;
			w = qmul(y0 - s1, G); y1 = w + s1;  s1 = y1 + w;
			w = qmul(y1 - s2, G); y2 = w + s2;  s2 = y2 + w;
			w = qmul(y2 - s3, G); y = w + s3;   s3 = y + w;
			o = mode == LP ? y : u - (y0 << 2) + (y1 << 2) + (y1 << 1) - (y2 << 2) + y;
		}
		out[j] = shl_sat(qmul(o, og), sh);
	}
	a->ph = ph;
	a->s0 = s0; a->s1 = s1; a->s2 = s2; a->s3 = s3;
#ifdef HOST
	host_amp(out, v);
#else
#ifdef SLD_BASE
	if (a->in) {                                    /* slide trig : la chaine d'ampli ne voit pas le trig */
		s32 t34 = V32(0x34), t38 = V32(0x38);
		V32(0x34) = V32(0x38) = 0;
		AMP_ENV(v);
		VCA(out, v);
		PUNCH(out, v);
		V32(0x34) = t34;
		V32(0x38) = t38;
		a->in--;
		return;
	}
#endif
	AMP_ENV(v);
	VCA(out, v);
	PUNCH(out, v);
#endif
}
