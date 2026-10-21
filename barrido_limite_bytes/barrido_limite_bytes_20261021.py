#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""barrido_limite_bytes_20261021.py — ¿el tope de LIMITE_BYTES es prudencia medida o decreto?

HUELLA-BARRIDO-LIMITE-BYTES-20261021

PROPOSITO
  Medir el coste REAL de la capa de contenido de tools/hooks/pre-commit en
  funcion del tamano del archivo indexado, para decidir si
  LIMITE_BYTES = 2 MiB es una frontera medida o un numero redondo.

POR QUE HACE FALTA UN INSTRUMENTO Y NO UN CRONOMETRO
  Desde HUELLA-PRE-COMMIT-LIMITE-MB-20261021 el hook RECHAZA todo archivo
  > 2 MiB ANTES de escanearlo. Cronometrar el hook real sobre un archivo de
  6 MiB mide la rama de rechazo (constante, ~1 s) y concluiria "el coste es
  plano, el tope es supersticion": el instrumento mediria su propia excepcion.
  Por eso cada punto se mide en DOS regimenes sobre el MISMO archivo:
    TOPE       el hook real                      -> LIMITE_MB (no escanea)
    CONTENIDO  una copia con UN literal cambiado -> escanea de verdad
  La copia es byte-identica salvo `LIMITE_BYTES=2097152`; el delta se mide y
  se imprime, y si deja de ser UNA linea el barrido no corre (RC 5). No se
  reimplementa el escaneo: se ejecuta el hook.

QUE MIDE
  Tiempo de pared y RSS maximo (ru_maxrss) del arbol de procesos del hook
  COMPLETO, por punto y por regimen, min de `--reps` repeticiones.
  Ademas, por punto, los bytes que la capa de contenido recibe DE VERDAD
  (`git diff --cached -U0 --diff-filter=ACMR | grep '^+' | grep -v '^+++'`):
  un archivo binario (con NUL) hace que git imprima `Binary files differ` y la
  capa escanearia CERO bytes — el punto pasaria como "rapido" sin medirse.
  Si los bytes recibidos < 90 % del tamano, RC 3.

ATRIBUCION DEL COSTE
  En el punto mayor se mide por separado (a) la extraccion del diff y (b) UNA
  pasada de `busca_patron` (printf de la variable | grep -qiE), para poder
  decir cuantas pasadas equivalentes cuesta el hook en vez de suponerlo.

PASES CONTENIDO: CONTAR EN VEZ DE CRONOMETRAR
  HUELLA-BARRIDO-PASES-CONTENIDO-20261021

  `pases_equivalentes` = t_hook / t_una_pasada es un PROXY con dos defectos
  medidos: (1) su control paga una lectura de disco (`_texto=$(cat "$1")`) que
  el hook no paga por patron, asi que SUBCUENTA —dijo 6.0 donde el conteo
  real es 11—; (2) dispersa. Medido en esta maquina: b (s/MiB) tomo
  1.183 · 1.193 · 1.342 · 1.438 · 1.971 en cinco corridas (1.67x), y el
  cociente t/t_pasada a 2 MiB tomo 4.30 · 7.65 · 8.85 (2.06x) porque el
  denominador pesa ~0.3 s. Una banda de +-50 % sobre SEGUNDOS es mas estrecha
  que esa dispersion: dispararia con la carga de la maquina, no con el codigo.

  RETIRADO DEL SELLO (HUELLA-F11-PISO-Y-PASES-RETIRADO-20261021). Declararlo
  `tipo: "proyeccion"` no lo volvio medible: tres corridas sobre el MISMO
  sello dieron 2.32 · 4.27 · 11.15 pasadas equivalentes, o sea delta -78.9 % ·
  -61.2 % · +1.3 % sobre el conteo real (11). Un cociente que oscila 80 puntos
  porcentuales sobre el mismo objeto no es una proyeccion con sesgo: es ruido.
  El sesgo se corrige, el ruido se retira. El campo ya no viaja al JSON; en su
  lugar va `_retirado` con la varianza que lo retiro y el puntero a la unica
  medicion, `coste.pases_contenido`. El printout de ATRIBUCION lo sigue
  mostrando como diagnostico de la corrida, jamas como cifra del sello.

  Por eso el coste se CUENTA en vez de cronometrarse: un `grep` de guardia en
  el PATH registra los bytes que recibe por stdin cada invocacion `grep -qiE`,
  y `pases_contenido` = invocaciones con >= UMBRAL_CONTENIDO bytes (las de
  RUTA reciben el nombre del archivo, ~20 B, y no cuestan por byte).
  La cantidad es DISCRETA y exacta: 11 en el hook sano, 20 con la llamada
  duplicada, 2 con las tablas de contenido colapsadas a un patron. Cero
  dispersion, y el mismo numero con la maquina cargada.
  Fail-closed: si el guardia no engancha (0 invocaciones) o el hook no pasa el
  fixture, RC 3. Un cero NUNCA se lee como mejora — es el fail-open que este
  instrumento mide (medido: PATH sin guardia -> rc 0 y 0 pasadas).

MEMORIA: EL RSS SI ES UN INSTRUMENTO (--solo-rss)
  HUELLA-BARRIDO-RSS-20261021

  El conteo de pasadas es ciego a la memoria: una cache que se acumula entre
  llamadas no anade ni una pasada y sin embargo puede cuatriplicar el RSS.
  El RSS se MIDIO antes de proponerlo como guardian, y dispersa mucho menos
  que el tiempo: a 12 MiB tomo 97.4 · 89.9 · 87.5 MB en tres corridas
  (1.11x), frente al 1.48x de los segundos en el mismo tramo.
  Sensibilidad medida con mutantes de bash sobre 12 MiB (mismo texto, 11
  patrones): sin cache 73.4 MB · una copia por llamada 100.2 MB (+37 %) ·
  copia ACUMULADA entre llamadas 325.9 MB (+344 %). El mutante que cambia de
  regimen es el que se acumula, y por eso el umbral absoluto discrimina.

  `--solo-rss` mide 1 y 12 MiB del regimen CONTENIDO y reporta el RSS y la
  pendiente MB/MiB. Un solo punto no distingue una cache de un buffer.
  El blob del hook entra al JSON (`hook_blob`): un baseline de memoria que no
  dice A QUE codigo pertenece es el defecto de «un nombre, dos objetos».

  `--hook RUTA` mide una COPIA del hook. Existe para que los falsadores se
  ejerzan sobre un mutante y no tocando el hook real — mutar el hook real
  produce falsos «FALLA» cuando el mutante esperado ya no esta en el archivo.

  Frontera declarada del conteo: el repo de trabajo es el de `preparar()` —
  hook + baseline, no el arbol entero. El guardian de frontera de archivo
  declara SKIP por ausencia del script (`pre-commit frontera · SKIP
  DECLARADO`), y el conteo NO se mueve: mide las invocaciones `grep -qiE` de
  `busca_patron`, que son de la capa de contenido. Copiar el arbol entero
  haria el conteo mas caro y no mas cierto.

SALIDA
  tabla  tamano_mib  t_tope_s  t_contenido_s  cpu_s  d_cpu  rss_tope_mb
         rss_contenido_mb  bytes_vistos  s_por_mib
  veredicto con las cuatro ramas (plano / no lineal / lineal-barato /
         lineal-caro) y el codo medido: el mayor tamano bajo 2 s y bajo 10 s.
  `--json RUTA` escribe los puntos y el veredicto.

  `cpu_s` es `user+sys` de la MISMA invocacion de `/usr/bin/time -l` que dio
  `t_contenido_s` — el campo ya venia en el stderr y se tiraba. `wall_menos_cpu_s`
  es el resto que el instrumento NO descompone (I/O + overhead del arranque) y
  puede salir NEGATIVO: `user`/`sys` se suman por CPU y el wall es tiempo
  transcurrido, asi que concurrencia en el arbol acumula mas CPU que reloj. Se
  declara con su signo; no se recorta a 0 ni se reparte en causas. El reloj de
  pared mide la maquina; el CPU mide el codigo. Cual de los dos rige el ajuste lo
  decide sim/preregistro_cpu_vs_wall_20261021.md, no este docstring.

EMISOR Y SELLO (HUELLA-BARRIDO-EMISOR-BLOB-20261021, HUELLA-SOLO-PASES-NO-SOBREESCRIBE-SELLO-20261021)
  El sello lleva `emisor_blob`: el blob de ESTE archivo. Un sello que no dice
  que barrido lo escribio es un numero sin fuente, y el guardian del maestro
  (F12) no puede distinguir un sello vivo de uno caducado. Se mide con
  `git hash-object` sobre el propio archivo, igual que `hook_blob` sobre el
  hook: la identidad del codigo que midio, no la fecha de un comentario.

  Un sello no se sobrescribe con una salida PARCIAL. `--solo-pases --json`
  escribe {huella, fixture, coste} y `--solo-rss --json` escribe
  {huella, hook_blob, puntos, rss}: ninguna de las dos formas trae `ajuste`,
  `veredicto` ni `_retirado`, asi que escribirla sobre sim/curvas/ deja el
  sello con nombre de sello y forma de salida parcial — y F10, F11 y F12 se
  quedan sin objeto de una sola vez, sin que nada chille hasta la corrida
  siguiente. El sello se regenera con la corrida COMPLETA (sin --solo-*); si
  alguien quiere de verdad degradarlo, lo declara con `--force-sello`.

CALIDAD DEL SELLO (HUELLA-BARRIDO-SELLO-DEGRADADO-20261021)
  Proteger la FORMA no basta: un sello con forma correcta y ajuste peor es una
  medida peor con el mismo nombre. Medido dos veces en el mismo turno sobre la
  misma maquina: `--reps 3` en calma dio R^2 0.9979 y `--reps 2` bajo carga dio
  R^2 0.8535 — mismo emisor, y el barrido escribia las dos.

  Regla: el eje del juicio es el OBJETO (`hook_blob`), no el emisor. El emisor
  dice quien midio, el hook dice que se midio: si el hook no cambio, la recta
  es comparable aunque el emisor cambie (MISMO_OBJETO); si el hook cambio, no
  hay nada que comparar y solo se declara (OBJETO_DISTINTO). Con el mismo
  objeto, el sello NO se escribe (SELLO_DEGRADADO, RC 1) si el R^2 nuevo cae
  mas de R2_TOLERANCIA, si el veredicto empeora, o si el objeto ENCOGIO
  (OBJETO_ENCOGIDO: menos puntos => el R^2 sube solo). `--force-sello` lo
  declara y escribe. Medido: una copia del sello pasaba de 6 a 3 puntos y de
  R^2 0.9979 a 0.99999999 con RC 0, y encogia el objeto despues de imprimir
  MISMO_OBJETO — con el eje colgando del emisor, un hook distinto medido por el
  mismo codigo ni se miraba. El juicio corre ANTES de `atribuir` y
  `medir_coste`: una corrida que va a ser rechazada no paga los ~40 s que
  faltan.

VENTANA DE DISPERSION (HUELLA-GUARDIA-OBJETO-ENCOGIDO-20261021)
  Un umbral que solo se reporta no es umbral. La ventana es el peor max/min por
  punto con el que se certifico el sello vivo (1.73x). Si la corrida dispersa
  mas, la corrida NO escribe el sello (FUERA_DE_VENTANA, RC 1) y el sello vive;
  `--force-ventana` lo declara y escribe. Medido en el piloto de ventana: 2 de 4
  corridas entraron (1.16x, 1.50x) y 2 no (1.82x, 8.38x) — la de 1.82x entraba
  antes sin que nada la parara.

VENTANA CON MUESTRA (HUELLA-GUARDIA-REPS-MINIMO-20261021)
  La ventana necesita piso de replicas. `disp_cont` es max/min POR PUNTO, asi que
  con `--reps 1` vale 1.00x en todos los puntos POR CONSTRUCCION: un 1.00x medido
  y un 1.00x sin muestra son el mismo numero para el guardian. Medido: una corrida
  con `--reps 1` paso el gate de dispersion con 1.00x y solo la detuvo
  OBJETO_ENCOGIDO. Regla: por debajo de `REPS_MIN_VENTANA` (2) la corrida NO
  escribe el sello (REPLICA_INSUFICIENTE, RC 1); `--declaro-reps` lo declara,
  escribe, y el sello queda con `dispersion.ventana_vacia = true` — dice que lo
  que certifica NO incluye la ventana. La vacua se juzga ANTES de mirar el sello
  previo: tambien una primera escritura puede sellar una ventana que no se midio.

CURVA: DOS DIMENSIONES (HUELLA-GUARDIA-CURVA-ROTA-20261021)
  La ventana mide PRECISION DENTRO del punto; la curva se puede romper ENTRE
  puntos. Medido: una corrida de hoy traia `disp_cont` 1.02 · 1.02 · 1.01 dentro
  de la ventana de 1.73x y sin embargo R^2 0.5253, porque el punto de 1.0 MiB
  costo mas que el de 2.0 MiB: preciso y fuera de lugar. El gate veia la
  dimension que el instrumento mide, no la que el objeto necesita.

  Dos ejes, y ninguno es `R^2` (load-dependent, retirado como juez en el v2):
  MONOTONIA —el coste no cae al crecer el archivo— y `residual_entre`, la
  desviacion de cada punto contra lo que interpolan sus vecinos EN MiB,
  normalizada por el error del propio punto con piso en la mediana de los
  errores de la corrida. El piso no es cosmetico: un punto medido identico tres
  veces tiene se = 0 por construccion, y sin piso cualquier curvatura vale
  infinitas sigmas. `RESIDUO_K` sale del SELLO (peor residual al certificarse
  3.03 => K 6.06) y no de la corrida que se juzga: el K dictado (3) habria
  rechazado el sello bueno por 1 %. Medido contra esto, la corrida rota de hoy
  da 222.5. `CURVA_ROTA` es RC 1 y su bandera es `--force-curva`: `--force-sello`
  perdona una degradacion, no una medicion rota. Sin error por punto el residuo
  no se calcula (RESIDUO_NO_CALCULABLE) y la curva se juzga solo por monotonia.
  LIMITE MEDIDO: el residuo mide contra la cuerda local, asi que una curvatura
  fuerte se ve igual que una ruptura. Con este espaciado (0.5, 1, 2, 4, 6, 12):
  recta 0.00, sello 3.03, concava suave (R^2 0.9944) 3.25 — pasa; concava fuerte
  (R^2 0.9606) 6.09 y logaritmica (R^2 0.9092) 8.47 — disparan. Dentro del corpus
  el objeto es lineal (el sello, 0.9979), asi que la frontera no se toca; fuera de
  ahi el gate declara rota una curva que solo es curva, y el recurso es
  `--force-curva`, no bajar K.

REGIMEN: DOS RAMAS, UN EJE (HUELLA-GUARDIA-REGIMEN-CRUZADO-20261021)
  Cada punto se mide en DOS regimenes sobre el MISMO archivo (`rc_tope` con el
  hook real, `rc_contenido` con la copia de un literal abierto), asi que un
  punto NO «cae» en una rama: porta las dos. Lo medido, contra el dictado:
  `rc_contenido` vale 0 en los seis puntos del sello y en toda corrida
  conservada — la rama juzgada es UNA sola—, mientras `rc_tope` cruza 0 -> 1
  entre 2.0 y 4.0 MiB (arriba del tope el hook no escanea: 2.54 s -> 0.16 s).
  Por eso el cruce se juzga sobre `rc_contenido` y se DECLARA sobre `rc_tope`:
  gatear el segundo rechazaria el sello bueno, que es monotono y lineal (R^2
  0.9979) a traves del cruce, porque esa rama gobierna `t_tope_s` y no la curva
  que el gate mide. Un cruce de `rc_contenido` son dos funciones en el mismo
  eje: la curva deja de ser comparable (CURVA_NO_EVALUABLE), y el sello no se
  escribe (REGIMEN_CRUZADO, RC 1) salvo `--force-regimen`, bandera propia como
  `--force-curva` y `--force-ventana`. El eje no tiene constante que elegir: un
  rc es igual o no lo es. Cuando es plano se declara plano (REGIMEN_CONSTANTE):
  un eje plano y un eje no implementado se ven igual desde el sello, y esta
  linea es la que los distingue.

RC
  0   curva medida
  1   el sello existente certifica una medida que esta corrida no sostiene:
      ajuste peor (SELLO_DEGRADADO), veredicto peor, objeto encogido
      (OBJETO_ENCOGIDO), corrida fuera de ventana (FUERA_DE_VENTANA), ventana
      sin muestra (REPLICA_INSUFICIENTE), curva rota (CURVA_ROTA: no monotona
      o residual sobre K) o regimen cruzado en la rama juzgada
      (REGIMEN_CRUZADO). Sin `--force-sello` / `--force-ventana` /
      `--declaro-reps` / `--force-curva` / `--force-regimen` no se escribe y el
      sello vive
  3   el regimen CONTENIDO no recibio los bytes (estaba midiendo su excepcion),
      o el guardia de `grep` no engancho / el hook no paso el fixture (el
      conteo de pasadas no es comparable), o un `--solo-*` intento escribir
      sobre un path con forma de sello (SELLO_NO_SOBREESCRIBIBLE)
  4   el regimen TOPE no rechazo un archivo sobre el tope (no hay dos regimenes)
  5   la copia no difiere en EXACTAMENTE un literal (no se mide este hook)
  6   curva insuficiente (menos de 3 puntos, o pendiente no positiva): sin recta
      no hay veredicto. Un solo punto da b=0, extrapola 0.0 s a 63 MiB y firma
      SUPERSTICION desde una recta que no existe — el fail-open del instrumento.
  20  falta git o /usr/bin/time
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HOOK_REL = "tools/hooks/pre-commit"
BASELINE_REL = "tools/limite_mb_baseline.txt"
LITERAL = "LIMITE_BYTES=2097152"
LITERAL_ABIERTO = "LIMITE_BYTES=999999999"
MIB = 1024 * 1024
TAMANOS_MIB = [0.5, 1.0, 2.0, 4.0, 6.0, 12.0]
# Los dos puntos del regimen de MEMORIA: 12 MiB es el tamano donde el RSS se
# separa del intercepto, y 1 MiB da la referencia baja para leer la pendiente
# MB/MiB. Dos puntos, porque un solo punto no distingue una cache de un buffer.
TAMANOS_RSS = (1.0, 12.0)
# 2 MiB es el tope declarado; 6 MiB es el tamano donde el falsador dictado
# decide entre supersticion y prudencia.
MIB_DECISION = 6.0
# Minimo de puntos para que la recta exista: con 2 puntos el ajuste es exacto y
# no discrimina nada; con 1, b no esta definido.
MIN_PUNTOS = 3
# Anclas REALES del corpus (medidas en tools/limite_mb_baseline.txt): el tope
# y el mayor objeto declarado. Se extrapolan con la recta medida y se marcan
# como EXTRAPOLADO; nunca se presentan como medicion.
ANCLAS_BYTES = [
    ("mayor objeto declarado (t08_multihop)", 66334586),
    ("objeto declarado mediano (BANCO_ESCALA_PARIDAD)", 6183624),
]

LINEA_RELLENO = "2026-10-21T00:00:00Z linea de relleno textual para el barrido; sin nulos.\n"
PATRON_UNA_PASADA = "(password|passwd|secret|token|api[_-]?key)[[:space:]]*[:=]"

# Fixture del conteo: extension .txt para que el hook consulte las DOS tablas de
# contenido (CRED_CUERPO + WEB_CUERPO_TEXTO). Cambiar la extension cambia el
# numero de patrones y con ello el conteo: el baseline no seria comparable.
FIXTURE_PASES = "fixture_pases_contenido.txt"
# 64 KiB basta: el CONTEO es independiente del tamano (medido: 11 pasadas a
# 64, 256 y 512 KiB) y el coste del conteo lo paga el hook, no el fixture.
FIXTURE_PASES_BYTES = 64 * 1024
# Invocaciones cuyo stdin supera esto son pasadas SOBRE EL TEXTO. Las tablas de
# RUTA reciben el nombre del archivo (~20 B) y no cuestan por byte.
UMBRAL_CONTENIDO = 4096
# Claves que SOLO escribe la corrida completa. `huella`, `coste` y `puntos`
# viajan tambien en las salidas parciales, asi que preguntar por ellas no
# discriminaria sello de parcial; estas tres nunca viajan en `--solo-*`.
SELLO_CLAVES = ("ajuste", "veredicto", "_retirado")
# Cuanto puede caer el R^2 de un sello sin que la caida sea degradacion. El
# ruido de la maquina mueve el ajuste mas que esto (medido: 0.9979 en calma vs
# 0.8535 bajo carga), asi que la tolerancia no tapa degradaciones reales; solo
# deja pasar el temblor de una corrida a otra.
R2_TOLERANCIA = 0.005
# Ventana de dispersion del sello vivo: su peor max/min por punto al certificarse
# (`sim/curvas/hook_limite_bytes_20261021.json`, sello 0c75dcb1:
# 1.34 · 1.09 · 1.00 · 1.05 · 1.26 · 1.73). Una corrida que dispersa mas que
# esto no midio el mismo objeto en condiciones comparables, asi que el umbral
# GATEA (RC 1) en vez de solo reportarse. Medido en el piloto
# `sim/ventana_piloto_20261021.json`: 2 de 4 corridas entraron (1.16x, 1.50x) y
# 2 no (1.82x, 8.38x). `--force-ventana` lo declara y escribe.
VENTANA_DISP_CONT = 1.73
# Piso de replicas de la ventana: `disp_cont` es max/min por punto, asi que con
# `--reps 1` vale 1.00 POR CONSTRUCCION en todos los puntos y entra en cualquier
# ventana. Medido: una corrida con `--reps 1` paso el gate de dispersion con
# 1.00x y solo la detuvo OBJETO_ENCOGIDO. Un 1.00 medido no es un 1.00 sin
# muestra: por debajo de este piso la ventana no se midio (REPLICA_INSUFICIENTE),
# y sellar sin medirla se declara con `--declaro-reps`.
REPS_MIN_VENTANA = 2
# Residuo ENTRE puntos. `disp_cont` mide la maquina DENTRO de un punto (precision);
# un punto puede ser preciso y estar fuera de la curva, y entonces el gate ve la
# dimension que el instrumento mide y no la que el objeto necesita. `residual_entre`
# es la desviacion de cada punto contra lo que interpolan sus vecinos EN MiB (los
# puntos no son equidistantes: 0.5, 1, 2, 4, 6, 12), normalizada por el error del
# propio punto. El denominador lleva PISO en la mediana de los errores de la
# corrida: sin piso, un punto medido identico tres veces tiene se = 0 por
# construccion y cualquier curvatura se vuelve infinitas sigmas (medido: el punto
# 2.0 MiB del sello, disp 1.00 con 3 reps, desvia 0.28 s con se 0).
# K sale del SELLO, nunca de la corrida que se juzga: su peor residual al
# certificarse fue 3.03 (2.0 MiB, el del se nula), asi que K = 2 x 3.03. Medido
# contra esto: la corrida de hoy con R^2 0.5253 da 222.5, y el K dictado (3)
# habria rechazado el SELLO BUENO por 1 %.
RESIDUO_K = 6.06
# `rama()` no firma "LINEAL": firma LINEAL_CARO, PRUDENCIA o SUPERSTICION. Para
# juzgar degradacion se ordena por CALIDAD DE MEDIDA, no por la conclusion:
# PRUDENCIA es el unico veredicto que dice "la curva no sostiene la ley";
# LINEAL_CARO y SUPERSTICION son las dos medidas lineales que discrepan sobre el
# tope (y el hook puede volverse barato sin que el EMISOR cambie). Un veredicto
# desconocido cuenta como peor: la taxonomia cambio y nadie lo declaro.
ORDEN_VEREDICTO = {"LINEAL_CARO": 0, "SUPERSTICION": 0, "PRUDENCIA": 1}
# Guardia de `grep`: registra los bytes que recibe por stdin y delega en el
# grep real. Solo intercepta `-qiE`, que es el unico verbo de busca_patron; el
# resto de los grep del hook (rutas, tablas, salidas del maestro) pasan intactos.
SHIM_GREP = r"""#!/bin/bash
case " $* " in
  *" -qiE "*)
    _shim_tmp=$(mktemp)
    cat > "$_shim_tmp"
    wc -c < "$_shim_tmp" | tr -d ' ' >> "$CONTEO"
    __GREP__ "$@" < "$_shim_tmp"
    _shim_rc=$?
    rm -f "$_shim_tmp"
    exit $_shim_rc
    ;;
esac
exec __GREP__ "$@"
"""

RE_REAL = re.compile(r"^\s*([0-9.]+)\s+real\b", re.M)
RE_RSS = re.compile(r"^\s*([0-9]+)\s+maximum resident set size", re.M)
# HUELLA-BARRIDO-EMITE-CPU-20261021
# `real`, `user` y `sys` comparten UNA linea ('  0.08 real  0.07 user  0.00 sys'):
# un `^\s*([0-9.]+)\s+user` anclado devuelve None. El patron exige los tres campos
# y su orden, de modo que el CPU no puede venir de otra linea que el wall.
RE_CPU = re.compile(r"^\s*([0-9.]+)\s+real\s+([0-9.]+)\s+user\s+([0-9.]+)\s+sys", re.M)


class Falla(Exception):
    def __init__(self, rc, msg):
        self.rc = rc
        self.msg = msg


def sh(cmd, cwd):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def texto_de(bytes_):
    """Relleno textual sin NUL: git no debe clasificarlo como binario."""
    n = max(1, bytes_ // len(LINEA_RELLENO) + 1)
    s = LINEA_RELLENO * n
    return s.encode()[:bytes_]


def preparar(work, hook_src, baseline_src):
    repo = os.path.join(work, "repo")
    os.makedirs(os.path.join(repo, "tools"), exist_ok=True)
    rc, _, err = sh(["git", "init", "-q", "."], repo)
    if rc != 0:
        raise Falla(20, f"git init fallo: {err.strip()}")
    sh(["git", "config", "user.email", "barrido@local"], repo)
    sh(["git", "config", "user.name", "barrido"], repo)
    sh(["git", "config", "commit.gpgsign", "false"], repo)

    hook_abierto = os.path.join(work, "pre-commit-abierto")
    with open(hook_src, "r", encoding="utf-8", errors="surrogateescape") as fh:
        crudo = fh.read()
    if crudo.count(LITERAL) != 1:
        raise Falla(5, f"{HOOK_REL} no contiene exactamente una vez `{LITERAL}` "
                       f"(encontradas {crudo.count(LITERAL)}): el tope se movio de forma")
    with open(hook_abierto, "w", encoding="utf-8", errors="surrogateescape") as fh:
        fh.write(crudo.replace(LITERAL, LITERAL_ABIERTO))

    a = crudo.splitlines()
    b = crudo.replace(LITERAL, LITERAL_ABIERTO).splitlines()
    if len(a) != len(b):
        raise Falla(5, "la copia cambio el numero de lineas: no es un literal, es una edicion")
    delta = [i for i in range(len(a)) if a[i] != b[i]]
    if len(delta) != 1:
        raise Falla(5, f"la copia difiere en {len(delta)} lineas, no en 1: {delta}")
    print(f"COPIA  {hook_src} -> pre-commit-abierto")
    print(f"DELTA  1 linea (l.{delta[0] + 1}): {a[delta[0]].strip()} -> {b[delta[0]].strip()}")

    if os.path.isfile(baseline_src):
        shutil.copy2(baseline_src, os.path.join(repo, BASELINE_REL))
        print(f"BASELINE copiada: {BASELINE_REL} (la rama TOPE ejerce el helper real)")
    else:
        print(f"BASELINE ausente en el origen: {BASELINE_REL} (la rama TOPE devolvera NO declarada)")

    with open(os.path.join(repo, "README.md"), "w", encoding="utf-8") as fh:
        fh.write("fixture del barrido de tamano\n")
    sh(["git", "add", "-A"], repo)
    rc, _, err = sh(["git", "commit", "-qm", "fixture"], repo)
    if rc != 0:
        raise Falla(20, f"commit inicial fallo: {err.strip()}")
    return repo, hook_abierto, delta[0]


def medir(hook, repo):
    """/usr/bin/time -l: tiempo de pared, CPU (user+sys) y RSS maximo del arbol del hook.

    El CPU sale de la MISMA invocacion que el wall — `user+sys` de la linea de
    `real`, que `time -l` ya imprimia y se tiraba. Un arnes aparte mediria otro
    objeto (otro arranque, otra cache), y entonces `wall - cpu` no mediria el
    resto de UNA corrida sino la diferencia entre dos. Ese resto puede ser
    NEGATIVO: `user` y `sys` se suman por CPU y el wall es tiempo transcurrido,
    asi que un arbol con algo de concurrencia acumula mas CPU que reloj.
    """
    cmd = ["/usr/bin/time", "-l", "bash", hook]
    p = subprocess.run(cmd, cwd=repo, capture_output=True, text=True)
    m_t = RE_REAL.search(p.stderr)
    m_r = RE_RSS.search(p.stderr)
    if not m_t or not m_r:
        raise Falla(20, "no se pudo leer `real`/`maximum resident set size` de /usr/bin/time -l")
    m_c = RE_CPU.search(p.stderr)
    if not m_c:
        raise Falla(20, "PARSEO_FALLIDO: la linea de `real` no trae `user`/`sys`. El wall se "
                        "midio y el CPU no; devolver t_cpu ausente o None seria medir media "
                        "linea y llamarla instrumento")
    if abs(float(m_t.group(1)) - float(m_c.group(1))) > 1e-9:
        raise Falla(20, "PARSEO_FALLIDO: el `real` de RE_REAL y el de RE_CPU no son el mismo "
                        "numero; el par (wall, cpu) no seria una invocacion")
    return {
        "rc": p.returncode,
        "seg": float(m_t.group(1)),
        "cpu": float(m_c.group(2)) + float(m_c.group(3)),
        "rss_mb": round(int(m_r.group(1)) / (MIB * 1.0), 1),
        "out": p.stdout,
    }


def bytes_vistos(repo, ruta):
    rc, out, _ = sh(["git", "diff", "--cached", "-U0", "--diff-filter=ACMR", "--", ruta], repo)
    if rc != 0:
        return -1
    n = 0
    for ln in out.splitlines():
        if ln.startswith("+") and not ln.startswith("+++"):
            n += len(ln.encode()) + 1
    return n


def atribuir(repo, hook_abierto, ruta, work):
    """Separa (a) extraccion del diff y (b) UNA pasada de busca_patron."""
    rc, out, _ = sh(["git", "diff", "--cached", "-U0", "--diff-filter=ACMR", "--", ruta], repo)
    lineas = [ln for ln in out.splitlines() if ln.startswith("+") and not ln.startswith("+++")]
    tmp = os.path.join(work, "texto_recibido.txt")
    with open(tmp, "w", encoding="utf-8", errors="surrogateescape") as fh:
        fh.write("\n".join(lineas) + "\n")

    t_diff = medir_comp(["git", "diff", "--cached", "-U0", "--diff-filter=ACMR", "--", ruta], repo)
    guion = ('_texto=$(cat "$1"); printf "%s" "$_texto" | grep -qiE -- "$2"')
    t_paso = medir_comp(["bash", "-c", guion, "_", tmp, PATRON_UNA_PASADA], repo)
    return {"t_diff_s": t_diff, "t_una_pasada_s": t_paso, "texto_bytes": os.path.getsize(tmp)}


def pases_contenido(repo, hook, work, fixture_rel=FIXTURE_PASES,
                    umbral=UMBRAL_CONTENIDO):
    """Cuenta las pasadas de la capa de contenido: bytes, no segundos.

    Un `grep` de guardia en el PATH registra los bytes que recibe por stdin en
    cada invocacion `grep -qiE`. Las pasadas sobre el TEXTO son las que superan
    `umbral`; las tablas de RUTA reciben el nombre del archivo y no cuestan por
    byte. La cantidad es discreta y exacta: no dispersa con la carga.
    """
    grep_real = shutil.which("grep")
    if not grep_real:
        raise Falla(20, "no hay `grep` en el PATH: sin grep real no se puede delegar")
    shim_dir = os.path.join(work, "guardia_grep")
    os.makedirs(shim_dir, exist_ok=True)
    shim = os.path.join(shim_dir, "grep")
    with open(shim, "w", encoding="utf-8") as fh:
        fh.write(SHIM_GREP.replace("__GREP__", grep_real))
    os.chmod(shim, 0o755)

    conteo = os.path.join(work, "conteo_pases.txt")
    if os.path.exists(conteo):
        os.remove(conteo)
    env = dict(os.environ)
    env["PATH"] = shim_dir + os.pathsep + env.get("PATH", "")
    env["CONTEO"] = conteo
    p = subprocess.run(["bash", hook], cwd=repo, capture_output=True, text=True, env=env)

    if not os.path.exists(conteo):
        raise Falla(3, "el guardia de grep no engancho: cero invocaciones `-qiE` "
                       "registradas. Un cero no es una mejora; es el instrumento sin medir")
    ns = [int(x) for x in open(conteo).read().split()]
    if not ns:
        raise Falla(3, "el guardia de grep no registro bytes: el conteo no existe")
    if p.returncode != 0:
        raise Falla(3, "el hook no paso el fixture (rc=%d): si rechaza, corta en el "
                       "primer acierto y el conteo queda corto" % p.returncode)
    contenido = [n for n in ns if n >= umbral]
    if not contenido:
        raise Falla(3, "cero pasadas sobre el texto: el guardia midio su propia ausencia "
                       "(ninguna invocacion supero %d B)" % umbral)
    vistos = bytes_vistos(repo, fixture_rel)
    bytes_esc = sum(contenido)
    return {
        "pases_contenido": len(contenido),
        "greps_totales": len(ns),
        "bytes_escaneados": bytes_esc,
        "bytes_indexados": vistos,
        "ratio_pases": round(bytes_esc / vistos, 2) if vistos > 0 else 0.0,
    }


def medir_coste(repo, hook, work):
    """Stagea el fixture de conteo, cuenta las pasadas y limpia el indice."""
    ruta = FIXTURE_PASES
    with open(os.path.join(repo, ruta), "wb") as fh:
        fh.write(texto_de(FIXTURE_PASES_BYTES))
    sh(["git", "add", "-f", "--", ruta], repo)
    try:
        vistos = bytes_vistos(repo, ruta)
        if vistos < 0.9 * FIXTURE_PASES_BYTES:
            raise Falla(3, "el fixture de conteo recibiria %d B de %d B: git lo clasifico "
                           "como binario y las pasadas contarian el vacio"
                        % (vistos, FIXTURE_PASES_BYTES))
        return pases_contenido(repo, hook, work, ruta)
    finally:
        sh(["git", "rm", "-q", "--cached", "--", ruta], repo)
        sobra = os.path.join(repo, ruta)
        if os.path.exists(sobra):
            os.unlink(sobra)


def medir_comp(cmd, repo, reps=2):
    mejor = None
    for _ in range(reps):
        p = subprocess.run(["/usr/bin/time", "-l"] + cmd, cwd=repo, capture_output=True, text=True)
        m = RE_REAL.search(p.stderr)
        if not m:
            raise Falla(20, "no se pudo cronometrar un componente")
        v = float(m.group(1))
        mejor = v if mejor is None else min(mejor, v)
    return round(mejor, 3)


def rama(pts, fit):
    """Las cuatro ramas: tres dictadas por el dueno + la que el barrido puede medir
    y la trichotomia no nombra (lineal y caro)."""
    p6 = next((p for p in pts if abs(p["mib"] - MIB_DECISION) < 1e-9), None)
    t6 = p6["t_contenido_s"] if p6 else fit["a"] + fit["b"] * MIB_DECISION
    rss6 = p6["rss_contenido_mb"] if p6 else 0.0
    tps = [p["t_contenido_s"] / p["mib"] for p in pts if p["mib"] >= 1.0]
    ratio = (max(tps) / min(tps)) if tps and min(tps) > 0 else float("inf")
    # La linealidad se juzga con R^2, NO con el cociente de s/MiB aparentes: ese
    # cociente mezcla el intercepto fijo (~1 s de arranque del hook) con la
    # pendiente, y llama "no lineal" a una recta por el solo hecho de tener
    # puntos pequeños. Mismo defecto que medir la excepcion en vez del escaneo.
    lineal = fit["r2"] >= 0.98
    if t6 < 2.0 and rss6 < 500:
        return ("SUPERSTICION", lineal, ratio,
                f"{MIB_DECISION:.0f} MiB cuesta {t6:.2f} s: no hay coste que justifique el fail-open")
    if not lineal or rss6 > 500 or t6 > 10.0:
        return ("PRUDENCIA", lineal, ratio,
                f"{MIB_DECISION:.0f} MiB cuesta {t6:.2f} s (RSS {rss6:.0f} MB, s/MiB max/min {ratio:.2f}): "
                "el tope debe ser el punto de la curva, no un 2 MiB redondo")
    return ("LINEAL_CARO", lineal, ratio,
            f"{MIB_DECISION:.0f} MiB cuesta {t6:.2f} s: lineal y por encima de 2 s. "
            "El fail-open esta justificado, pero el tope no es optimo y el coste POR BYTE es mejorable")


def codo(pts, fit, presupuesto):
    """Mayor tamano medido cuyo coste cae bajo el presupuesto (medido, no extrapolado)."""
    ok = [p["mib"] for p in pts if p["t_contenido_s"] <= presupuesto]
    if ok:
        return max(ok), "medido"
    mib = (presupuesto - fit["a"]) / fit["b"] if fit["b"] > 0 else 0.0
    return round(max(mib, 0.0), 2), "extrapolado"


def ajuste(pts):
    """Minimos cuadrados t = a + b*mib sobre los puntos medidos."""
    n = len(pts)
    sx = sum(p["mib"] for p in pts)
    sy = sum(p["t_contenido_s"] for p in pts)
    sxx = sum(p["mib"] ** 2 for p in pts)
    sxy = sum(p["mib"] * p["t_contenido_s"] for p in pts)
    den = n * sxx - sx * sx
    if den == 0:
        return {"a": 0.0, "b": 0.0, "r2": 0.0, "s_por_mib_cola": 0.0}
    b = (n * sxy - sx * sy) / den
    a = (sy - b * sx) / n
    ss_tot = sum((p["t_contenido_s"] - sy / n) ** 2 for p in pts)
    ss_res = sum((p["t_contenido_s"] - (a + b * p["mib"])) ** 2 for p in pts)
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    mitad = pts[len(pts) // 2]
    ultimo = pts[-1]
    cola = ((ultimo["t_contenido_s"] - mitad["t_contenido_s"]) /
            (ultimo["mib"] - mitad["mib"])) if ultimo["mib"] != mitad["mib"] else 0.0
    return {"a": a, "b": b, "r2": r2, "s_por_mib_cola": cola}


def residuales_entre(pts, reps):
    """Desviacion de cada punto contra sus vecinos, en errores del propio punto.

    `disp_cont` dice si la maquina midio bien ESE punto; esto dice si el punto
    pertenece a la curva. Devuelve `(residuales, mediana_se)` alineados con
    `pts`, o `(None, None)` si no se puede calcular (sin `t_contenido_max_s`,
    con menos de 2 reps —sin muestra no hay error— o con todos los errores en
    cero).
    """
    if not pts or len(pts) < 3 or not isinstance(reps, int) or reps < 2:
        return None, None
    ses = []
    for p in pts:
        mx = p.get("t_contenido_max_s")
        if not isinstance(mx, (int, float)):
            return None, None
        ses.append(max(0.0, mx - p["t_contenido_s"]) / 2.0 / (reps ** 0.5))
    orden = sorted(ses)
    med = orden[len(orden) // 2] if len(orden) % 2 else (orden[len(orden) // 2 - 1] + orden[len(orden) // 2]) / 2.0
    piso = max(med, 0.0)
    if piso <= 0:
        return None, None
    t = [p["t_contenido_s"] for p in pts]
    m = [p["mib"] for p in pts]
    out = []
    for i in range(len(pts)):
        if i == 0:
            pred = t[1] + (t[2] - t[1]) / (m[2] - m[1]) * (m[0] - m[1])
        elif i == len(pts) - 1:
            pred = t[i - 1] + (t[i - 1] - t[i - 2]) / (m[i - 1] - m[i - 2]) * (m[i] - m[i - 1])
        else:
            pred = t[i - 1] + (t[i + 1] - t[i - 1]) * (m[i] - m[i - 1]) / (m[i + 1] - m[i - 1])
        out.append(abs(t[i] - pred) / max(ses[i], piso))
    return out, med


def es_sello(dato):
    """True si `dato` tiene forma de sello completo y no de salida parcial."""
    return isinstance(dato, dict) and any(k in dato for k in SELLO_CLAVES)


def r2_de(dato):
    """El R^2 que porta un sello, o None si no lo porta legible."""
    aj = dato.get("ajuste") if isinstance(dato, dict) else None
    r2 = aj.get("r2") if isinstance(aj, dict) else None
    if isinstance(r2, bool) or not isinstance(r2, (int, float)):
        return None
    return float(r2)


def forma_de_sello(ruta):
    """True si el JSON que ya vive en `ruta` tiene forma de sello completo.

    Pregunta por las claves que solo escribe la corrida completa. Si el path no
    existe, no es JSON o es una salida parcial, no hay sello que proteger: un
    `--solo-pases --json nuevo.json` legitimo no se bloquea.
    """
    if not os.path.isfile(ruta):
        return False
    try:
        with open(ruta, encoding="utf-8") as fh:
            dato = json.load(fh)
    except (OSError, ValueError):
        return False
    return es_sello(dato)


def guardia_sello(ruta, force):
    """Un `--solo-*` no puede dejar un sello con forma de salida parcial."""
    if force:
        print(f"FORCE_SELLO: sobrescribo {ruta} con una salida PARCIAL (declarado: el "
              f"sello deja de ser sello y F10/F11/F12 se quedan sin objeto)",
              file=sys.stderr)
        return
    if forma_de_sello(ruta):
        raise Falla(3, f"SELLO_NO_SOBREESCRIBIBLE: {ruta} tiene forma de sello "
                       f"({', '.join(SELLO_CLAVES)}) y esta corrida escribe una salida "
                       f"parcial: la sobrescritura borra coste, ajuste, veredicto y "
                       f"_retirado de una vez, y el guardian del maestro leeria el vacio "
                       f"como si fuera el sello. El sello se regenera con la corrida "
                       f"COMPLETA (sin --solo-*); degradarlo a proposito se declara con "
                       f"--force-sello")


# HUELLA-GUARDIA-OBJETO-ENCOGIDO-20261021
# HUELLA-GUARDIA-REPS-MINIMO-20261021
# HUELLA-GUARDIA-CURVA-ROTA-20261021
def guardia_calidad(ruta, previo, r2_nuevo, veredicto_nuevo, emisor_nuevo, hook_blob, force,
                    pts=None, fit=None, force_ventana=False, reps=None, declaro_reps=False,
                    force_curva=False, force_regimen=False):
    """Un sello no se reescribe con una medida peor sin decirlo.

    El OBJETO medido es el hook, y lo dice `hook_blob`; el EMISOR dice que codigo
    lo midio. El eje del juicio es el OBJETO: con el mismo hook la recta es
    comparable aunque el emisor cambie; si el hook cambia no hay nada que comparar
    y solo se declara. El TAMANO del objeto entra al juicio (`len(puntos)`): un
    ajuste sobre 3 puntos no es comparable con uno sobre 6, porque con menos puntos
    el R^2 sube solo — «mejor ajuste» puede ser un objeto mas chico. La VENTANA de
    dispersion (`VENTANA_DISP_CONT`) es condicion de comparabilidad y no un dato
    informativo: una corrida que dispersa mas que la que certifico el sello midio
    en otras condiciones. Ajuste peor, objeto encogido o corrida fuera de ventana
    => RC 1 sin escribir; `--force-sello` / `--force-ventana` lo declaran y
    escriben. La VENTANA, ademas, necesita muestra: por debajo de
    `REPS_MIN_VENTANA` repeticiones por punto `disp_cont` vale 1.00x por
    construccion, asi que esa corrida no midio la ventana (REPLICA_INSUFICIENTE
    RC 1) y sellarla sin ventana se declara con `--declaro-reps`, que deja el
    sello marcado `ventana_vacia`. Devuelve el estado que el sello porta. La
    CURVA entra como segunda dimension, y no por `R^2` (load-dependent, retirado
    como juez en el v2): monotonia en bytes —el coste no cae al crecer el
    archivo— y `residual_entre` contra los vecinos, con `RESIDUO_K` sacado del
    sello. Curva no monotona o residual sobre K => CURVA_ROTA RC 1; su bandera
    es `--force-curva`, no `--force-sello` (que perdona la degradacion, no la
    medicion rota). El REGIMEN entra antes que la curva: cada punto porta las dos
    ramas (`rc_tope`, `rc_contenido`), asi que un cruce de `rc_contenido` entre
    puntos consecutivos son dos funciones en el mismo eje — la curva deja de ser
    comparable (CURVA_NO_EVALUABLE) y la corrida no escribe el sello
    (REGIMEN_CRUZADO RC 1) salvo `--force-regimen`. El cruce de `rc_tope` se
    declara y NO gatea: gobierna `t_tope_s`, que este gate no juzga, y el sello
    sano lo atraviesa monotono (R^2 0.9979). Un eje plano se declara plano
    (REGIMEN_CONSTANTE): un eje plano y un eje no implementado se ven igual.
    """
    estado = {"reps": reps, "ventana_vacia": False, "curva_rota": False,
              "residual_entre": None, "mediana_se": None, "regimen_cruzado": False,
              "rc_por_punto": None, "regimenes_cruzados": None, "curva_juzgada": False}
    # La vacua no es un defecto del sello previo sino de ESTA corrida, asi que se
    # juzga antes de mirar el sello: una PRIMERA escritura tambien puede sellar
    # una ventana que no se midio.
    if pts is not None:
        n_reps = reps if isinstance(reps, int) and reps > 0 else None
        trae = "sin declarar" if n_reps is None else f"{n_reps}"
        if n_reps is None or n_reps < REPS_MIN_VENTANA:
            if not declaro_reps:
                raise Falla(1, f"REPLICA_INSUFICIENTE: la corrida trae {trae} rep(s) por punto y "
                               f"`disp_cont` es max/min, asi que con una sola repeticion vale "
                               f"1.00x en todos los puntos: ese 1.00x no es una dispersion "
                               f"medida, es la ausencia de muestra, y entra en cualquier ventana. "
                               f"Por debajo de {REPS_MIN_VENTANA} reps la ventana de "
                               f"{VENTANA_DISP_CONT:.2f}x no se midio y {ruta} queda intacto. Se "
                               f"repite con --reps {REPS_MIN_VENTANA} o mas; sellar sin ventana "
                               f"se declara con --declaro-reps")
            estado["ventana_vacia"] = True
            print(f"VENTANA_VACUA_DECLARADA: la corrida trae {trae} rep(s) por punto sobre un piso "
                  f"de {REPS_MIN_VENTANA}; su 1.00x no mide dispersion y el sello que se escriba "
                  f"queda marcado ventana_vacia=true — lo que certifica NO incluye la ventana",
                  file=sys.stderr)
        elif declaro_reps:
            print(f"DECLARACION_SIN_OBJETO: --declaro-reps sobra con {trae} rep(s) por punto: la "
                  f"ventana de {VENTANA_DISP_CONT:.2f}x si se midio (se declara y se ignora)",
                  file=sys.stderr)
    # El REGIMEN es propiedad de ESTA corrida, no del sello previo: se censa
    # antes de mirarlo. La rama juzgada es `rc_contenido` (la curva mide el
    # escaneo real); `rc_tope` gobierna `t_tope_s`, que este gate no juzga.
    if pts:
        estado["rc_por_punto"] = [
            {"mib": p.get("mib"), "rc_tope": p.get("rc_tope"),
             "rc_contenido": p.get("rc_contenido")} for p in pts
        ]
        cruce_cont = []
        cruce_tope = []
        for a, b in zip(pts, pts[1:]):
            for rama, clave, caja in (("contenido", "rc_contenido", cruce_cont),
                                      ("tope", "rc_tope", cruce_tope)):
                ra, rb = a.get(clave), b.get(clave)
                if ra is not None and rb is not None and ra != rb:
                    caja.append({"de_mib": a.get("mib"), "a_mib": b.get("mib"), "rama": rama,
                                 "rc_de": ra, "rc_a": rb})
        estado["regimenes_cruzados"] = {"contenido": cruce_cont, "tope": cruce_tope}
        if cruce_tope:
            print("REGIMEN_TOPE: " + "; ".join(
                f"{c['de_mib']:g} -> {c['a_mib']:g} MiB (rc_tope {c['rc_de']} -> {c['rc_a']})"
                for c in cruce_tope) + " — la rama TOPE cambia de funcion ahi, pero `t_tope_s` "
                "no es la curva que este gate juzga: se declara y no se bloquea", file=sys.stderr)
        if not cruce_cont:
            print(f"REGIMEN_CONSTANTE: rc_contenido plano en {len(pts)} punto(s) "
                  f"(rc={pts[0].get('rc_contenido')}); la rama juzgada es una sola y la curva "
                  f"es comparable", file=sys.stderr)
        else:
            detalle_reg = "; ".join(
                f"{c['de_mib']:g} -> {c['a_mib']:g} MiB (rc_contenido {c['rc_de']} -> {c['rc_a']})"
                for c in cruce_cont)
            estado["regimen_cruzado"] = True
            if not force_regimen:
                raise Falla(1, f"REGIMEN_CRUZADO: {detalle_reg}. Dos puntos consecutivos "
                               f"midieron ramas distintas del regimen CONTENIDO, asi que son "
                               f"dos funciones en el mismo eje y la curva deja de ser "
                               f"comparable con la del sello (CURVA_NO_EVALUABLE): {ruta} "
                               f"queda intacto. Si el cruce es deliberado se declara con "
                               f"--force-regimen")
            print(f"REGIMEN_CRUZADO_FORZADO: {detalle_reg} (declarado; el sello queda con "
                  f"regimen_cruzado=true y sin curva juzgada)", file=sys.stderr)
    if not es_sello(previo):
        return estado  # no habia sello: una salida parcial no es objeto que degradar
    emisor_prev = previo.get("emisor_blob")
    r2_prev = r2_de(previo)
    ver_prev = previo.get("veredicto")
    mismo_emisor = (isinstance(emisor_prev, str) and len(emisor_prev) == 40
                    and emisor_prev == emisor_nuevo)
    if not mismo_emisor:
        if isinstance(emisor_prev, str) and len(emisor_prev) == 40:
            print(f"EMISOR_CAMBIADO: sello {emisor_prev[:12]} (R^2 "
                  f"{'sin ajuste' if r2_prev is None else '%.4f' % r2_prev}, {ver_prev}) -> "
                  f"vivo {emisor_nuevo[:12]} (R^2 {r2_nuevo:.4f}, {veredicto_nuevo})",
                  file=sys.stderr)
        else:
            print(f"SELLO_PREVIO_SIN_EMISOR: {ruta} no declara que codigo lo escribio; se "
                  f"reescribe con {emisor_nuevo[:12]}", file=sys.stderr)
    # El eje es el OBJETO, no el emisor. Antes esta comparacion vivia DENTRO de
    # `not mismo_emisor`, asi que un hook nuevo medido por el mismo codigo pasaba
    # como mismo objeto sin que nadie lo mirara.
    prev_hook = previo.get("hook_blob")
    if not (isinstance(prev_hook, str) and len(prev_hook) == 40):
        print(f"SELLO_PREVIO_SIN_HOOK: {ruta} no declara que objeto midio; sin identidad "
              f"del objeto no hay comparacion posible y no se juzga", file=sys.stderr)
        return estado
    if prev_hook != hook_blob:
        print("OBJETO_DISTINTO: el hook cambio; el ajuste nuevo no es comparable con el del "
              "sello y no se juzga", file=sys.stderr)
        return estado
    if not mismo_emisor:
        print("MISMO_OBJETO: el hook no cambio; el ajuste SI es comparable (el emisor "
              "declara quien midio, no que se midio)", file=sys.stderr)
    # La ventana es condicion de comparabilidad: fuera de ella la recta mide la
    # maquina, no el hook. Por eso gatea y no se suma a `motivos` (que
    # `--force-sello` puede perdonar de una vez): solo `--force-ventana` la abre.
    disp_prev = None
    dispersion_prev = previo.get("dispersion")
    if isinstance(dispersion_prev, dict):
        disp_prev = dispersion_prev.get("max_ratio_cont")
    if isinstance(disp_prev, (int, float)) and disp_prev > VENTANA_DISP_CONT:
        print(f"SELLO_PREVIO_FUERA_DE_VENTANA: el sello vivo en {ruta} se certifico "
              f"dispersando {disp_prev:.2f}x, mas que la ventana {VENTANA_DISP_CONT:.2f}x; "
              f"la ventana sigue siendo {VENTANA_DISP_CONT:.2f}x", file=sys.stderr)
    disp_nuevo = max((p.get("disp_cont") or 0.0) for p in pts) if pts else None
    if disp_nuevo is not None and disp_nuevo > VENTANA_DISP_CONT:
        if not force_ventana:
            raise Falla(1, f"FUERA_DE_VENTANA: la corrida dispersa {disp_nuevo:.2f}x "
                           f"(max/min por punto) sobre una ventana de {VENTANA_DISP_CONT:.2f}x. "
                           f"Fuera de la ventana la recta mide la maquina y no el hook, asi que "
                           f"el sello que vive en {ruta} queda intacto. Si es ruido, se sube "
                           f"--reps y se repite en calma; si la escritura es deliberada se "
                           f"declara con --force-ventana")
        print(f"FUERA_DE_VENTANA_FORZADO: {disp_nuevo:.2f}x > {VENTANA_DISP_CONT:.2f}x; "
              f"reescribo {ruta} (declarado)", file=sys.stderr)
    # La CURVA es el objeto y la ventana es la precision: un punto puede estar
    # bien medido y fuera de lugar. Dos ejes, ambos fuera de `motivos` (que
    # `--force-sello` perdona entero): solo `--force-curva` los abre.
    rota = []
    if pts and estado["regimen_cruzado"]:
        # Con dos ramas en el eje, la monotonia compara funciones distintas: el
        # eje no es «no evaluable» por prudencia, es que no hay una sola curva.
        print("CURVA_NO_EVALUABLE: la corrida cruza de rama CONTENIDO, asi que monotonia y "
              "residuo compararian dos funciones; no se juzga la curva", file=sys.stderr)
    elif pts:
        estado["curva_juzgada"] = True
        for a, b in zip(pts, pts[1:]):
            if a["t_contenido_s"] > b["t_contenido_s"]:
                rota.append(f"MONOTONIA rota {a['mib']:g} -> {b['mib']:g} MiB "
                            f"({a['t_contenido_s']:.2f} s > {b['t_contenido_s']:.2f} s: un archivo "
                            f"mas grande costo menos)")
        resid, med_se = residuales_entre(pts, reps)
        estado["residual_entre"] = resid
        estado["mediana_se"] = med_se
        if resid is None:
            print(f"RESIDUO_NO_CALCULABLE: sin error por punto (hacen falta 2 o mas reps y "
                  f"`t_contenido_max_s`) no hay contra que normalizar el residuo; la curva se "
                  f"juzga solo por monotonia", file=sys.stderr)
        else:
            peor = max(range(len(resid)), key=lambda i: resid[i])
            if resid[peor] > RESIDUO_K:
                rota.append(f"RESIDUO {resid[peor]:.2f} en {pts[peor]['mib']:g} MiB sobre K "
                            f"{RESIDUO_K:.2f} (desvio contra sus vecinos en errores del propio "
                            f"punto: preciso y fuera de la curva)")
    if rota:
        detalle_curva = "; ".join(rota)
        estado["curva_rota"] = True
        if not force_curva:
            raise Falla(1, f"CURVA_ROTA: {detalle_curva}. La curva es el objeto: fuera de la "
                           f"forma no hay ley que sellar, y {ruta} queda intacto. Si el hook "
                           f"cambio de regimen o la maquina se cruzo, se repite; si la escritura "
                           f"es deliberada se declara con --force-curva")
        print(f"CURVA_ROTA_FORZADA: {detalle_curva} (declarado; el sello queda con "
              f"curva_rota=true)", file=sys.stderr)
    motivos = []
    # El tamano del objeto se juzga ANTES que la calidad del ajuste: si el objeto
    # encogio, el R^2 no es comparable y decir «mejor ajuste» seria confundir la
    # calidad con el tamano.
    prev_pts = previo.get("puntos")
    n_prev = len(prev_pts) if isinstance(prev_pts, list) else None
    n_nuevo = len(pts) if isinstance(pts, list) else None
    encogido = False
    if n_prev is None:
        print(f"SELLO_PREVIO_SIN_PUNTOS: {ruta} no porta la lista de puntos; no hay tamano "
              f"contra el que comparar los {n_nuevo} puntos nuevos", file=sys.stderr)
    elif n_nuevo is not None and n_nuevo < n_prev:
        encogido = True
        motivos.append(f"OBJETO_ENCOGIDO {n_prev} -> {n_nuevo} puntos (con menos puntos el R^2 "
                       f"sube solo: un ajuste «mejor» sobre un objeto mas chico no es una "
                       f"medida mejor)")
    elif n_nuevo is not None and n_nuevo > n_prev:
        print(f"OBJETO_CRECIDO: {n_prev} -> {n_nuevo} puntos; el ajuste puede caer sin que el "
              f"objeto empeore (se declara)", file=sys.stderr)
    if r2_prev is None:
        print(f"SELLO_PREVIO_SIN_AJUSTE: {ruta} no porta R^2 legible; se reescribe con un "
              f"sello completo (R^2 {r2_nuevo:.4f})", file=sys.stderr)
    elif r2_nuevo < r2_prev - R2_TOLERANCIA:
        motivos.append(f"R^2 {r2_prev:.4f} -> {r2_nuevo:.4f} (cae {r2_prev - r2_nuevo:.4f}, "
                       f"mas de la tolerancia {R2_TOLERANCIA})")
    # El veredicto es CONCLUSION del OBJETO: si el hook no cambio (ya verificado
    # arriba), una conclusion peor es una medida peor, la haya medido quien la
    # haya medido. Antes este eje colgaba de `mismo_emisor`, asi que un emisor
    # nuevo degradaba el veredicto sin bloqueo (medido: una copia del sello paso
    # de LINEAL_CARO a PRUDENCIA con RC 0).
    if ver_prev != veredicto_nuevo:
        o_prev = ORDEN_VEREDICTO.get(ver_prev) if isinstance(ver_prev, str) else None
        o_nue = ORDEN_VEREDICTO.get(veredicto_nuevo, 1)
        if o_prev is None or o_nue > o_prev:
            motivos.append(f"veredicto {ver_prev} -> {veredicto_nuevo}")
        else:
            print(f"VEREDICTO_CAMBIA: {ver_prev} -> {veredicto_nuevo} (conclusion, no calidad "
                  f"de medida: se declara y no se bloquea)", file=sys.stderr)
    if not motivos:
        return estado
    detalle = "; ".join(motivos)
    # Un rechazo que no muestra POR QUE se rechaza invita al --force-sello a
    # ciegas. El juicio corre antes de la tabla, asi que la evidencia se imprime
    # aqui: sin los puntos, el operador no puede distinguir "la maquina estaba
    # cargada" de "el hook cambio de regimen".
    if pts and fit:
        print("  puntos de la corrida rechazada (disp = max/min por punto):", file=sys.stderr)
        for q in pts:
            pred = fit["a"] + fit["b"] * q["mib"]
            print(f"    {q['mib']:>5.1f} MiB  medido {q['t_contenido_s']:>6.2f} s  "
                  f"recta {pred:>6.2f} s  residuo {q['t_contenido_s'] - pred:>+6.2f} s  "
                  f"disp {q.get('disp_cont', 0.0):.2f}x", file=sys.stderr)
    if force:
        if encogido:
            print(f"OBJETO_ENCOGIDO_FORZADO: reescribo {ruta} con {n_nuevo} puntos sobre un "
                  f"sello de {n_prev} (declarado)", file=sys.stderr)
        print(f"SELLO_DEGRADADO_FORZADO: reescribo {ruta} pese a {detalle} (declarado)",
              file=sys.stderr)
        return estado
    quien = ("el MISMO emisor" if mismo_emisor
             else f"emisor nuevo {emisor_nuevo[:12]} sobre el MISMO hook")
    raise Falla(1, f"SELLO_DEGRADADO: {detalle}. El sello que ya vive en {ruta} certifica una "
                   f"medida que esta corrida no sostiene ({quien}): reescribirlo cambiaria lo "
                   f"medido por lo que la maquina o el tamano del objeto dejan medir. El sello "
                   f"queda intacto. Si la degradacion es deliberada se declara con --force-sello; "
                   f"si es ruido, se sube --reps y se repite con la maquina en calma")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Barrido del coste real de la capa de contenido (LIMITE_BYTES)")
    ap.add_argument("--repo", default=".", help="repo origen (de donde se leen hook y baseline)")
    ap.add_argument("--reps", type=int, default=2, help="repeticiones por punto (se toma el minimo)")
    ap.add_argument("--sizes", default=",".join(str(s) for s in TAMANOS_MIB), help="tamanos en MiB, separados por coma")
    ap.add_argument("--work", default=None, help="directorio de trabajo (por defecto temporal)")
    ap.add_argument("--keep", action="store_true", help="no borrar el directorio de trabajo")
    ap.add_argument("--json", default=None, help="escribir puntos y veredicto en JSON")
    ap.add_argument("--solo-pases", dest="solo_pases", action="store_true",
                    help="solo cuenta las pasadas de contenido (sin curva): el verbo que "
                         "cobra el coste en el maestro, ~1.5 s en vez de ~2 min")
    ap.add_argument("--solo-rss", dest="solo_rss", action="store_true",
                    help="solo mide el RSS de la capa de contenido a 1 y 12 MiB: el verbo "
                         "que cobra la memoria, ~25 s (el de 12 MiB escanea de verdad)")
    ap.add_argument("--hook", default=None,
                    help="hook a medir (por defecto tools/hooks/pre-commit del repo). Permite "
                         "ejercer los falsadores sobre una COPIA sin tocar el hook real")
    ap.add_argument("--force-sello", dest="force_sello", action="store_true",
                    help="declara una degradacion DELIBERADA del sello: que un --solo-* lo "
                         "deje en salida parcial (RC 3 sin el) o que la corrida completa lo "
                         "reescriba con un ajuste peor u un objeto encogido (RC 1 sin el)")
    ap.add_argument("--force-ventana", dest="force_ventana", action="store_true",
                    help="declara una corrida FUERA DE VENTANA de dispersion "
                         f"(> {VENTANA_DISP_CONT:.2f}x): sin el, esa corrida no escribe el "
                         "sello (RC 1)")
    ap.add_argument("--declaro-reps", dest="declaro_reps", action="store_true",
                    help="declara que la corrida sella SIN haber medido la ventana de dispersion "
                         f"por falta de replicas (< {REPS_MIN_VENTANA} por punto): sin el, esa "
                         "corrida no escribe el sello (REPLICA_INSUFICIENTE, RC 1)")
    ap.add_argument("--force-curva", dest="force_curva", action="store_true",
                    help="declara una curva ROTA (no monotona en bytes, o un punto a mas de "
                         f"K={RESIDUO_K:.2f} errores de sus vecinos): sin el, esa corrida no "
                         "escribe el sello (CURVA_ROTA, RC 1)")
    ap.add_argument("--force-regimen", dest="force_regimen", action="store_true",
                    help="declara que la corrida cruza de rama CONTENIDO (dos funciones en el "
                         "mismo eje): sin el, esa corrida no escribe el sello "
                         "(REGIMEN_CRUZADO, RC 1)")
    args = ap.parse_args(argv)

    if not os.path.isfile("/usr/bin/time"):
        print("FALLA CERRADA: falta /usr/bin/time -l — sin RSS no hay medicion, y sin medicion no hay veredicto")
        return 20

    repo_src = os.path.abspath(args.repo)
    hook_src = os.path.abspath(args.hook) if args.hook else os.path.join(repo_src, HOOK_REL)
    if not os.path.isfile(hook_src):
        print(f"FALLA CERRADA: falta {HOOK_REL if not args.hook else args.hook} en {repo_src}")
        return 20
    # El blob del hook entra al JSON: sin el, un baseline de memoria no dice a
    # QUE codigo pertenece, y «el mismo nombre, dos objetos» se cuela entero.
    rc_blob, hook_blob, _ = sh(["git", "hash-object", hook_src], repo_src)
    if rc_blob != 0 or len(hook_blob.strip()) != 40:
        print(f"FALLA CERRADA: no pude hashear {hook_src}: sin identidad del objeto no hay baseline")
        return 20
    hook_blob = hook_blob.strip()
    # El emisor se hashea a si mismo: el sello declara QUE codigo lo escribio,
    # y el guardian del maestro (F12) compara este blob con el barrido vivo.
    # Sin identidad del emisor, un sello puede ser de cualquier version anterior.
    rc_emi, emisor_blob, _ = sh(["git", "hash-object", os.path.abspath(__file__)], repo_src)
    if rc_emi != 0 or len(emisor_blob.strip()) != 40:
        print("FALLA CERRADA: no pude hashear el emisor; sin identidad el sello no se ata a su fuente")
        return 20
    emisor_blob = emisor_blob.strip()

    work = args.work or tempfile.mkdtemp(prefix="barrido_mb.")
    os.makedirs(work, exist_ok=True)
    try:
        repo, hook_abierto, linea_delta = preparar(work, hook_src, os.path.join(repo_src, BASELINE_REL))
        if args.solo_pases:
            if args.json:
                guardia_sello(args.json, args.force_sello)
            coste = medir_coste(repo, hook_abierto, work)
            print()
            print(f"PASES CONTENIDO {coste['pases_contenido']} sobre el texto "
                  f"({coste['greps_totales']} invocaciones -qiE; "
                  f"{coste['bytes_escaneados']} B escaneados / {coste['bytes_indexados']} B "
                  f"indexados = {coste['ratio_pases']}x)")
            print(f"DELTA      el unico literal cambiado es el de la linea {linea_delta + 1} "
                  f"(LIMITE_BYTES); no es un conteo de lineas, es su posicion")
            if args.json:
                with open(args.json, "w", encoding="utf-8") as fh:
                    json.dump({
                        "huella": "HUELLA-BARRIDO-PASES-CONTENIDO-20261021",
                        "fixture": FIXTURE_PASES,
                        "fixture_bytes": FIXTURE_PASES_BYTES,
                        "umbral_contenido_b": UMBRAL_CONTENIDO,
                        "literal_linea": linea_delta + 1,
                        "coste": coste,
                    }, fh, ensure_ascii=False, indent=2)
                print(f"JSON       {args.json}")
            return 0
        if args.solo_rss:
            if args.json:
                guardia_sello(args.json, args.force_sello)
            rss = {}
            for mib in TAMANOS_RSS:
                nbytes = int(round(mib * MIB))
                ruta = f"rss_{str(mib).replace('.', 'p')}mib.txt"
                with open(os.path.join(repo, ruta), "wb") as fh:
                    fh.write(texto_de(nbytes))
                sh(["git", "add", "-f", "--", ruta], repo)
                vistos = bytes_vistos(repo, ruta)
                if vistos < 0.9 * nbytes:
                    raise Falla(3, f"el regimen CONTENIDO recibiria {vistos} B de {nbytes} B: "
                                   "el RSS medido seria el de la excepcion, no el del escaneo")
                m = medir(hook_abierto, repo)
                if m["rc"] not in (0, 1):
                    raise Falla(4, f"{ruta}: el regimen CONTENIDO devolvio rc={m['rc']} (inesperado)")
                rss[mib] = {"mib": mib, "bytes": nbytes, "rss_mb": m["rss_mb"],
                            "seg": round(m["seg"], 2), "bytes_vistos": vistos}
                print(f"RSS {mib:>5.1f} MiB  {m['rss_mb']:>6.1f} MB  ({m['seg']:.2f} s, "
                      f"{vistos} B vistos)")
                sh(["git", "rm", "-q", "--cached", "--", ruta], repo)
                os.unlink(os.path.join(repo, ruta))
            bajo, alto = TAMANOS_RSS[0], TAMANOS_RSS[1]
            pendiente = (rss[alto]["rss_mb"] - rss[bajo]["rss_mb"]) / (alto - bajo)
            print(f"RSS PENDIENTE {pendiente:.2f} MB/MiB entre {bajo:.1f} y {alto:.1f} MiB "
                  f"({rss[bajo]['rss_mb']:.1f} -> {rss[alto]['rss_mb']:.1f} MB)")
            if args.json:
                with open(args.json, "w", encoding="utf-8") as fh:
                    json.dump({
                        "huella": "HUELLA-BARRIDO-RSS-20261021",
                        "hook_blob": hook_blob,
                        "puntos": [rss[k] for k in TAMANOS_RSS],
                        "rss": {"mib_1": rss[bajo]["rss_mb"], "mib_12": rss[alto]["rss_mb"],
                                "mb_por_mib": round(pendiente, 2)},
                    }, fh, ensure_ascii=False, indent=2)
                print(f"JSON       {args.json}")
            return 0
        tamanos = [float(s) for s in args.sizes.split(",") if s.strip()]
        pts = []

        print()
        print(f"{'MiB':>6} {'B':>10} {'t_tope_s':>9} {'t_cont_s':>9} {'cpu_s':>6} {'d_cpu':>6} "
              f"{'rss_top_MB':>10} {'rss_cont_MB':>11} {'vistos':>10} {'s/MiB':>7}")
        print("-" * 100)

        for mib in tamanos:
            nbytes = int(round(mib * MIB))
            ruta = f"big_{str(mib).replace('.', 'p')}mib.txt"
            with open(os.path.join(repo, ruta), "wb") as fh:
                fh.write(texto_de(nbytes))
            sh(["git", "add", "-f", "--", ruta], repo)

            vistos = bytes_vistos(repo, ruta)
            if vistos < 0.9 * nbytes:
                raise Falla(3, f"el regimen CONTENIDO recibiria {vistos} B de {nbytes} B: "
                               "git clasifico el fixture como binario o el filtro no paso las lineas. "
                               "Medir esto seria medir la excepcion, no el escaneo")

            tope = None
            tope_segs = []
            for _ in range(max(1, args.reps)):
                m = medir(hook_src, repo)
                tope_segs.append(m["seg"])
                tope = m if tope is None else (m if m["seg"] < tope["seg"] else tope)
            cont = None
            cont_segs = []
            cont_cpus = []
            for _ in range(max(1, args.reps)):
                m = medir(hook_abierto, repo)
                cont_segs.append(m["seg"])
                cont_cpus.append(m["cpu"])
                cont = m if cont is None else (m if m["seg"] < cont["seg"] else cont)

            if nbytes > 2 * MIB:
                if not (tope["rc"] == 1 and "LIMITE_MB" in tope["out"]):
                    raise Falla(4, f"{ruta} ({nbytes} B) sobre el tope y el hook real NO imprimio LIMITE_MB "
                                   f"(rc={tope['rc']}): no hay dos regimenes que comparar")
            if cont["rc"] not in (0, 1):
                raise Falla(4, f"{ruta}: el regimen CONTENIDO devolvio rc={cont['rc']} (inesperado)")

            p = {
                "mib": mib,
                "bytes": nbytes,
                "t_tope_s": round(tope["seg"], 2),
                "t_contenido_s": round(cont["seg"], 2),
                # max/min de las reps: la dispersion se MIDE en la corrida, no
                # se declara de memoria. Es lo que hace visible que una banda
                # de +-50 % sobre segundos es mas estrecha que el ruido.
                "t_contenido_max_s": round(max(cont_segs), 2),
                "disp_cont": round(max(cont_segs) / min(cont_segs), 2) if min(cont_segs) > 0 else 0.0,
                # `cont` es la rep que gano el minimo de wall, asi que `cont["cpu"]`
                # es el CPU de ESA invocacion: el par (t_contenido_s, t_cpu_s) es un
                # solo objeto. Con minimos separados por metrica el par seria de dos
                # corridas y `wall_menos_cpu_s` no mediria el resto de ninguna.
                # Ese resto puede ser negativo (user+sys se suma por CPU; ver medir()).
                "t_cpu_s": round(cont["cpu"], 2),
                "t_cpu_max_s": round(max(cont_cpus), 2),
                "disp_cpu": round(max(cont_cpus) / min(cont_cpus), 2) if min(cont_cpus) > 0 else 0.0,
                "wall_menos_cpu_s": round(cont["seg"] - cont["cpu"], 2),
                "rc_tope": tope["rc"],
                "rc_contenido": cont["rc"],
                "rss_tope_mb": tope["rss_mb"],
                "rss_contenido_mb": cont["rss_mb"],
                "bytes_vistos": vistos,
            }
            pts.append(p)
            print(f"{mib:>6} {nbytes:>10} {p['t_tope_s']:>9.2f} {p['t_contenido_s']:>9.2f} "
                  f"{p['t_cpu_s']:>6.2f} {p['disp_cpu']:>5.2f}x "
                  f"{p['rss_tope_mb']:>10.1f} {p['rss_contenido_mb']:>11.1f} {vistos:>10} "
                  f"{p['t_contenido_s'] / mib:>7.2f}")

            sh(["git", "rm", "-q", "--cached", "--", ruta], repo)
            os.unlink(os.path.join(repo, ruta))

        if len(pts) < MIN_PUNTOS:
            raise Falla(6, f"curva insuficiente: {len(pts)} punto(s), hacen falta {MIN_PUNTOS}. "
                           "Con menos, la recta es degenerada y el veredicto lo firma el intercepto")
        fit = ajuste(pts)
        if fit["b"] <= 0:
            raise Falla(6, f"pendiente no positiva ({fit['b']:.4f} s/MiB): el coste no crece con el tamano "
                           "en esta muestra; no hay ley que ajustar ni veredicto que firmar")
        veredicto, lineal, ratio, motivo = rama(pts, fit)
        c2, m2 = codo(pts, fit, 2.0)
        c10, m10 = codo(pts, fit, 10.0)

        # El sello existente se lee AQUI, antes de `atribuir` y `medir_coste`: si
        # esta corrida degrada el ajuste, el rechazo no paga los ~40 s que faltan.
        previo = None
        if args.json and os.path.isfile(args.json):
            try:
                with open(args.json, encoding="utf-8") as fh:
                    previo = json.load(fh)
            except (OSError, ValueError):
                previo = None
        estado_calidad = guardia_calidad(args.json, previo, fit["r2"], veredicto, emisor_blob,
                                         hook_blob, args.force_sello, pts, fit, args.force_ventana,
                                         max(1, args.reps), args.declaro_reps, args.force_curva,
                                         args.force_regimen)
        # El par de dimensiones viaja con cada punto: `residual_intra` es la
        # precision dentro del punto (`disp_cont`, no se renombra) y
        # `residual_entre` es la pertenencia a la curva.
        for i, p in enumerate(pts):
            p["residual_intra"] = p["disp_cont"]
            p["residual_entre"] = (None if estado_calidad["residual_entre"] is None
                                   else round(estado_calidad["residual_entre"][i], 2))

        mayor = max(pts, key=lambda p: p["mib"])
        ruta_mayor = f"big_{str(mayor['mib']).replace('.', 'p')}mib.txt"
        with open(os.path.join(repo, ruta_mayor), "wb") as fh:
            fh.write(texto_de(mayor["bytes"]))
        sh(["git", "add", "-f", "--", ruta_mayor], repo)
        at = atribuir(repo, hook_abierto, ruta_mayor, work)
        pases = (mayor["t_contenido_s"] / at["t_una_pasada_s"]) if at["t_una_pasada_s"] > 0 else 0.0
        sh(["git", "rm", "-q", "--cached", "--", ruta_mayor], repo)
        os.unlink(os.path.join(repo, ruta_mayor))

        coste = medir_coste(repo, hook_abierto, work)
        dispersion = {
            "max_ratio_cont": round(max(p["disp_cont"] for p in pts), 2),
            # Mismo objeto (dispersion en la corrida), otra metrica: el par
            # wall/cpu es lo que decide si el CPU es el objeto correcto.
            "max_ratio_cpu": round(max(p["disp_cpu"] for p in pts), 2),
            "reps": max(1, args.reps),
            # La ventana no se midio si la corrida no traia muestra: el sello lo
            # dice en vez de heredar el 1.00x de una sola repeticion.
            "ventana_vacia": estado_calidad["ventana_vacia"],
            "reps_minimo_ventana": REPS_MIN_VENTANA,
            # La curva, en la misma escala que la declaro el guardian: si una de
            # las dos dimensiones viaja sin la otra, el sello dice «preciso» de
            # una corrida que no pertenece a ninguna recta.
            "curva_rota": estado_calidad["curva_rota"],
            "residuo_k": RESIDUO_K,
            "max_residual_entre": (None if not estado_calidad["residual_entre"]
                                   else round(max(estado_calidad["residual_entre"]), 2)),
            "mediana_se_s": (None if estado_calidad["mediana_se"] is None
                             else round(estado_calidad["mediana_se"], 4)),
        }
        # Dispersion ENTRE corridas: si el destino ya tiene un JSON, se compara
        # contra el. Es el unico modo de que la inestabilidad del veredicto quede
        # escrita por el instrumento y no por la mano de quien la recuerda.
        # (`previo` se cargo arriba, antes del guardia de calidad.)
        entre = {}
        if isinstance(previo, dict) and isinstance(previo.get("puntos"), list):
            mapa = {round(q.get("mib", -1), 3): q for q in previo["puntos"]}
            for p in pts:
                q = mapa.get(round(p["mib"], 3))
                if q and q.get("t_contenido_s"):
                    entre[str(p["mib"])] = {
                        "t_cont_previo_s": q["t_contenido_s"],
                        "t_cont_ahora_s": p["t_contenido_s"],
                        "ratio": round(p["t_contenido_s"] / q["t_contenido_s"], 2),
                    }
        if entre:
            dispersion["entre_corridas"] = entre

        print()
        print(f"AJUSTE     t = {fit['a']:.3f} s + {fit['b']:.3f} s/MiB  (minimos cuadrados sobre los {len(pts)} puntos)")
        print(f"LINEALIDAD R^2 = {fit['r2']:.4f}  -> {'LINEAL' if lineal else 'NO LINEAL'}"
              f"   ·   pendiente en la cola {fit['s_por_mib_cola']:.2f} s/MiB"
              f"   ·   s/MiB aparente max/min {ratio:.2f} (el intercepto lo infla)")
        for p in pts:
            pred = fit["a"] + fit["b"] * p["mib"]
            print(f"  {p['mib']:>5.1f} MiB  medido {p['t_contenido_s']:>6.2f} s   "
                  f"recta {pred:>6.2f} s   residuo {p['t_contenido_s'] - pred:>+6.2f} s   "
                  f"RSS {p['rss_contenido_mb']:>6.1f} MB")
        print(f"CODO 2 s   {c2} MiB ({m2})   ·   CODO 10 s   {c10} MiB ({m10})")
        print(f"ATRIBUCION en {mayor['mib']:.1f} MiB: extraccion del diff {at['t_diff_s']:.2f} s · "
              f"UNA pasada de busca_patron {at['t_una_pasada_s']:.2f} s · "
              f"el hook completo equivale a {pases:.1f} pasadas")
        print(f"PASES CONTENIDO {coste['pases_contenido']} sobre el texto "
              f"({coste['greps_totales']} invocaciones -qiE; "
              f"{coste['bytes_escaneados']} B escaneados / {coste['bytes_indexados']} B "
              f"indexados = {coste['ratio_pases']}x). CONTADO, no cronometrado: la cantidad "
              f"es discreta y no dispersa")
        print(f"             el proxy de tiempo ({pases:.1f}) SUBCUENTA (su control paga una "
              f"lectura de disco que el hook no paga por patron) y DISPERSA (-78.9 / -61.2 / "
              f"+1.3 % en tres corridas del mismo sello): RETIRADO del JSON, no declarado")
        print(f"DISPERSION en la corrida: peor max/min por punto {dispersion['max_ratio_cont']:.2f}x "
              f"con {dispersion['reps']} rep(s) — una banda de +-50 % sobre segundos seria mas "
              f"estrecha que el ruido")
        if dispersion["ventana_vacia"]:
            print(f"             VENTANA_VACUA: con {dispersion['reps']} rep(s) el 1.00x es "
                  f"ausencia de muestra, no dispersion medida; este sello NO certifica la "
                  f"ventana de {VENTANA_DISP_CONT:.2f}x (declarado)")
        mr = dispersion["max_residual_entre"]
        if mr is None:
            print(f"CURVA      residuo no calculable sin error por punto; monotonia "
                  f"{'rota' if dispersion['curva_rota'] else 'ok'} (K {RESIDUO_K:.2f})")
        else:
            print(f"CURVA      peor residual_entre {mr:.2f} sobre K {RESIDUO_K:.2f} "
                  f"({mr / RESIDUO_K:.2f}x del umbral); monotonia "
                  f"{'rota' if any(a['t_contenido_s'] > b['t_contenido_s'] for a, b in zip(pts, pts[1:])) else 'ok'}"
                  f"{' · CURVA_ROTA declarada' if dispersion['curva_rota'] else ''}")
        if entre:
            peor = max(entre.items(), key=lambda kv: kv[1]["ratio"])
            print(f"DISPERSION entre corridas: peor {peor[1]['ratio']:.2f}x en {peor[0]} MiB "
                  f"({peor[1]['t_cont_previo_s']} s -> {peor[1]['t_cont_ahora_s']} s). El veredicto "
                  f"depende de un UMBRAL que esta dispersion cruza: PRUDENCIA y LINEAL_CARO no son "
                  f"distinguibles aqui, y ninguno de los dos cambia lo que hay que hacer")
        for nombre, nb in ANCLAS_BYTES:
            t = fit["a"] + fit["b"] * (nb / (MIB * 1.0))
            print(f"EXTRAPOLADO {nombre}: {nb} B ({nb / (MIB * 1.0):.2f} MiB) -> {t:.1f} s por archivo")
        print()
        print(f"VEREDICTO  {veredicto}")
        print(f"           {motivo}")
        print(f"           {mayor['mib']:.1f} MiB escaneado en {mayor['t_contenido_s']:.2f} s con RSS "
              f"{mayor['rss_contenido_mb']:.0f} MB; el mismo archivo por la rama de tope: "
              f"{mayor['t_tope_s']:.2f} s (no escanea)")

        if args.json:
            rss = None
            por_mib = {p["mib"]: p["rss_contenido_mb"] for p in pts}
            if TAMANOS_RSS[0] in por_mib and TAMANOS_RSS[1] in por_mib:
                bajo, alto = TAMANOS_RSS
                rss = {"mib_1": por_mib[bajo], "mib_12": por_mib[alto],
                       "mb_por_mib": round((por_mib[alto] - por_mib[bajo]) / (alto - bajo), 2)}
            with open(args.json, "w", encoding="utf-8") as fh:
                json.dump({
                    "huella": "HUELLA-BARRIDO-LIMITE-BYTES-20261021",
                    "hook_blob": hook_blob,
                    "emisor_blob": emisor_blob,
                    "rss": rss,
                    "delta_linea": linea_delta + 1,
                    "puntos": pts,
                    "ajuste": fit,
                    "lineal": lineal,
                    "ratio_s_por_mib": ratio,
                    "codo_2s": {"mib": c2, "base": m2},
                    "codo_10s": {"mib": c10, "base": m10},
                    "atribucion": at,
                    "coste": coste,
                    "dispersion": dispersion,
                    # El regimen viaja como dimension propia: `rc_por_punto` dice
                    # de que rama es cada punto y `cruzados` donde el eje cambia
                    # de funcion. Sin esto el sello declara «curva rota» sin poder
                    # decir si el objeto cambio de rama o la maquina se cruzo.
                    "regimen": {
                        "rc_por_punto": estado_calidad["rc_por_punto"],
                        "cruzados": estado_calidad["regimenes_cruzados"],
                        "constante_contenido": not estado_calidad["regimen_cruzado"],
                        "curva_juzgada": estado_calidad["curva_juzgada"],
                    },
                    "_retirado": {
                        "campo": "pases_equivalentes",
                        "motivo": ("tres corridas sobre el MISMO sello dieron 2.32 / 4.27 / 11.15 "
                                   "pasadas equivalentes: delta -78.9 % / -61.2 % / +1.3 % sobre "
                                   "el conteo real. Un cociente que oscila 80 puntos porcentuales "
                                   "sobre el mismo objeto es ruido, no proyeccion; el sesgo se "
                                   "corrige, el ruido se retira"),
                        "medicion": ("coste.pases_contenido = %d — contada con guardia de grep "
                                     "en el PATH: discreta, exacta, sin dispersion"
                                     % coste["pases_contenido"]),
                        "como_se_retiro": ("HUELLA-F11-PISO-Y-PASES-RETIRADO-20261021 · el "
                                           "campo se elimino del emisor, no se reescribio el "
                                           "sello a mano: este JSON se regenera con el barrido"),
                    },
                    "veredicto": veredicto,
                    "motivo": motivo,
                    "nota": ("`coste.pases_contenido` es la MEDICION: se cuenta con un guardia "
                             "de grep en el PATH y no dispersa (11 en el hook sano, 20 con la "
                             "llamada duplicada, 2 con las tablas colapsadas). La proyeccion por "
                             "tiempo (`t_hook / t_una_pasada`) NO se certifica ni se declara "
                             "como proyeccion: se retiro por ruido — ver `_retirado`. Regla: un "
                             "numero que oscila mas que la banda que lo juzgaria no se "
                             "recalibra, se retira."),
                }, fh, ensure_ascii=False, indent=2)
            print(f"JSON       {args.json}")
        return 0
    except Falla as f:
        print(f"\nFALLA CERRADA ({f.rc}): {f.msg}")
        return f.rc
    finally:
        if args.keep:
            print(f"WORK       {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
