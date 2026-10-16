/* Model:Groove, jalon 3 : le convertisseur v6 -> v7 (notes/56 §3.49, §3.58).
 *
 * Deux fonctions :
 *
 *   groove_v7(dst, src) -> 1   la TRANSFORMEE PURE, sans OS : un bloc v6 -> un bloc v7.
 *   groove_chain()             la COLLE, appelee par la redirection a 0x4005de74.
 *
 * -------------------------------------------------------------------------------------------
 * LA TRANSFORMEE (les chiffres viennent du §3.51, verifies par les notes et par le generateur) :
 *
 *   v6 : [512][96 x 14 848][96 x 7 680][512][4] = 2 163 716
 *   v7 : [512][80 x 16 292][80 x 7 680][512][4] = 1 918 788
 *
 *   - les 512 premiers octets sont copies, et la version (a +4) devient 7 ;
 *   - 80 patterns : l'ELEMENT de §3.50 (copier 4, copier 4 332, zero 1 444, copier 10 512) ;
 *     les curseurs avancent seuls de 14 848 (source) et 16 292 (destination) ;
 *   - la source saute alors la banque F : 16 x 14 848 = 237 568, ce qui la pose sur les kits v6
 *     (src + 1 425 920) tandis que la destination est deja sur les kits v7 (dst + 1 303 872) ;
 *   - 80 kits : copier 7 094 (1 773 mots longs + 1 mot), zero 200 (50 mots longs), puis sauter
 *     les 386 octets qui restent dans le creneau de 7 680, des deux cotes ;
 *   - la source saute ensuite 16 kits (122 880) pour tomber sur la queue v6 (src + 2 163 200),
 *     et la destination est deja sur la queue v7 (dst + 1 918 272) : 512 octets copies ;
 *   - le sceau de cloture 0xBACEF00C est ecrit a dst + 1 918 784.
 *
 * La queue rangee (une liste plate d'entrees qui portent leur propre numero de piste, §3.42)
 * est copiee TELLE QUELLE : les pistes 0-5 restent valides, les pistes 6-7 n'ont aucun verrou.
 *
 * -------------------------------------------------------------------------------------------
 * LA COLLE (le contrat de registres, lu dans le prologue de la chaine 0x4005d9f6 et dans les
 * blocs, par exemple le bloc v5 en 0x4005dd90) :
 *
 *   a2 = le bloc (l'image), 2 163 716 octets      a3 = le drapeau (peut etre nul)
 *   a4 = le contexte de la chaine                  fp (A6) = l'allocateur 0x400802e0
 *   a5 = le liberateur 0x400cf044
 *
 * Le bloc v5 fait exactement : allouer (jsr %fp@), convertir, memcpy(bloc, resultat, taille),
 * liberer (jsr %a5@), puis poser le drapeau. La colle fait la meme chose en v7, et refait le
 * controle de fin de chaine — sceau, sceau de cloture a 1 918 784, version == 7 — qui est ce
 * que la redirection remplace.
 *
 * Registres : la colle ne touche ni d5, ni d6, ni d7 (le chemin de chargement s'en sert APRES
 * la chaine : 0x4008d9c8 lit %d6), et la transformee ne touche que a0/a1/d0/d1/d2.
 */

	.text

/* ------------------------------------------------------------------ groove_v7(dst, src) */
	.globl	groove_v7
	.type	groove_v7, @function
groove_v7:
	movel	%sp@(4),%a0			/* dst */
	movel	%sp@(8),%a1			/* src */

	/* 1. les 512 premiers octets : sceau, version, et le reste de l'en-tete */
	movel	#128,%d2
1:	movel	%a1@+,%d0
	movel	%d0,%a0@+
	subql	#1,%d2
	bnes	1b
	moveq	#7,%d0
	movel	%d0,%a0@(-508)			/* la version du bloc : 6 -> 7 (dst + 4) */

	/* 2. les 80 patterns (la banque F est abandonnee : elle est au-dela) */
	movel	#80,%d2
2:	movel	%a1@+,%d0			/* [0, 4) : l'en-tete de l'element */
	movel	%d0,%a0@+
	movel	#1083,%d1			/* [4, 4336) : les pas des six pistes = 1 083 mots longs */
3:	movel	%a1@+,%d0
	movel	%d0,%a0@+
	subql	#1,%d1
	bnes	3b
	moveq	#0,%d0
	movel	#361,%d1			/* [4336, 5780) : les pistes 6-7, a zero = 361 mots longs */
4:	movel	%d0,%a0@+
	subql	#1,%d1
	bnes	4b
	movel	#2628,%d1			/* [5780, 16292) : la queue rangee, telle quelle */
5:	movel	%a1@+,%d0
	movel	%d0,%a0@+
	subql	#1,%d1
	bnes	5b
	subql	#1,%d2
	bnes	2b

	/* 3. la source saute la banque F : 16 x 14 848 = 237 568 (elle est alors sur les kits v6) */
	addal	#237568,%a1

	/* 4. les 80 kits : 7 094 copies, 200 a zero, puis 386 sautes de chaque cote */
	movel	#80,%d2
6:	movel	#1773,%d1			/* 7 094 = 1 773 mots longs + 1 mot */
7:	movel	%a1@+,%d0
	movel	%d0,%a0@+
	subql	#1,%d1
	bnes	7b
	movew	%a1@+,%d0
	movew	%d0,%a0@+
	moveq	#0,%d0
	movel	#50,%d1				/* 200 a zero = 50 mots longs */
8:	movel	%d0,%a0@+
	subql	#1,%d1
	bnes	8b
	addal	#586,%a1			/* le reste du creneau source : 7 680 - 7 094 */
	addal	#386,%a0			/* le reste du creneau destination : 7 680 - 7 294 */
	subql	#1,%d2
	bnes	6b

	/* 5. la source saute les 16 kits non gardes (16 x 7 680 = 122 880) : elle est sur la queue */
	addal	#122880,%a1

	/* 6. la queue de 512 octets, puis le sceau de cloture */
	movel	#128,%d2
9:	movel	%a1@+,%d0
	movel	%d0,%a0@+
	subql	#1,%d2
	bnes	9b
	movel	#-1160843252,%d0		/* 0xBACEF00C */
	movel	%d0,%a0@+			/* dst + 1 918 784 */

	moveq	#1,%d0				/* succes */
	rts
	.size	groove_v7, .-groove_v7

/* ------------------------------------------------------------------ groove_chain() */
	.globl	groove_chain
	.type	groove_chain, @function
groove_chain:
	lea	-16(%sp),%sp			/* ce que la chaine ne sauvegarde pas : d5-d7 */
	movem.l	%d5-%d7, (%sp)

	/* 1. le tampon v7 */
	movel	#1918788,%sp@-
	jsr	%fp@
	addql	#4,%sp
	tstl	%d0
	beqs	.Lfail
	movel	%d0,%d5				/* d5 : le tampon (la colle peut, elle le sauve) */

	/* 2. convertir : groove_v7(dst = le tampon, src = le bloc) — le PREMIER argument est
	 *    le DERNIER empile. */
	movel	%a2,%sp@-
	movel	%d5,%sp@-
	bsr	groove_v7			/* pc-relatif : un `jsr <etiquette>` sort en absolu */
	addql	#8,%sp

	/* 3. recopier dans l'image : memcpy(a2, d5, 1918788) */
	movel	#1918788,%sp@-
	movel	%d5,%sp@-
	movel	%a2,%sp@-
	lea	0x4008f1f0,%a0
	jsr	%a0@
	lea	%sp@(12),%sp

	/* 4. liberer le tampon */
	movel	%d5,%sp@-
	jsr	%a5@
	addql	#4,%sp

	/* 5. le drapeau */
	tstl	%a3
	beqs	.Lcheck
	moveb	#1,%a3@

.Lcheck:
	/* 6. le controle de fin de chaine, en v7 */
	movel	%a2@(4),%d0			/* la version du bloc */
	moveal	#-1091585330,%a0		/* 0xBEEFBACE */
	cmpal	%a2@,%a0
	bnes	.Lfail
	movel	#1918784,%d1
	moveal	#-1160843252,%a0		/* 0xBACEF00C */
	cmpal	%a2@(0,%d1:l),%a0
	bnes	.Lfail
	moveq	#7,%d1
	cmpl	%d0,%d1
	seq	%d0
	negl	%d0
	bras	.Lout

.Lfail:
	clrb	%d0

.Lout:
	movem.l	(%sp), %d5-%d7
	lea	16(%sp),%sp
	rts
	.size	groove_chain, .-groove_chain
