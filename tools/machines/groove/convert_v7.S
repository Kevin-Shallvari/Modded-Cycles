/* Model:Groove, jalon 3 : le convertisseur de format v6 -> v7 (notes/56 §3.49).
 *
 * Ce fichier contient le CONVERTISSEUR D'ELEMENT : le repacking d'UN pattern range.
 *
 *   v6 : [4 o][6 x 722 = 4 332 o de pas][10 512 o de queue]            = 14 848
 *   v7 : [4 o][8 x 722 = 5 776 o de pas][10 512 o de queue]            = 16 292
 *
 * soit : copier 4, copier 4 332, METTRE A ZERO 1 444 (les pas des pistes 6-7), copier 10 512.
 * La queue rangee (une liste plate de 80 entrees de 130 o, §3.42) est copiee TELLE QUELLE : ses
 * entrees portent leur propre numero de piste (0..5), donc elles restent valides, et les pistes
 * 6-7 n'ont aucun verrou.
 *
 * Les trois longueurs et les trois offsets sont divisibles par 4, et les adresses sont alignees :
 * on copie donc en mots longs.
 *
 *   groove_elem(dst, src) -> 1
 */

	.text
	.globl	groove_elem
	.type	groove_elem, @function
groove_elem:
	movel	%sp@(4),%a0		/* dst */
	movel	%sp@(8),%a1		/* src */

	/* [0, 4) : l'en-tete du bloc range (le genre, etc.) */
	movel	%a1@+,%d0
	movel	%d0,%a0@+

	/* [4, 4336) : les pas des six pistes d'origine = 1083 mots longs */
	movel	#1083,%d1
1:	movel	%a1@+,%d0
	movel	%d0,%a0@+
	subql	#1,%d1
	bnes	1b

	/* [4336, 5780) : les pas des pistes 6-7, a zero = 361 mots longs */
	movel	#361,%d1
	moveq	#0,%d0
2:	movel	%d0,%a0@+
	subql	#1,%d1
	bnes	2b

	/* [5780, 16292) : la queue rangee, copiee telle quelle = 2628 mots longs */
	movel	#2628,%d1
3:	movel	%a1@+,%d0
	movel	%d0,%a0@+
	subql	#1,%d1
	bnes	3b

	moveq	#1,%d0			/* succes */
	rts
	.size	groove_elem, .-groove_elem
