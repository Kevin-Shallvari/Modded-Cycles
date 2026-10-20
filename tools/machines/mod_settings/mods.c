/* Mod Settings (notes/72): a page of the mods' own settings in SETTINGS › CONFIG, and its first setting, the USB audio
 * output: 2CH (the stereo mix, as stock) or 6CH (the six tracks, the 6ch-usbup mod).
 *
 * Settings: a record of 16 bytes at 0x404e9b80, in the settings block the OS loads at start-up and saves after each
 * change (0x404e9b10, 272 bytes, flash offset 0x78000). The OS's checksum covers 0x404e9b18..0x404e9b62 only;
 * 0x404e9b63..0x404e9c0f is neither read nor written by the OS or by another mod. Our record has its own magic and
 * check byte; without a valid record every setting is 0, its default (USB audio: 2CH).
 *
 * USB audio: the 15 changes of 6ch-usbup to the USB driver and descriptors (mods_gen.h, from
 * tweaks/model-cycles_OS1.13/11-6ch-usbup.json) are made in memory, only in 6CH: at start-up just before the USB
 * mode is set up (usb_boot, mods_hooks.S), or when the setting changes, with the USB stopped as for a change of USB
 * mode (0x40004e04). The bytes they replace are kept first and put back for 2CH. In 2CH nothing of this code runs
 * after start-up: the driver is the OS's own, byte for byte.
 */
typedef unsigned char u8;
typedef unsigned int u32;
typedef int s32;

#include "mods_gen.h"                         /* SITES, NEW6, ICON_MODS (tools/gen_mod_settings.py) */

typedef struct {                              /* std::function of the OS: storage, manager, invoker */
	void *st0, *st1;
	u32 mgr;
	void *inv;
} fn_t;

#define NEW(n)         ((void *(*)(u32))0x400802e0)(n)
#define BITMAP         ((void (*)(void *, u32, u32, const u8 *, u32))0x40070172)
#define STRING         ((void (*)(void *, const char *, void *))0x400f980c)
#define STRING_DTOR    ((void (*)(void *))0x400f7d5c)
#define MENU_VIEW      ((void (*)(void *, const char *, u32, void *, void *))0x400406d8)
#define VIEW_KEYS      ((void (*)(void *, u32))0x4007649e)
#define ITEM           ((void (*)(void *, fn_t *, fn_t *, fn_t *, fn_t *, s32, s32))0x400734b0)
#define APPEND         ((void (*)(void *, void *))0x40072ce6)
#define FN_DTOR        ((void (*)(fn_t *))0x400cf044)
#define FN_MANAGER     0x4002cf00             /* manager of a 4-byte closure */
#define HANDLE_COPY    ((void (*)(u32 *, u32 *))0x400d807e)
#define HANDLE_RELEASE ((void (*)(u32 *))0x400cf23c)
#define VIEW_PUSH      ((void (*)(void *, u32 *))0x40075754)
#define VIEW_REDRAW    ((void (*)(void *))0x40076082)
#define VALUE_TEXT     ((void (*)(void *, u32, s32, s32, u32, u32, const char *, const char *))0x40071c10)
#define SAVE_SETTINGS  ((void (*)(void))0x400449b8)
#define USB_STOP       ((void (*)(void))0x40004d9a)
#define USB_RESTART    ((void (*)(void))0x40004db4)

/* mods_hooks.S */
void item_label(void);
void item_icon(void);
void make_handle(u32 *handle, void *parent, void *view);
u32 irq_off(void);
void irq_restore(u32 sr);
void cache_push(volatile u8 *p);
void cache_sync(void);

/* --- settings --- */
#define REC     ((volatile u8 *)0x404e9b80)
#define MAGIC   0x4d4f4453                    /* "MODS" */
enum { R_VER = 4, R_SET = 5, R_N = 10, R_CHK = 15, VERSION = 1 };
enum { S_USB6 = 0 };

static u8 rec_sum(void)
{
	u8 s = 0x5a;
	u32 i;

	for (i = R_VER; i < R_CHK; i++)
		s += REC[i];
	return s;
}

static int rec_ok(void)
{
	return *(volatile u32 *)REC == MAGIC && REC[R_CHK] == rec_sum();
}

u32 mods_get(u32 k)
{
	return rec_ok() ? REC[R_SET + k] : 0;
}

static void mods_put(u32 k, u8 v)
{
	u32 i;

	if (!rec_ok()) {
		*(volatile u32 *)REC = MAGIC;
		REC[R_VER] = VERSION;
		for (i = 0; i < R_N; i++)
			REC[R_SET + i] = 0;
	}
	REC[R_SET + k] = v;
	REC[R_CHK] = rec_sum();
	SAVE_SETTINGS();                          /* as the OS after each change (0x40044e74) */
}

/* --- USB audio, 2CH or 6CH --- */
static u8 saved[USB6_BYTES];                  /* the driver's bytes under the 6CH changes */
static u8 usb6_on;                            /* the 6CH changes are in place */

static void copy(volatile u8 *d, const volatile u8 *s, u32 n)
{
	while (n--)
		*d++ = *s++;
}

void usb6_apply(u32 on)
{
	const struct site *s;
	u32 sr;

	if (on == usb6_on)
		return;
	sr = irq_off();
	for (s = SITES; s < SITES + USB6_SITES; s++) {
		volatile u8 *p = (volatile u8 *)s->addr;

		if (on) {
			copy(saved + s->at, p, s->len);
			copy(p, NEW6 + s->at, s->len);
		} else {
			copy(p, saved + s->at, s->len);
		}
	}
	usb6_on = on;
	irq_restore(sr);
	for (s = SITES; s < SITES + USB6_SITES; s++) {
		cache_push((volatile u8 *)s->addr);
		cache_push((volatile u8 *)s->addr + s->len - 1);
	}
	cache_sync();                             /* the CPU runs the new code, the USB controller reads the new
						     descriptors */
}

/* Ring slots: 16 in 2CH, 9 in 6CH (0x400027b3, 0x400029b9), 16 or 5 for the input (0x4000253b). The OS does not
 * clear their indices when a stream starts: one left from the other mode would write past the ring. */
static void usb6_rings(void)
{
	*(volatile u32 *)0x8000bc94 = 0;
	*(volatile u32 *)0x8000bc90 = 0;
}

static u32 usb6_wanted(void)                  /* 1 = 6CH; 0, or any other value, = 2CH */
{
	return mods_get(S_USB6) == 1;
}

/* At start-up (usb_boot), before the USB mode is set up and the USB attached. */
void mods_boot(void)
{
	if (usb6_wanted()) {
		usb6_rings();
		usb6_apply(1);
	}
}

/* From the menu: saved, then the USB stopped and restarted as for a change of USB mode (0x40004e04): the computer
 * sees the Model:Cycles leave and come back about a second later, and reads its new descriptors. */
static void usb6_set(u32 on)
{
	mods_put(S_USB6, on);
	USB_STOP();
	usb6_rings();
	usb6_apply(on);
	USB_RESTART();
}

/* --- menus --- */
static u8 icon_bm[28];                        /* Bitmap: the icon of the Mods line and of the page */
static u32 page_h[2];                         /* shared pointer to the page, as the Config Menu's own (+600..) */

/* Line USB Audio: LEVEL/DATA pressed switches 2CH / 6CH (as Device Config › USB mode, 0x40031f8a). */
void usb_press(void **st)
{
	u8 *page = *(u8 **)*st;

	usb6_set(!usb6_wanted());
	VIEW_REDRAW(page + 56);
}

void usb_draw(void **st, u32 a, void *canvas, s32 x, s32 y)
{
	(void)st;
	(void)a;
	VALUE_TEXT(canvas, 0x401429ec, x, y - 12, 1, 0, (const char *)0x401301e6, usb6_wanted() ? "6CH" : "2CH");
}

/* Line Mods of the Config Menu: opens the page (as 0x4003bd42). */
void mods_open(void **st)
{
	void *cfg = *(void **)*st;
	u32 tmp[2];

	HANDLE_COPY(tmp, page_h);
	VIEW_PUSH(cfg, tmp);
	HANDLE_RELEASE(&tmp[1]);
}

/* A line: label, press, display (each with a 4-byte closure), no change function (as the Config Menu's lines). */
static void add_item(void *view, void *const inv[3], const u32 clo[3])
{
	fn_t f[4];
	void *item;
	u32 i;

	for (i = 0; i < 3; i++) {
		u32 *p = NEW(4);

		*p = clo[i];
		f[i].st0 = p;
		f[i].st1 = 0;
		f[i].mgr = FN_MANAGER;
		f[i].inv = inv[i];
	}
	f[3].st0 = f[3].st1 = 0;
	f[3].mgr = 0;
	f[3].inv = 0;
	item = NEW(0x54);
	ITEM(item, &f[0], &f[1], &f[2], &f[3], -1, 8);
	APPEND(view, item);
	for (i = 0; i < 4; i++)
		FN_DTOR(&f[i]);
}

/* End of the Config Menu's constructor (cfg_tail): the page, once, then the line Mods after Device. */
void mods_menu_add(void *cfg)
{
	static void *const USB_INV[3] = { item_label, usb_press, usb_draw };
	static void *const MODS_INV[3] = { item_label, mods_open, item_icon };

	if (!page_h[0]) {
		u8 *page = NEW(0x23c);
		u32 title, clo[3];
		u8 alloc;

		BITMAP(icon_bm, 31, 22, ICON_MODS, 0x4016e980);       /* mask: the kept copy (tools/sprites.py) */
		STRING(&title, "Mod Settings", &alloc);
		MENU_VIEW(page, "ModSettingsMenu", 1, &title, icon_bm);
		STRING_DTOR(&title);
		VIEW_KEYS(page + 56, 3);                              /* as Device Config and Battery */
		clo[0] = (u32)"USB Audio";
		clo[1] = (u32)page;
		clo[2] = 0;
		add_item(page, USB_INV, clo);
		make_handle(page_h, cfg, page + 56);
	}
	{
		u32 clo[3];

		clo[0] = (u32)"Mods";
		clo[1] = (u32)cfg;
		clo[2] = (u32)icon_bm;
		add_item(cfg, MODS_INV, clo);
	}
}
