#!/usr/bin/env bash
# HUELLA-GUARDIAN-FRONTERA-ARCHIVO-20261021
# ============================================================================
# guardian_frontera_archivo.sh — instrumento del §6.3 de
# sim/NOTA_DE_FRONTERA_DONALDO_20261020.md.
#
# EL HUECO QUE CIERRA (textual de la nota):
#   «El `.gitignore` es el unico guardian. Si alguien añade `archivo/` con
#    `git add -f`, la frontera desaparece sin que nada avise. No hay
#    instrumento que lo detecte hoy.»
#
# LA LEY: ninguna ruta NUEVA bajo un prefijo ignorado entra al indice.
#   - "prefijo ignorado" no se declara aqui: se DERIVA de `git check-ignore`,
#     para que la ley siga al .gitignore y no a una copia suya que envejece.
#     (Un .gitignore que cambia mueve la ley; una lista duplicada, no.)
#   - "nueva" = esta en el indice y NO esta en el baseline congelado.
#   - el baseline es DEUDA DECLARADA, no permiso: solo encoge.
#
# QUE NO HACE:
#   - no lee contenido de ninguna ruta (solo compara nombres)
#   - no escribe nada: `--regenerar` imprime a stdout, no toca el archivo
#   - no borra ni mueve: `git rm --cached` es una tupla del dueño, no de esto
#
# Uso:
#   tools/guardian_frontera_archivo.sh                  mide el indice
#   tools/guardian_frontera_archivo.sh -q               solo RC
#   tools/guardian_frontera_archivo.sh --regenerar      imprime baseline nuevo
#   tools/guardian_frontera_archivo.sh --baseline RUTA  baseline alterno
#   tools/guardian_frontera_archivo.sh --prefijo X/     prefijo extra a vigilar
#
# RC (fail-closed):
#   0  FRONTERA INTACTA   — indice == baseline sobre los prefijos vigilados
#   1  FRONTERA ROTA      — hay ruta(s) en el indice que el baseline no declara
#   3  BASELINE ILEGIBLE  — no existe o no se puede leer
#   4  BASELINE OBSOLETO  — declara rutas que ya no estan: deja de medir,
#                            y una re-entrada futura pasaria como "ya estaba"
#   20 uso incorrecto
#   21 no hay arbol git
# ============================================================================
set -euo pipefail

QUIET=0
REGEN=0
BASELINE=""
PREFIJOS=("archivo/")

while [ $# -gt 0 ]; do
  case "$1" in
    -q|--quiet) QUIET=1; shift ;;
    --regenerar) REGEN=1; shift ;;
    --baseline)
      [ $# -ge 2 ] || { printf 'uso: %s --baseline RUTA\n' "$0" >&2; exit 20; }
      BASELINE="$2"; shift 2 ;;
    --prefijo)
      [ $# -ge 2 ] || { printf 'uso: %s --prefijo PREFIJO/\n' "$0" >&2; exit 20; }
      PREFIJOS+=("$2"); shift 2 ;;
    -h|--help) sed -n '2,40p' "$0"; exit 0 ;;
    *) printf 'uso: %s [-q] [--regenerar] [--baseline RUTA] [--prefijo P/]\n' "$0" >&2; exit 20 ;;
  esac
done

RAIZ=$(git rev-parse --show-toplevel 2>/dev/null) || {
  printf 'guardian: no hay arbol git que medir\n' >&2; exit 21; }

[ -n "$BASELINE" ] || BASELINE="$RAIZ/tools/frontera_archivo_baseline.txt"

# --- el indice, filtrado por los prefijos que el .gitignore realmente ignora ---
IND=$(mktemp) || exit 20
BASE=$(mktemp) || { rm -f "$IND"; exit 20; }
trap 'rm -f "$IND" "$BASE"' EXIT

: > "$IND"
for p in "${PREFIJOS[@]}"; do
  # solo se vigila un prefijo si git lo considera ignorado; si no, se declara
  if git -C "$RAIZ" check-ignore -q --no-index "$p""x" 2>/dev/null; then
    git -C "$RAIZ" ls-files -- "$p" >> "$IND"
  else
    [ "$QUIET" -eq 1 ] || printf 'PREFIJO_NO_IGNORADO %s (no se vigila: el .gitignore no lo cubre)\n' "$p"
  fi
done
sort -u -o "$IND" "$IND"

if [ "$REGEN" -eq 1 ]; then
  printf '# HUELLA-FRONTERA-ARCHIVO-BASELINE-20261021\n'
  printf '# Regenerado por tools/guardian_frontera_archivo.sh --regenerar\n'
  printf '# Cada fila es deuda declarada (ya estaba en el indice), no permiso.\n'
  cat "$IND"
  exit 0
fi

# --- contraste con la deuda declarada ---
if [ ! -r "$BASELINE" ]; then
  printf 'BASELINE_ILEGIBLE ruta=%s\n' "$BASELINE" >&2
  exit 3
fi
grep -v -E '^[[:space:]]*(#|$)' "$BASELINE" | sed 's/[[:space:]]*$//' | sort -u > "$BASE" || true

NUEVAS=$(comm -23 "$IND" "$BASE" || true)
FALTAN=$(comm -13 "$IND" "$BASE" || true)

N_IDX=$(wc -l < "$IND" | tr -d ' ')
N_BASE=$(wc -l < "$BASE" | tr -d ' ')

RC=0
if [ -n "$NUEVAS" ]; then
  RC=1
  printf 'FRONTERA_ROTA — %s ruta(s) en el indice que el baseline no declara:\n' "$(printf '%s\n' "$NUEVAS" | wc -l | tr -d ' ')"
  printf '%s\n' "$NUEVAS" | sed 's/^/  NUEVA  /'
  printf 'Accion del dueño (no de este guardian): git rm --cached <ruta>  y sacarla del stage.\n'
  printf 'Si la ruta DEBE quedarse, se declara en la nota de frontera — no se añade al baseline.\n'
fi

if [ -n "$FALTAN" ]; then
  [ "$RC" -eq 0 ] && RC=4
  printf 'BASELINE_OBSOLETO — declara ruta(s) que ya no estan en el indice:\n'
  printf '%s\n' "$FALTAN" | sed 's/^/  FALTA  /'
  printf 'Mientras sigan ahi, una re-entrada por `git add -f` pasaria como "ya estaba".\n'
  printf 'Regenerar: tools/guardian_frontera_archivo.sh --regenerar > <baseline>\n'
fi

if [ "$RC" -eq 0 ] && [ "$QUIET" -eq 0 ]; then
  printf 'FRONTERA_OK indice=%s baseline=%s prefijos=%s\n' \
    "$N_IDX" "$N_BASE" "$(IFS=,; printf '%s' "${PREFIJOS[*]}")"
fi
exit "$RC"
