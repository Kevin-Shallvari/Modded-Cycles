/*
 * Wave : machine ajoutee du Model:Cycles avec Model-TG (OS 1.13), qui joue une table d'ondes pre-travailee
 * (notes/52). Moteur en virgule fixe.
 *
 * Le fichier que Model-TG a charge pour la piste (track_slot -> slot_base, slot_count ; en-tete de 64 o, puis
 * 16 bits gros-boutiens) est une table convertie par l'outil web : la table entiere, puis les copies adoucies
 * par octave plus courtes que la table (LGC, OFF). Rien n'est calcule ici : les copies sont lues telles
 * quelles. Un fichier non converti (slot_count non multiple de S_TOTAL) ne joue rien.
 *
 * Potards : COLOR = position dans la table ; MACHINE tenue + COLOR = enveloppe -> position (0 : rien ; param 0x0a,
 * k = 27) ; SHAPE = enveloppe -> coupure (64 : rien) ; SWEEP = coupure du passe-bas d'Acid (20 Hz -> 20 kHz) ;
 * CONTOUR = resonance ; DECAY = duree de l'enveloppe et chaine d'ampli d'origine (comme Acid) ; PUNCH = accent.
 *
 * Contrat de la boucle des voix (notes/14) : update(pmod, v, p) puis render(out, v), une fois par bloc de 32 trames.
 */
typedef signed char s8;
typedef short s16;
typedef int s32;
typedef unsigned int u32;
typedef unsigned short u16;

#include "wt_tables.h"

#define Q31MAX 0x7fffffff

#ifdef HOST
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

/* Model-TG (adresses fournies par tools/gen_wavetable.py, ou par le banc HOST) */
#ifdef HOST
extern s32 host_track_slot[6], host_track_pend[6], host_slot[3 * 64];
extern char *host_mem;
extern u32 host_clock;
#define TRACK_SLOT host_track_slot
#define TRACK_PEND host_track_pend
#define SLOT_HASH  ((u32 *)host_slot)
#define SLOT_BASE  ((u32 *)host_slot + 64)
#define SLOT_COUNT ((u32 *)host_slot + 128)
#define CLOCK      host_clock
#define SAMPLE(b)  ((const s16 *)(host_mem + (b)))
void host_amp(s32 *out, char *v);
s32 host_load(u32 hash);
#define AMP_DECAY(d) (0)
#else
#define TRACK_SLOT ((volatile s32 *)TG_TRACK_SLOT)
#define TRACK_PEND ((volatile s32 *)TG_TRACK_PEND)
#define SLOT_HASH  ((volatile u32 *)TG_SLOT_HASH)
#define SLOT_BASE  ((volatile u32 *)(TG_SLOT_HASH + 256))
#define SLOT_COUNT ((volatile u32 *)(TG_SLOT_HASH + 512))
#define CLOCK      (*(volatile u32 *)0x8000184c)             /* change a chaque bloc audio */
#define SAMPLE(b)  ((const s16 *)(b))
#define CYC_VOICE0   0x42308828
#define CYC_VSTRIDE  0x31c
#define AMP_ENV(v)   ((void (*)(char *))0x400a9252)(v)
#define VCA(o, v)    ((void (*)(s32 *, char *))0x400a9430)(o, v)
#define PUNCH(o, v)  ((void (*)(s32 *, char *))0x400a967a)(o, v)
#define AMP_DECAY(d) (((const s32 *)0x4011d84c)[d])
#endif
#define MARK_OFF   0x2c
#define MARK       0x57415631                       /* 'WAV1' */
#define IDLE_LEVEL (1 << 14)
#define HDR        64                               /* en-tete du fichier de Model-TG */
#define LGN        11                               /* trames de 2048 points (regle fixe du convertisseur) */
/* coude du filtre d'Acid (notes/51), niveaux Q27 */
#define T1       16106127
#define T2       53687091
#define KNEE_S   751619277
#define B2_Q27   10468982
#define B3_Q27   29259839
#define B2_Q31   167503724
#define OUT_GAIN 751619277
#define OUT_ACC  1127428915
#define DC_R     2144672558                         /* 1 - 2 pi 10 / 48000, Q31 */
#define ATK      32                                 /* fondu d'entree en echantillons (~0,7 ms) */
#define ATK_SH   5                                  /* log2(ATK) */

struct wt {
	u32 ph, dt, seen;
	s32 env, cpos, pos, pprev, frames, dcx, dcy, atk;
	s32 s0, s1, s2, s3;
	s32 G, c1, c2, c3, c4, P1, D1, Ps, Ds, Qs, kq8, og, xg;
};
#ifdef HOST
static struct wt tracks[6];
static inline struct wt *track_of(const char *v) { return &tracks[*(const s32 *)(v + 0x300)]; }
#else
static struct wt tracks[6];
static inline struct wt *track_of(const char *v) { return &tracks[((u32)v - CYC_VOICE0) / CYC_VSTRIDE]; }
#endif
static inline s32 knob(s16 x) { s32 k = x >> 8; return k < 0 ? 0 : k > 127 ? 127 : k; }
static inline u32 mag(s32 x) { return x < 0 ? -(u32)x : (u32)x; }
static inline s32 shl_sat(s32 x, int sh)
{
	s32 lim = Q31MAX >> sh;
	return x > lim ? Q31MAX : x < -lim ? -Q31MAX : x << sh;
}
static s32 recip_q28(s32 d)
{
	int sh = 0;
	s32 r, e;
	while (d < 0x40000000) {
		d <<= 1;
		sh++;
	}
	r = 1515870810 - (qmul(d, 2021161080) >> 1);
	for (int i = 0; i < 3; i++) {
		e = (1 << 30) - qmul(d, r);
		r = qmul(r, e) << 2;
	}
	if (sh == 0)
		return r >> 1;
	return r >= (Q31MAX >> (sh - 1)) ? Q31MAX : r << (sh - 1);
}

static inline s32 idle(const char *v)
{
	return !V32(0x34) && !V32(0x38) && mag(V32(0x230)) < IDLE_LEVEL && mag(V32(0x234)) < IDLE_LEVEL;
}

void wt_update(s32 pmod, char *v, const char *p)
{
	struct wt *a = track_of(v);
	int t = a - tracks;
	s32 acc = P16(0x1e) != 0, dec = knob(P16(0x24));
	s32 col8 = P16(0x16), shape = knob(P16(0x18)), cut8 = P16(0x1a), res = knob(P16(0x1c)), epos = knob(P16(0x36));
	s32 n, oct, r, i, fr, slot, pend, pf, mod;
	u32 d;

	if (V32(MARK_OFF) != MARK) {                    /* 1re note sur cette machine */
		a->ph = 0;
		a->env = 0;
		a->s0 = a->s1 = a->s2 = a->s3 = 0;
		a->dcx = a->dcy = 0;
		V32(MARK_OFF) = MARK;
	}
	a->seen = CLOCK;
	if (V32(0x38))                                  /* nouvelle note : fondu d'entree (anti-clic) */
		a->atk = ATK;
	/* chaine d'ampli d'origine, comme Acid */
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
		a->env = Q31MAX;
	}
	/* le sample en attente de Model-TG : pris a la note, ou voix muette (comme son sampler_pre) */
	pend = TRACK_PEND[t];
	if (pend >= 0 && (V32(0x38) || idle(v))) {
		TRACK_SLOT[t] = (s16)pend;
		TRACK_PEND[t] = -1;
	}
	slot = TRACK_SLOT[t];
	/* table pre-travailee : F trames, la longueur totale est F x S_TOTAL ; sinon rien a jouer */
	if (slot >= 0 && slot < 64 && SLOT_HASH[slot]) {
		u32 count = SLOT_COUNT[slot];
		u32 f = count / S_TOTAL;
		a->frames = (count % S_TOTAL == 0 && f >= 1 && f <= 256) ? (s32)f : 0;
	} else {
		a->frames = 0;
	}

	/* note (comme Acid) */
	n = ((s32)P16(0x14) << 8) + (((s32)P16(0x22) - 0x4000) << 3) - (64 << 16) + pmod;
	n = n < 0 ? 0 : n > (127 << 16) ? (127 << 16) : n;
	oct = n / (12 << 16);
	r = n - oct * (12 << 16);
	i = r >> 12;
	fr = r & 0xfff;
	d = (PITCH_TAB[i] + (((PITCH_TAB[i + 1] - PITCH_TAB[i]) * (u32)fr) >> 12)) << oct;
	a->dt = d;
	/* copie : une par octave au-dessus de COPY_N0 (Q16), Q16 */
	a->cpos = (n - COPY_N0) / 12;
	a->cpos = a->cpos < 0 ? 0 : a->cpos > ((NCOPY - 1) << 16) - 1 ? ((NCOPY - 1) << 16) - 1 : a->cpos;

	/* position : COLOR + Env Pos / 127 x enveloppe, sur toute la table ; Q16 de trame */
	col8 = col8 < 0 ? 0 : col8 > (127 << 8) ? (127 << 8) : col8;
	pf = (col8 << 7) / 127                          /* Q15 */
	     + ((epos * 258 * (a->env >> 16)) >> 15);
	pf = pf < 0 ? 0 : pf > 32767 ? 32767 : pf;
	a->pprev = a->pos;                              /* glisse depuis la fin du bloc d'avant... */
	a->pos = a->frames > 1 ? pf * (a->frames - 1) * 2 : 0;
	if (V32(0x38) || a->pprev >= (a->frames << 16))
		a->pprev = a->pos;                      /* ...sauf a la note */
	mod = ((shape - 64) * 24576 / 63 * (a->env >> 16)) >> 15;   /* enveloppe -> coupure : +-6 octaves */
	a->env = qmul(a->env, FDEC_TAB[dec]);

	/* passe-bas d'Acid : SWEEP 0..127 = 20 Hz -> 20 kHz (pas de 1/16 d'octave au-dessus de 10 Hz, Q8) */
	cut8 = cut8 < 0 ? 0 : cut8 > (127 << 8) ? (127 << 8) : cut8;
	i = 4096 + cut8 * 40832 / (127 << 8) + mod;
	i = i < 0 ? 0 : i > (G_TAB_N - 1) * 256 - 1 ? (G_TAB_N - 1) * 256 - 1 : i;
	{
		int gi = i >> 8;
		s32 G = G_TAB[gi] + qmul(G_TAB[gi + 1] - G_TAB[gi], (i & 255) << 23);
		s32 i1g = Q31MAX - G, G2 = qmul(G, G), G3 = qmul(G2, G), G4 = qmul(G3, G);
		s32 kq8 = res * 9089028, kG4;
		if (acc)
			kq8 += kq8 / 10;
		kG4 = qmul(kq8, G4);
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
		a->og = qmul((1 << 28) + (kq8 >> 1), acc ? OUT_ACC : OUT_GAIN);
		a->xg = acc ? 1932735283 : 1073741824;
	}
}

/* une lecture : trame de 2^lg points en base, phase ph, interpolation lineaire */
static inline s32 at(const s16 *base, int lg, u32 ph)
{
	u32 m = (1u << lg) - 1, k = ph >> (32 - lg);
	s32 f = (s32)((ph << lg) >> 19), x0 = base[k], x1 = base[(k + 1) & m];
	return x0 + (((x1 - x0) * f) >> 13);
}

void wt_render(s32 *out, char *v)
{
	struct wt *a = track_of(v);
	int t = a - tracks;
	s32 slot = TRACK_SLOT[t], lg[2], F = a->frames;
	const s16 *cb[2], *base;
	u32 ph = a->ph, dt = a->dt;
	s32 s0 = a->s0, s1 = a->s1, s2 = a->s2, s3 = a->s3;
	s32 G = a->G, c1 = a->c1, c2 = a->c2, c3 = a->c3, c4 = a->c4;
	s32 P1 = a->P1, D1 = a->D1, Ps = a->Ps, Ds = a->Ds, Qs = a->Qs, kq8 = a->kq8, og = a->og, xg = a->xg;
	s32 dcx = a->dcx, dcy = a->dcy;
	s32 ps, dp, cw, c0;
	int k;

	if ((!V32(0x34) && !V32(0x38) && mag(V32(0x230)) < IDLE_LEVEL && mag(V32(0x234)) < IDLE_LEVEL)
	    || slot < 0 || slot >= 64 || !F) {
		for (int j = 0; j < 32; j++)
			out[j] = 0;
		return;
	}
	base = SAMPLE(SLOT_BASE[slot] + HDR);
	ps = a->pprev;                                  /* position glissee echantillon par echantillon */
	dp = (a->pos - a->pprev) >> 5;
	c0 = a->cpos >> 16;
	cw = (a->cpos & 0xffff) >> 3;
	for (k = 0; k < 2; k++) {
		int c = c0 + k;
		cb[k] = base + OFF[c] * F;              /* OFF : points par trame depuis le debut du fichier */
		lg[k] = LGC[c];
	}
	for (int j = 0; j < 32; j++) {
		s32 p0, p1, pw, x0, y0, x;
		ps += dp;
		p0 = ps >> 16;
		p1 = p0 + 1 < F ? p0 + 1 : p0;
		pw = (ps & 0xffff) >> 3;                /* Q13 */
		x0 = at(cb[0] + (p0 << lg[0]), lg[0], ph);
		y0 = at(cb[0] + (p1 << lg[0]), lg[0], ph);
		x = x0 + (((y0 - x0) * pw) >> 13);
		if (cw) {
			s32 x1 = at(cb[1] + (p0 << lg[1]), lg[1], ph), y1 = at(cb[1] + (p1 << lg[1]), lg[1], ph);
			s32 z = x1 + (((y1 - x1) * pw) >> 13);
			x += ((z - x) * cw) >> 13;
		}
		ph += dt;
		x = qmul(x << 12, xg);                  /* Q27 */
		dcy = x - dcx + qmul(dcy, DC_R);        /* coupe le continu (~10 Hz) */
		dcx = x;
		x = dcy;
		{
			s32 S = qmac4(c1, s0, c2, s1, c3, s2, c4, s3);
			s32 y = qmac2(P1, x, D1, S), fb, u, w, y0_, y1_, y2_;
			if (y >= T1 || y <= -T1) {
				int neg = y < 0;
				y = qmac2(Ps, x, Ds, S) + (neg ? Qs : -Qs);
				if (mag(y) < T2)
					fb = qmul(KNEE_S, y) + (neg ? -B2_Q27 : B2_Q27);
				else
					fb = neg ? -B3_Q27 : B3_Q27;
			} else {
				fb = y;
			}
			u = x - (qmul(kq8, fb) << 3);
			w = qmul(u - s0, G);  y0_ = w + s0;  s0 = y0_ + w;
			w = qmul(y0_ - s1, G); y1_ = w + s1; s1 = y1_ + w;
			w = qmul(y1_ - s2, G); y2_ = w + s2; s2 = y2_ + w;
			w = qmul(y2_ - s3, G); y = w + s3;   s3 = y + w;
			out[j] = shl_sat(qmul(y, og), 7);
			if (a->atk > 0) {                       /* fondu d'entree : evite le clic au declenchement */
				out[j] = (out[j] >> ATK_SH) * (ATK - a->atk);
				a->atk--;
			}
		}
	}
	a->ph = ph;
	a->s0 = s0; a->s1 = s1; a->s2 = s2; a->s3 = s3;
	a->dcx = dcx; a->dcy = dcy;
#ifdef HOST
	host_amp(out, v);
#else
	AMP_ENV(v);
	VCA(out, v);
	PUNCH(out, v);
#endif
}
