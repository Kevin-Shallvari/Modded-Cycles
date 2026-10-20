/* Step record (notes/73): with the sequencer stopped, a double press on REC starts it. Each note played (TRIG keys
 * in chromatic mode on the active track, pads T1-T6 on their own track, a MIDI keyboard) is written on the current
 * step; the notes held together go on the same step, which moves on when the last one is released. PLAY skips a
 * step, STOP goes back one, REC leaves; it also ends after the last step of the track. The current step blinks fast.
 *
 * Knobs turned before a note: the trig gets their values as p-locks, the next notes too, until they are turned
 * again. The sound changes as usual (it is heard), and goes back to what it was when step record ends.
 *
 * Everything runs in the interface task, through the OS's own functions:
 *   - keys: the transport keys' handler (0x4002439a, REC 9, PLAY 10, STOP 11), sr_key in step_rec_hooks.S;
 *   - notes: every note played posts a message to the interface (0x4008171e, 0x4008145e); its handler
 *     (0x40007000) gives notes to live record only while it runs (0x4006ba76): sr_on and sr_off take them before;
 *   - trig: as live record writes one (0x40012158), on our step instead of the playing one;
 *   - knobs: a change made by the user reaches the setter 0x4000ba7a with its "record" flag set (the flag that makes
 *     live record lock it, 0x4000f4b8): sr_set notes the word of the sound before it is written;
 *   - lights: posted first in each frame of the lights (0x40006a76), before the views; the 30 Hz tick (0x400081e4)
 *     blinks them and leaves step record if the sequencer starts, grid record is on, or the pattern changes.
 */
typedef unsigned char u8;
typedef signed char s8;
typedef short s16;
typedef unsigned int u32;
typedef int s32;

#define FN(a, r, ...)  ((r (*)(__VA_ARGS__))(a))
#define NEW(n)         FN(0x400802e0, void *, u32)(n)
#define PROJECT()      FN(0x400cf866, void *, void)()
#define UISTATES()     FN(0x400cf9a8, void *, void)()
#define LEDS()         FN(0x400cfaf4, void *, void)()
#define SEQ_STATE()    FN(0x4005481a, u32, void)()                    /* 1: playing */
#define PATTERN(p)     FN(0x4000f208, void *, void *)(p)
#define TRACK(pat, t)  FN(0x4000cfcc, void *, void *, s32)(pat, t)
#define ACTIVE(p)      FN(0x40012412, s32, void *)(FN(0x4000eb90, void *, void *)(p))
#define TRK_LEN(trk)   FN(0x40016402, s32, void *)(trk)
#define HAS_TRIG(trk, s) (u8)FN(0x40015c20, u32, void *, s32)(trk, s)
#define PLACE(trk, s)  FN(0x40017b48, void, void *, s32, s32)(trk, s, 1)
#define SET_NOTE(trk, s, v)  FN(0x40016642, void, void *, s32, s32)(trk, s, v)
#define SET_VEL(trk, s, v)   FN(0x400166c2, void, void *, s32, s32)(trk, s, v)
#define SET_MICRO(trk, s, v) FN(0x400167bc, void, void *, s32, s32)(trk, s, v)
#define SET_LOCK(trk, s, k, v) FN(0x4001646a, u32, void *, s32, s32, s32)(trk, s, k, v)
#define GRID_ON(ui)    (u8)FN(0x4006b978, u32, void *)(ui)
#define GRID_SET(ui, v) FN(0x4006b9f6, void, void *, s32)(ui, v)
#define LIVE_SET(ui, v) FN(0x4006ba90, void, void *, s32)(ui, v)
#define PATTERN_SELECT(ui) (u8)FN(0x4006bb18, u32, void *)(ui)
#define HELD(code)     (u8)FN(0x4007faf4, u32, s32)(code)
#define LED(obj, l, s) FN(0x40005f86, void, void *, s32, s32, u32)(obj, l, s, 0x404a8cb8)
#define STEP_LED(i)    FN(0x4000608c, s32, s32)(i)
#define PAGE_LED(i)    FN(0x400060ac, s32, s32)(i)
#define LEDS_DIRTY(vc) FN(0x40076c04, void, void *)(vc)
#define STRING(s, t, a) FN(0x400f980c, void, void *, const char *, void *)(s, t, a)
#define STRING_DTOR(s) FN(0x400f7d5c, void, void *)(s)
#define POPUP(obj, s)  FN(0x400747c0, void, void *, void *)(obj, s)
#define SHARED(sp, o)  FN(0x400d4082, void, u32 *, void *)(sp, o)
#define PUSH(vc, sp)   FN(0x4007700e, u32, void *, u32 *, s32)(vc, sp, 0)
#define RELEASE(c)     FN(0x400cf23c, void, u32 *)(c)

enum { K_REC = 9, K_PLAY = 10, K_STOP = 11, K_TRACK = 2, K_PATTERN = 3, K_SETTINGS = 13 };
enum { L_REC = 28 };
#define NHELD 8
#define NTOUCH 32
#define NOINLINE       __attribute__((noinline))
#define WORD(p, k)     (*(volatile s16 *)((u8 *)(p) + 20 + 2 * (k)))   /* word k of a sound (0x4000ba7a) */

struct touch {                                  /* a parameter the user changed during step record */
	u8 t, k;
	s16 old, last;                              /* its value before; the last one the user set */
};

u8 sr_active;                                   /* tested by the hooks (step_rec_hooks.S) */
static u8 cur, len, wrote, nheld, ntouch, phase, ticks;
static u8 held[NHELD][2];                       /* notes held: track, note */
static struct touch touched[NTOUCH];
static void *sound[6];                          /* the sound of each track whose parameters were changed */
static void *vc;                                /* the view controller: popups, lights */
static void *pat_in;                            /* the pattern step record started on */

NOINLINE static void popup(const char *text)
{
	u32 str, sp[2];
	u8 alloc;
	void *obj;

	if (!vc)
		return;
	STRING(&str, text, &alloc);
	obj = NEW(0x9c);
	POPUP(obj, &str);                           /* as "Live-rec:\nQuantized", 0x400245ac */
	SHARED(sp, obj);
	PUSH(vc, sp);
	RELEASE(&sp[1]);
	STRING_DTOR(&str);
}

NOINLINE static void *data_of(void *obj)                 /* vtable[10]: the sound's data, as the setter */
{
	return FN((*(void ***)obj)[10], void *, void *)(obj);
}

NOINLINE static void notify(void *obj, s32 k)            /* "word k changed", as the setter (0x4000bb04) */
{
	u32 desc[2];

	desc[0] = 0x400fd0ac;
	desc[1] = k;
	FN((*(void ***)obj)[4], void, void *, u32 *)(obj, desc);
}

/* The sounds go back to what they were: each word changed during step record, unless something else changed it
 * since (a preset loaded, for instance). */
NOINLINE static void restore(void)
{
	u32 i;

	for (i = 0; i < ntouch; i++) {
		struct touch *e = &touched[i];
		void *obj = sound[e->t];
		u8 *p;

		if (!obj || !(p = data_of(obj)) || WORD(p, e->k) != e->last)
			continue;
		WORD(p, e->k) = e->old;
		notify(obj, e->k);
	}
}

NOINLINE static void leave(u32 put_back)
{
	if (put_back)
		restore();
	sr_active = 0;
	nheld = ntouch = 0;
	popup("Step-rec:\nOFF");
	if (vc)
		LEDS_DIRTY(vc);
}

NOINLINE static void enter(void *view)
{
	void *ui = UISTATES(), *proj = PROJECT();
	u32 i;

	if (GRID_ON(ui))                            /* the first press turned grid record on */
		GRID_SET(ui, 0);
	LIVE_SET(ui, 0);
	pat_in = PATTERN(proj);
	len = TRK_LEN(TRACK(pat_in, ACTIVE(proj)));
	cur = wrote = nheld = ntouch = ticks = 0;
	phase = 1;
	for (i = 0; i < 6; i++)
		sound[i] = 0;
	vc = *(void **)((u8 *)view + 44);
	sr_active = 1;
	popup("Step-rec:\nON");
	LEDS_DIRTY(vc);
}

NOINLINE static void move(s32 d)
{
	wrote = 0;
	if (d < 0) {
		if (cur)
			cur--;
	} else if (++cur >= len) {
		leave(1);
		return;
	}
	phase = 1;
	ticks = 0;
	LEDS_DIRTY(vc);
}

/* Transport keys (sr_key): 1 = taken. With a modifier held (FUNC, TRACK, PATTERN, Model-TG's SETTINGS), the OS's. */
u32 sr_transport(s32 code, void *view, void *ev)
{
	u32 fl = *(u32 *)((u8 *)ev + 16);
	u32 press = (fl & 1) && !(fl & 8);

	if (code < K_REC || code > K_STOP || (fl & 2) || HELD(K_TRACK) || HELD(K_PATTERN) || HELD(K_SETTINGS))
		return 0;
	if (!sr_active) {
		if (code == K_REC && press && (fl & 4) && SEQ_STATE() != 1 && !PATTERN_SELECT(UISTATES())) {
			enter(view);
			return 1;
		}
		return 0;
	}
	if (press) {
		if (code == K_REC)
			leave(1);
		else if (!nheld)
			move(code == K_PLAY ? 1 : -1);
	}
	return 1;
}

/* The parameters of track t changed during step record, as p-locks on the current step (as live record locks a
 * knob turned, 0x4000f4b8). */
NOINLINE static void write_locks(void *trk, u32 t)
{
	u32 i;

	for (i = 0; i < ntouch; i++) {
		struct touch *e = &touched[i];
		u8 *p;
		s16 v;

		if (e->t != t || !sound[t] || !(p = data_of(sound[t])))
			continue;
		v = WORD(p, e->k);
		if (v != e->old)
			SET_LOCK(trk, cur, e->k, v);
	}
}

/* A note played (sr_on, message a2): written on the current step of its track, as live record writes one
 * (0x40012158: trig, note, velocity, no micro-timing). */
void sr_note_on(u8 *msg)
{
	u32 t = msg[8], i;
	s8 note = msg[16], vel = msg[17];
	void *trk;

	if (t >= 6)
		return;
	trk = TRACK(PATTERN(PROJECT()), t);
	if (!HAS_TRIG(trk, cur))
		PLACE(trk, cur);
	SET_NOTE(trk, cur, note);
	if (vel >= 0)
		SET_VEL(trk, cur, vel);
	SET_MICRO(trk, cur, 64);
	write_locks(trk, t);
	wrote = 1;
	for (i = 0; i < nheld; i++)
		if (held[i][0] == t && held[i][1] == (u8)note)
			return;
	if (nheld < NHELD) {
		held[nheld][0] = t;
		held[nheld][1] = note;
		nheld++;
	}
	LEDS_DIRTY(vc);
}

/* A note released (sr_off): when the last note held is released, the next step. */
void sr_note_off(u8 *msg)
{
	u32 i;

	for (i = 0; i < nheld; i++)
		if (held[i][0] == msg[8] && held[i][1] == msg[16])
			break;
	if (i == nheld)
		return;
	held[i][0] = held[nheld - 1][0];
	held[i][1] = held[nheld - 1][1];
	if (--nheld == 0 && wrote)
		move(1);
}

/* The setter is about to write word k of a track's sound (sr_set, change made by the user): its value before. */
void sr_touch(u8 *p, s32 k, s32 v, void *acc, s32 t)
{
	struct touch *e = 0;
	u32 i;

	if ((u32)t >= 6 || (u32)k > 32)
		return;
	for (i = 0; i < ntouch; i++)
		if (touched[i].t == t && touched[i].k == k)
			e = &touched[i];
	if (!e) {
		if (ntouch >= NTOUCH)
			return;
		e = &touched[ntouch++];
		e->t = t;
		e->k = k;
		e->old = WORD(p, k);
	}
	e->last = v;
	sound[t] = *(void **)((u8 *)acc + 4);
}

/* Lights (sr_leds), before the views post theirs (the first state posted wins, 0x40005f86): the active track's trigs
 * on the page of the current step, the current step blinking, its page blinking, REC lit. */
void sr_lights(void *ctl)
{
	void *leds = LEDS(), *proj = PROJECT();
	void *trk = TRACK(PATTERN(proj), ACTIVE(proj));
	u32 page = cur >> 4, pages = (len + 15) >> 4, i;

	vc = ctl;
	for (i = 0; i < 16; i++) {
		u32 s = page * 16 + i;

		LED(leds, STEP_LED(i), s >= len ? 1 : s == cur ? 2 - !phase : HAS_TRIG(trk, s) ? 2 : 1);
	}
	for (i = 0; i < 4; i++)
		LED(leds, PAGE_LED(i), i >= pages ? 1 : i == page ? 2 - !phase : 2);
	LED(leds, L_REC, 2);
}

/* 30 Hz (sr_tick): blink, and leave if something else took over. */
void sr_tick_c(void)
{
	void *pat = PATTERN(PROJECT());

	if (SEQ_STATE() == 1 || GRID_ON(UISTATES()) || pat != pat_in) {
		leave(pat == pat_in);
		return;
	}
	if (++ticks >= 4) {                         /* 3.75 blinks per second */
		ticks = 0;
		phase ^= 1;
		if (vc)
			LEDS_DIRTY(vc);
	}
}
