/* Model:Groove, jalon 2 : remplissage des 80 patterns déployés (notes/56 §3.62).
 *
 * La seconde boucle de 0x40061738 remplit les 80 créneaux déployés depuis le
 * pattern 0 : memcpy(dst = curseur+28, src = modèle, n = S), index en
 * curseur+S+24 (= fin-4 du contenu), fanion en curseur+S-12, avec S = 40924.
 * Les trois sites 16 bits (n, pas, index) ne peuvent pas porter 40924
 * (> 0x7FFF : extension de signe — §3.62) et ColdFire n'a pas de déplacement
 * 32 bits : le pas passe par un registre d'index, et tout le reste tient en
 * formes courtes. D'où cette boucle en cave (même mécanisme que §3.58).
 *
 * Entrée : a2 = l'en-tête (curseur, avancé comme la boucle), d4 = le modèle,
 *           a3 = memcpy.
 * Registres : a2 (curseur), d2 (le pas : callee-saved tous deux, restaurés par
 * l'épilogue de l'appelant — et préservés par memcpy, qui écrase d0/d1/a0/a1
 * à la place), d3 (l'index, finit à 80). a2/d4/a3 lus sauf a2 avancé ; d3
 * comme la boucle. Pile équilibrée. d5-d7/a4-a6/fp intouchés.
 */

	.text
	.globl	groove_fill
	.type	groove_fill, @function
groove_fill:
	movel	#40924,%d2			/* le pas */
	clrl	%d3				/* i = 0 */
1:
	movel	#40924,%sp@-			/* n */
	movel	%d4,%sp@-			/* src = le modèle */
	lea	%a2@(28),%a1			/* dst = curseur+28 */
	movel	%a1,%sp@-
	jsr	%a3@				/* memcpy */
	lea	%sp@(12),%sp
	lea	%a2@(0,%d2:l),%a1		/* curseur+pas ; index à +24 */
	movel	%d3,%a1@(24)
	lea	%a2@(0,%d2:l),%a2		/* pas (comme la boucle) */
	moveb	%d3,%a2@(-12)			/* fanion */
	addql	#1,%d3
	cmpil	#80,%d3
	bnes	1b
	rts
	.size	groove_fill, .-groove_fill
