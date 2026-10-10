/*
 * Wave : machine ajoutee du Model:Cycles avec Model-TG (OS 1.13), qui joue une table d'ondes de l'utilisateur
 * (notes/52). Moteur en virgule fixe.
 *
 * Table : le fichier que Model-TG a charge pour la piste (track_slot -> slot_base, slot_count ; en-tete de 64 o, puis
 * 16 bits gros-boutiens) ; trames de 2048 points (moins pour un fichier plus court : un seul cycle).
 * Copies par demi-octave (notes/52 §4) : preparees hors de l'audio (wt_tick, tache des LED, une etape par bloc), dans
 * la SDRAM libre au-dessus de Model-TG (POOL, partagee entre les pistes) ; tant qu'elles manquent, la table brute.
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
extern char *host_copies, *host_scratch, *host_mem;
extern u32 host_clock;
#define TRACK_SLOT host_track_slot
#define TRACK_PEND host_track_pend
#define SLOT_HASH  ((u32 *)host_slot)
#define SLOT_BASE  ((u32 *)host_slot + 64)
#define SLOT_COUNT ((u32 *)host_slot + 128)
#define POOL       ((s16 *)host_copies)
#define SCRATCH    ((s32 *)host_scratch)
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
#define POOL       ((s16 *)COPIES_AT)
#define SCRATCH    ((s32 *)SCRATCH_AT)
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
#define MAXN_LOG   11                               /* trames de 2048 points au plus */
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

/* copies d'une piste (wt_tick) : off[c] < 0 = table brute ; ready : copies deja faites, un bit par copie */
struct copies {
	u32 hash, ready;
	s32 off[NCOPY];
	s8 lg[NCOPY];
};
struct wt {
	u32 ph, dt, seen;
	s32 env, cpos, pos, pprev, frames, lgn, dcx, dcy;
	s32 ai;                                     /* allocation des copies + 1, 0 : aucune */
	s32 s0, s1, s2, s3;
	s32 G, c1, c2, c3, c4, P1, D1, Ps, Ds, Qs, kq8, og, xg;
	struct copies cp;
};
#define PF 6                                        /* pseudo-piste : la table sous le curseur du navigateur */
#ifdef HOST
static struct wt tracks[7];
static inline struct wt *track_of(const char *v) { return &tracks[*(const s32 *)(v + 0x300)]; }
#else
static struct wt tracks[7];
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

/* trames de la case : lg2 de leur longueur (0 : rien a jouer) et leur nombre */
static int layout(u32 count, s32 *frames)
{
	int lg = MAXN_LOG;
	while (lg > 5 && (1u << lg) > count)
		lg--;
	if ((1u << lg) > count) {
		*frames = 0;
		return 0;
	}
	*frames = count >> lg;
	if (*frames > 256)
		*frames = 256;
	return lg;
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
	s32 n, oct, r, i, fr, idx, slot, pend, pf, mod;
	u32 d;

	if (V32(MARK_OFF) != MARK) {                    /* 1re note sur cette machine */
		a->ph = 0;
		a->env = 0;
		a->s0 = a->s1 = a->s2 = a->s3 = 0;
		a->dcx = a->dcy = 0;
		V32(MARK_OFF) = MARK;
	}
	a->seen = CLOCK;
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
	a->lgn = slot >= 0 && slot < 64 && SLOT_HASH[slot] ? layout(SLOT_COUNT[slot], &a->frames) : 0;

	/* note (comme Acid) */
	n = ((s32)P16(0x14) << 8) + (((s32)P16(0x22) - 0x4000) << 3) - (64 << 16) + pmod;
	n = n < 0 ? 0 : n > (127 << 16) ? (127 << 16) : n;
	oct = n / (12 << 16);
	r = n - oct * (12 << 16);
	i = r >> 12;
	fr = r & 0xfff;
	d = (PITCH_TAB[i] + (((PITCH_TAB[i + 1] - PITCH_TAB[i]) * (u32)fr) >> 12)) << oct;
	a->dt = d;
	/* copie : 2 par octave au-dessus de COPY_N0 (Q16), Q16 */
	a->cpos = (n - COPY_N0) / 6;
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
	idx = 4096 + cut8 * 40832 / (127 << 8) + mod;
	idx = idx < 0 ? 0 : idx > (G_TAB_N - 1) * 256 - 1 ? (G_TAB_N - 1) * 256 - 1 : idx;
	i = idx >> 8;
	{
		s32 G = G_TAB[i] + qmul(G_TAB[i + 1] - G_TAB[i], (idx & 255) << 23);
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

/* une lecture : trame de 2^lg points en base, phase ph, interpolation lineaire ; copies a mi-niveau : << sh */
static inline s32 at(const s16 *base, int lg, int sh, u32 ph)
{
	u32 m = (1u << lg) - 1, k = ph >> (32 - lg);
	s32 f = (s32)((ph << lg) >> 19), x0 = base[k] << sh, x1 = base[(k + 1) & m] << sh;
	return x0 + (((x1 - x0) * f) >> 13);
}

void wt_render(s32 *out, char *v)
{
	struct wt *a = track_of(v);
	int t = a - tracks;
	s32 slot = TRACK_SLOT[t], lg[2], sh[2], lgn = a->lgn;
	const s16 *cb[2];
	u32 ph = a->ph, dt = a->dt;
	s32 s0 = a->s0, s1 = a->s1, s2 = a->s2, s3 = a->s3;
	s32 G = a->G, c1 = a->c1, c2 = a->c2, c3 = a->c3, c4 = a->c4;
	s32 P1 = a->P1, D1 = a->D1, Ps = a->Ps, Ds = a->Ds, Qs = a->Qs, kq8 = a->kq8, og = a->og, xg = a->xg;
	s32 dcx = a->dcx, dcy = a->dcy;
	s32 ps, dp, cw, c0;
	const s16 *raw;
	int k;

	if ((!V32(0x34) && !V32(0x38) && mag(V32(0x230)) < IDLE_LEVEL && mag(V32(0x234)) < IDLE_LEVEL)
	    || slot < 0 || slot >= 64 || !lgn || !a->frames) {
		for (int j = 0; j < 32; j++)
			out[j] = 0;
		return;
	}
	raw = SAMPLE(SLOT_BASE[slot] + HDR);
	ps = a->pprev;                                  /* position glissee echantillon par echantillon */
	dp = (a->pos - a->pprev) >> 5;
	c0 = a->cpos >> 16;
	cw = (a->cpos & 0xffff) >> 3;
	for (k = 0; k < 2; k++) {
		int c = c0 + k;
		if (a->cp.hash == SLOT_HASH[slot] && (a->cp.ready >> c & 1)) {
			cb[k] = POOL + a->cp.off[c];
			lg[k] = a->cp.lg[c];
			sh[k] = 1;
		} else {
			cb[k] = raw;
			lg[k] = lgn;
			sh[k] = 0;
		}
	}
	for (int j = 0; j < 32; j++) {
		s32 p0, p1, pw, x0, y0, x;
		ps += dp;
		p0 = ps >> 16;
		p1 = p0 + 1 < a->frames ? p0 + 1 : p0;
		pw = (ps & 0xffff) >> 3;                /* Q13 */
		x0 = at(cb[0] + (p0 << lg[0]), lg[0], sh[0], ph);
		y0 = at(cb[0] + (p1 << lg[0]), lg[0], sh[0], ph);
		x = x0 + (((y0 - x0) * pw) >> 13);
		if (cw) {
			s32 x1 = at(cb[1] + (p0 << lg[1]), lg[1], sh[1], ph), y1 = at(cb[1] + (p1 << lg[1]), lg[1], sh[1], ph);
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

/* ---- copies : hors de l'audio (wt_tick), multiplications entieres seulement (pas d'EMAC) ---------------- */
#define POOL_N   (POOL_BYTES / 2)                   /* points de la reserve */
#define BUDGET   3072                               /* papillons par etape (~0,6 ms) */

/* x * w / 2^15, w en Q15 : exact sur 32 bits pour |x| < 2^30 */
static inline s32 m15(s32 x, s32 w) { return (x >> 15) * w + (((x & 0x7fff) * w) >> 15); }

static void bitrev(s32 *re, s32 *im, int lg)
{
	int n = 1 << lg;
	for (int i = 1, j = 0; i < n; i++) {
		int bit = n >> 1;
		for (; j & bit; bit >>= 1)
			j ^= bit;
		j ^= bit;
		if (i < j) {
			s32 x = re[i]; re[i] = re[j]; re[j] = x;
			x = im[i]; im[i] = im[j]; im[j] = x;
		}
	}
}

/* etages s.. d'une FFT de 2^lg points (apres bitrev), tant qu'il reste du budget ; rend l'etage suivant.
 * directe : / 2 par etage (sortie = X / N) ; inverse : sans echelle */
static int stages(s32 *re, s32 *im, int lg, int inv, int s, int *budget)
{
	int n = 1 << lg;
	for (; s <= lg && *budget > 0; s++, *budget -= n >> 1) {
		int half = 1 << (s - 1), step = 1 << (MAXN_LOG - s);
		for (int k = 0; k < half; k++) {
			s32 wr = COS_TAB[k * step], wi = inv ? SIN_TAB[k * step] : -SIN_TAB[k * step];
			for (int i = k; i < n; i += half << 1) {
				int j = i + half;
				s32 tr = m15(re[j], wr) - m15(im[j], wi), ti = m15(re[j], wi) + m15(im[j], wr);
				if (inv) {
					re[j] = re[i] - tr; im[j] = im[i] - ti;
					re[i] += tr; im[i] += ti;
				} else {
					re[j] = (re[i] - tr) >> 1; im[j] = (im[i] - ti) >> 1;
					re[i] = (re[i] + tr) >> 1; im[i] = (im[i] + ti) >> 1;
				}
			}
		}
	}
	return s;
}

/* reserve partagee : une allocation par table (les pistes sur la meme table la partagent) */
static struct { u32 hash, off, size; s32 refs; } al[7];

static void release(int t)
{
	struct wt *a = &tracks[t];
	a->cp.hash = 0;
	a->cp.ready = 0;
	if (a->ai) {
		if (--al[a->ai - 1].refs <= 0)
			al[a->ai - 1].size = al[a->ai - 1].refs = 0;
		a->ai = 0;
	}
}

/* premier trou de size points, ou -1 */
static s32 gap(u32 size)
{
	u32 at = 0;
	for (int moved = 1; moved;) {
		moved = 0;
		for (int i = 0; i < 7; i++)
			if (al[i].size && at < al[i].off + al[i].size && al[i].off < at + size) {
				at = al[i].off + al[i].size;
				moved = 1;
			}
	}
	return at + size <= POOL_N ? (s32)at : -1;
}

/* place des copies (en points, depuis 0) : over points par harmonique, de 64 a 2^lgn ; rend le total */
static u32 plan(struct copies *cp, int lgn, s32 frames, int over)
{
	u32 total = 0;
	for (int c = 0; c < NCOPY; c++) {
		int lg = 6;
		if (HMAX[c] >= (1 << (lgn - 1))) {
			cp->off[c] = -1;                /* toutes les harmoniques : la table brute */
			continue;
		}
		while (lg < lgn && (1 << lg) < over * HMAX[c])
			lg++;
		cp->lg[c] = lg;
		cp->off[c] = total;
		total += (u32)frames << lg;
	}
	return total;
}

enum { LOAD, FWD, SPLIT, BUILD, INV, STORE };
#define CHEAP_LG 9                                  /* copies de 512 points au plus : les notes aigues, vite faites */
/* travail en cours : une piste a la fois, deux trames par FFT (l'une reelle, l'autre imaginaire) ; deux passes :
 * d'abord les petites copies (les aigus, ou le repli s'entend), puis les grandes */
static struct {
	s32 on, t, slot, lgn, frames, i, c, stage, s, pass;
	u32 hash, wait, mask[2];
	struct copies cp;
} job;

static void start(int t, int slot)
{
	static const s8 over[3] = { 8, 4, 2 };
	u32 total = 0;
	s32 at = -1, k;
	release(t);                                     /* la voix reprend la table brute... */
	job.t = t;
	job.slot = slot;
	job.hash = SLOT_HASH[slot];
	job.lgn = layout(SLOT_COUNT[slot], &job.frames);
	job.on = 0;
	if (job.lgn < 7)
		return;                                 /* trop courte : la table brute */
	for (k = 0; k < 3 && at < 0; k++) {
		total = plan(&job.cp, job.lgn, job.frames, over[k]);
		at = gap(total);
	}
	if (at < 0)
		return;                                 /* reserve pleine : la table brute */
	for (k = 0; k < 7 && al[k].size; k++)
		;
	if (k == 7)
		return;
	al[k].hash = job.hash;
	al[k].off = at;
	al[k].size = total;
	al[k].refs = 1;
	tracks[t].ai = k + 1;
	{
		struct copies *cp = &tracks[t].cp;
		job.mask[0] = job.mask[1] = 0;
		for (int c = 0; c < NCOPY; c++) {
			if (job.cp.off[c] >= 0)
				job.cp.off[c] += at;
			cp->off[c] = job.cp.off[c];
			cp->lg[c] = job.cp.lg[c];
			if (job.cp.off[c] >= 0)
				job.mask[job.cp.lg[c] <= CHEAP_LG ? 0 : 1] |= 1u << c;
		}
		cp->hash = job.hash;                    /* rien de pret : la voix lit la table brute */
	}
	job.i = 0;
	job.pass = job.mask[0] ? 0 : 1;
	job.stage = LOAD;
	job.on = 1;
	job.wait = CLOCK;                               /* ...des le bloc suivant, avant qu'on ecrive */
}

/* une passe finie : ses copies servent des le bloc suivant */
static void publish(void)
{
	tracks[job.t].cp.ready |= job.mask[job.pass];
	if (job.pass == 0 && job.mask[1]) {
		job.pass = 1;
		job.i = 0;
		job.stage = LOAD;
	} else {
		job.on = 0;
	}
}

/* une etape : environ BUDGET papillons */
static void step(void)
{
	s32 *ar = SCRATCH, *ai = ar + 2048, *x1r = ai + 2048, *x1i = x1r + 1025, *x2r = x1i + 1025, *x2i = x2r + 1025;
	s32 *wr = x2i + 1025, *wi = wr + 2048;
	int n = 1 << job.lgn, budget = BUDGET;

	while (budget > 0 && job.on) {
		int c = job.c, lg = c < NCOPY ? job.cp.lg[c] : 0, m = 1 << lg;
		switch (job.stage) {
		case LOAD: {                            /* trames i et i + 1, lues pendant que le fichier est la */
			const s16 *src;
			if (SLOT_HASH[job.slot] != job.hash) {
				release(job.t);
				job.on = 0;
				return;
			}
			src = SAMPLE(SLOT_BASE[job.slot] + HDR) + (job.i << job.lgn);
			for (int k = 0; k < n; k++) {
				ar[k] = (s32)src[k] << 12;
				ai[k] = job.i + 1 < job.frames ? (s32)src[k + n] << 12 : 0;
			}
			bitrev(ar, ai, job.lgn);
			job.s = 1;
			job.stage = FWD;
			budget -= n >> 1;
			break;
		}
		case FWD:
			job.s = stages(ar, ai, job.lgn, 0, job.s, &budget);
			if (job.s > job.lgn)
				job.stage = SPLIT;
			break;
		case SPLIT:                             /* les deux spectres : X1 = (Z + Z*) / 2, X2 = (Z - Z*) / 2j */
			for (int k = 0; k <= n / 2; k++) {
				int r = (n - k) & (n - 1);
				x1r[k] = (ar[k] + ar[r]) >> 1;
				x1i[k] = (ai[k] - ai[r]) >> 1;
				x2r[k] = (ai[k] + ai[r]) >> 1;
				x2i[k] = (ar[r] - ar[k]) >> 1;
			}
			job.c = 0;
			job.stage = BUILD;
			budget -= n >> 1;
			break;
		case BUILD: {                           /* W = Y1 + j Y2, sans le continu : une FFT inverse, deux trames */
			int h;
			while (job.c < NCOPY && !(job.mask[job.pass] >> job.c & 1))
				job.c++;
			if (job.c >= NCOPY) {
				job.i += 2;
				if (job.i >= job.frames)
					publish();
				else
					job.stage = LOAD;
				break;
			}
			c = job.c;
			lg = job.cp.lg[c];
			m = 1 << lg;
			h = HMAX[c] < m / 2 - 1 ? HMAX[c] : m / 2 - 1;
			for (int k = 0; k < m; k++)
				wr[k] = wi[k] = 0;
			for (int k = 1; k <= h; k++) {
				wr[k] = x1r[k] - x2i[k];     wi[k] = x1i[k] + x2r[k];
				wr[m - k] = x1r[k] + x2i[k]; wi[m - k] = x2r[k] - x1i[k];
			}
			bitrev(wr, wi, lg);
			job.s = 1;
			job.stage = INV;
			budget -= m >> 1;
			break;
		}
		case INV:
			job.s = stages(wr, wi, lg, 1, job.s, &budget);
			if (job.s > lg)
				job.stage = STORE;
			break;
		case STORE: {                           /* a mi-niveau : place pour le depassement */
			s16 *d0 = POOL + job.cp.off[c] + (job.i << lg), *d1 = d0 + m;
			for (int k = 0; k < m; k++) {
				s32 y = (wr[k] + (1 << 12)) >> 13;
				d0[k] = y > 32767 ? 32767 : y < -32768 ? -32768 : y;
				if (job.i + 1 < job.frames) {
					y = (wi[k] + (1 << 12)) >> 13;
					d1[k] = y > 32767 ? 32767 : y < -32768 ? -32768 : y;
				}
			}
			job.c++;
			job.stage = BUILD;
			budget -= m >> 1;
			break;
		}
		}
	}
}

/* la case que la piste joue, ou jouera a la prochaine note */
static int want(int t)
{
	s32 p = TRACK_PEND[t];
	if (p >= 0 && (s16)p >= 0)
		return (s16)p;
	return TRACK_SLOT[t];
}

static u32 failed;                                  /* table sans copies possibles : ne plus essayer */

/* navigateur (wt_cursor, notes/52) : le fichier sous le curseur, sur la piste de Wave, et quand */
volatile u32 wt_pf_hash, wt_pf_size, wt_pf_clock;
static u32 pf_done;
#define DEBOUNCE 450                                /* blocs : 300 ms sans bouger */
#define PF_MAX   (4 << 20)                          /* au-dela, pas de chargement d'avance */

/* charge la table par Model-TG, poliment (pd_mode 1 : ne chasse que l'inutile) ; rend la case, ou -1 */
static s32 tg_load(u32 hash)
{
#ifdef HOST
	return host_load(hash);
#else
	register s32 d0 __asm__("d0") = hash;
	*(volatile s32 *)TG_PD_MODE = 1;
	__asm__ volatile("jsr " TG_ENSURE_LOADED_S
			 : "+d"(d0) : : "d1", "d5", "d6", "d7", "a0", "a1", "a3", "a4", "a5", "memory", "cc");
	*(volatile s32 *)TG_PD_MODE = 0;
	return d0;
#endif
}

/* la piste t prend les copies de la pseudo-piste (faites ou en cours) */
static void adopt(int t)
{
	struct wt *a = &tracks[t], *p = &tracks[PF];
	release(t);
	for (int c = 0; c < NCOPY; c++) {
		a->cp.off[c] = p->cp.off[c];
		a->cp.lg[c] = p->cp.lg[c];
	}
	a->ai = p->ai;
	a->cp.ready = p->cp.ready;
	a->cp.hash = p->cp.hash;
	p->ai = 0;
	p->cp.hash = p->cp.ready = 0;
	if (job.on && job.t == PF)
		job.t = t;
}

/* tache des LED de Model-TG, une fois par bloc audio, niveau 0 (led_hook) */
void wt_tick(void)
{
	u32 now = CLOCK;
	for (int t = 0; t < 6; t++)                     /* plus notre machine depuis ~5 s : copies rendues */
		if (tracks[t].ai && now - tracks[t].seen > 8192 && !(job.on && job.t == t))
			release(t);
	for (int t = 0; t < 6; t++) {                   /* le fichier choisi : celui qu'on preparait */
		int s;
		if (now - tracks[t].seen > 2048 || !tracks[PF].cp.hash)
			continue;
		s = want(t);
		if (s >= 0 && s < 64 && SLOT_HASH[s] == tracks[PF].cp.hash && tracks[t].cp.hash != tracks[PF].cp.hash) {
			adopt(t);
			return;
		}
	}
	if (job.on) {
		int ok;
		if (job.t == PF) {
			ok = job.hash == wt_pf_hash;
		} else {
			int s = want(job.t);
			ok = s >= 0 && s < 64 && SLOT_HASH[s] == job.hash;
		}
		if (!ok) {
			if (job.t == PF)
				pf_done = 0;            /* le curseur revient : on recommencera */
			release(job.t);
			job.on = 0;
			return;
		}
		if (now != job.wait)
			step();
		return;
	}
	for (int t = 0; t < 6; t++) {
		int s;
		u32 h;
		if (now - tracks[t].seen > 2048)          /* pas notre machine depuis ~1,4 s */
			continue;
		s = want(t);
		if (s < 0 || s >= 64 || !(h = SLOT_HASH[s]) || tracks[t].cp.hash == h || h == failed)
			continue;
		for (int u = 0; u < 7; u++) {           /* deja faites pour une autre piste : partagees */
			if (u == t || tracks[u].cp.hash != h || !tracks[u].ai)
				continue;
			release(t);
			for (int c = 0; c < NCOPY; c++) {
				tracks[t].cp.off[c] = tracks[u].cp.off[c];
				tracks[t].cp.lg[c] = tracks[u].cp.lg[c];
			}
			tracks[t].ai = tracks[u].ai;
			al[tracks[t].ai - 1].refs++;
			tracks[t].cp.hash = h;
			tracks[t].cp.ready = tracks[u].cp.ready;
			return;
		}
		start(t, s);
		if (!job.on)
			failed = h;
		return;
	}
	/* rien a faire pour les pistes : le fichier sous le curseur, apres 300 ms */
	if (wt_pf_hash && wt_pf_hash != pf_done && now - wt_pf_clock > DEBOUNCE && wt_pf_size < PF_MAX) {
		u32 h = pf_done = wt_pf_hash;
		s32 s = tg_load(h);
		if (s >= 0 && s < 64 && SLOT_HASH[s] == h && tracks[PF].cp.hash != h)
			start(PF, s);
	}
}

#ifdef HOST
/* banc : copies pretes de la piste t */
u32 wt_ready(int t) { return tracks[t].cp.hash ? tracks[t].cp.ready : 0; }
u32 wt_hash(int t) { return tracks[t].cp.hash; }
#endif
