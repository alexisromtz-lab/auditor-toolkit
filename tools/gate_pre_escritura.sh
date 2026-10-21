#!/usr/bin/env bash
# gate_pre_escritura.sh — arnes de PRE-VUELO obligatorio y bloqueante (A2.1).
# Regla: sin corrida previa con RC 0 esta PROHIBIDO abrir o mutar el archivo.
# Uso: bash gate_pre_escritura.sh TARGET BLOB_PRE HUELLA [LINEAS_PRE]
#
#   TARGET      ruta ABSOLUTA del objeto destino (relativa -> RC 20)
#   BLOB_PRE    git hash-object esperado (contrato de identidad)
#   HUELLA      fragmento literal EXCLUSIVO del texto a insertar (grep -F)
#   LINEAS_PRE  (opcional) wc -l esperado
#
# Tupla de autorizacion: una orden de append/edicion que no traiga sus cuatro
# parametros se RECHAZA por defecto de contrato (no se escribe; se pide la tupla).
#
# RC (fail-closed):
#   0   PRE-VUELO OK — listo para recibir edicion
#   10  el objeto no existe               -> CREACION AUTORIZADA (objeto nuevo)
#   11  la huella YA habita en el destino  -> COLISION: la fila ya esta escrita
#       (COLISION es SOLO el 11: el 10 no choca con nada porque no hay objeto.)
#   12  blob distinto al contrato          -> DESFASE DE OBJETO (arbol en movimiento)
#   13  estado sucio en git (modificaciones no adjudicadas)
#   14  el destino no vive en un arbol git -> el gate no puede validar identidad
#       (incluye el caso de un directorio inexistente: sin arbol no hay nada
#        que firmar, ni siquiera una creacion)
#   15  lineas distintas al contrato
#   20  uso incorrecto (tupla incompleta, o TARGET no absoluto)
set -euo pipefail

TARGET="${1:-}"
BLOB_PRE="${2:-}"
HUELLA="${3:-}"
LINEAS_PRE="${4:-}"

# HUELLA-GATE-TELEMETRIA-RC-20261019
# Telemetria FUERA DE BANDA y con retroaccion nula sobre el arbol rastreado:
#   (a) no puede mover el RC      -> cada comando con || true, funcion con return 0;
#   (b) no puede abortar por set -u -> toda expansion con valor por defecto;
#   (c) no puede refrescar el indice -> todo git con --no-optional-locks;
#   (d) el hash del arbol NO es "ls-files -s" solo: eso es CIEGO a los archivos
#       no rastreados (??), que es exactamente la retroaccion que se quiere cazar.
#       Se hashea HEAD + indice + status --porcelain -uall, en flujo puro.
# Campos (9, siempre 9: el vacio se escribe '-'): hora_utc target blob_pre
#   blob_salida rc hash_arbol_ini hash_arbol_fin st_target_ini st_target_fin
#
# HUELLA-GATE-TELEMETRIA-V2-TARGET-SCOPED-20261020
# V2 acota el estado al TARGET y mide el blob EN LA SALIDA:
#   (i)  st_target_* = hash de 'status --porcelain -uall -- TARGET' (pathspec),
#        no del arbol entero. Con el hash global, 'otra mano escribe fuera del
#        TARGET' y 'el gate escribe dentro del TARGET' son la MISMA observacion:
#        el campo no discriminaba causa. Limpio = e69de29b (blob vacio).
#   (ii) blob_salida se recomputa DENTRO del trap EXIT, no se hereda de la
#        variable del paso 3: si el flujo corta antes (10/11/12/13/14/15/20)
#        BLOB_ACTUAL seguiria vacio y el campo diria '-' habiendo objeto.
#   NOTA DE FORMATO: 7 -> 9 campos. Un lector que exija exactamente 7 campos
#   (censo viejo) rechaza las filas nuevas: se declara, no se parchea el lector.
# HUELLA-GATE-NO-OPTIONAL-LOCKS-20261020
# Auditoria de (c): la cabecera prometia el flag en TODO git, pero el cuerpo lo
#   omitia en TRES sitios del flujo principal (paso 2b rev-parse, paso 3
#   hash-object, paso 4 status --porcelain). Aqui se alinean cuerpo y cabecera.
#   Invariante mecanizable (0 lineas de codigo sin el flag):
#     grep -nE '(^|[^#[:alnum:]_])git ' gate_pre_escritura.sh \
#       | grep -v -- '--no-optional-locks'   -> solo comentarios y mensajes
# Destino del log (HUELLA-GATE-TELEMETRIA-HOME-20261020): fuera de /tmp, que
#   no sobrevive al reinicio, y fuera del arbol rastreado. Regla dura: la ruta
#   jamas es relativa — un fallback relativo crearia un no rastreado DENTRO del
#   repo y el gate acabaria midiendo su propia telemetria (el instrumento que
#   se cuenta a si mismo). Si HOME no existe cae a /tmp y se declara volatil;
#   nunca al arbol de trabajo.
GATE_TELEMETRIA_LOG="${GATE_TELEMETRIA_LOG:-${HOME:-/tmp}/platino-telemetria.log}"
BLOB_ACTUAL=""
GATE_HASH_INI="sin-arbol"
ST_TARGET_INI="sin-arbol"

_gate_hash_arbol() {
  local dir="${1:-}" raiz="" h=""
  # La raiz se resuelve a TOPLEVEL: medido, 'git -C subdir status' acota la salida
  # al subdirectorio, de modo que el hash de tools/ no es el hash del repo.
  if [ -n "$dir" ]; then
    raiz="$(git --no-optional-locks -C "$dir" rev-parse --show-toplevel 2>/dev/null)" || raiz=""
  fi
  if [ -n "$raiz" ]; then
    h="$({ git --no-optional-locks -C "$raiz" rev-parse HEAD 2>/dev/null
           git --no-optional-locks -C "$raiz" ls-files -s 2>/dev/null
           git --no-optional-locks -C "$raiz" status --porcelain -uall 2>/dev/null
         } | git --no-optional-locks hash-object --stdin 2>/dev/null)" || h=""
  fi
  printf '%s' "${h:-sin-arbol}"
}

_gate_st_target() {
  local dir="${1:-}" raiz="" h=""
  if [ -n "$dir" ] && [ -n "${TARGET:-}" ]; then
    raiz="$(git --no-optional-locks -C "$dir" rev-parse --show-toplevel 2>/dev/null)" || raiz=""
  fi
  if [ -n "$raiz" ]; then
    h="$(git --no-optional-locks -C "$raiz" status --porcelain -uall -- "$TARGET" 2>/dev/null \
         | git --no-optional-locks hash-object --stdin 2>/dev/null)" || h=""
  fi
  printf '%s' "${h:-sin-arbol}"
}

_gate_blob_salida() {
  local dir="" h=""
  if [ -n "${TARGET:-}" ] && [ -f "${TARGET:-}" ]; then
    dir="$(dirname -- "$TARGET" 2>/dev/null)" || dir=""
    if [ -n "$dir" ]; then
      h="$(git --no-optional-locks -C "$dir" hash-object -- "$TARGET" 2>/dev/null)" || h=""
    fi
    printf '%s' "${h:--}"
  else
    printf '%s' "AUSENTE"
  fi
}

_gate_telemetria_exit() {
  local rc="${1:-0}" dir="" fin="sin-arbol" blob_sal="" st_fin="sin-arbol"
  if [ -n "${TARGET:-}" ]; then dir="$(dirname -- "$TARGET" 2>/dev/null)" || dir=""; fi
  fin="$(_gate_hash_arbol "$dir")"
  st_fin="$(_gate_st_target "$dir")"
  blob_sal="$(_gate_blob_salida)"
  printf '%s %s %s %s %s %s %s %s %s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${TARGET:--}" "${BLOB_PRE:--}" \
    "${blob_sal:--}" "$rc" "${GATE_HASH_INI:-sin-arbol}" "${fin:-sin-arbol}" \
    "${ST_TARGET_INI:--}" "${st_fin:-sin-arbol}" \
    >>"${GATE_TELEMETRIA_LOG:-${HOME:-/tmp}/platino-telemetria.log}" 2>/dev/null || true
  return 0
}
trap '_gate_telemetria_exit $?' EXIT

if [ -n "${TARGET:-}" ]; then
  GATE_HASH_INI="$(_gate_hash_arbol "$(dirname -- "$TARGET" 2>/dev/null)")" || GATE_HASH_INI="sin-arbol"
  ST_TARGET_INI="$(_gate_st_target "$(dirname -- "$TARGET" 2>/dev/null)")" || ST_TARGET_INI="sin-arbol"
fi

if [ -z "$TARGET" ] || [ -z "$BLOB_PRE" ] || [ -z "$HUELLA" ]; then
  echo "CONTRATO INCOMPLETO: uso = gate_pre_escritura.sh TARGET BLOB_PRE HUELLA [LINEAS_PRE]" >&2
  echo "Orden sin tupla de destino: rechazo por defecto de contrato. Cero escrituras." >&2
  exit 20
fi

# HUELLA-GATE-ORDEN-DE-TUPLA-20261021
# 0b. La HUELLA no puede ser numerica ni un fragmento minimo. La tupla del
#    dictado llega ordenada BLOB_PRE, LINEAS_PRE, HUELLA; el gate pide
#    BLOB_PRE, HUELLA, LINEAS_PRE. Con los dos ultimos intercambiados la HUELLA
#    vale "0", el grep de colision dispara SIEMPRE y el gate responde RC 11
#    ("YA ESCRIBIDO") sobre un objeto que nadie escribio: la rama pasiva miente
#    y la tarea se cierra sin escribir. Medido: 4 documentos nuevos dieron
#    RC 11 en la post-verificacion solo por el orden. Fail-closed con causa.
case "$HUELLA" in
  *[!0-9]*)
      if [ "${#HUELLA}" -lt 6 ]; then
        echo "CONTRATO INCOMPLETO: HUELLA demasiado corta ('$HUELLA', ${#HUELLA} caracteres)." >&2
        echo "La HUELLA es un fragmento literal EXCLUSIVO del texto a insertar. Cero escrituras." >&2
        exit 20
      fi ;;
  *)
      echo "CONTRATO INCOMPLETO: HUELLA numerica ('$HUELLA') = orden de tupla intercambiado." >&2
      echo "Uso: gate_pre_escritura.sh TARGET BLOB_PRE HUELLA [LINEAS_PRE] — HUELLA tercera, LINEAS_PRE al final." >&2
      exit 20 ;;
esac

# HUELLA-GATE-TARGET-ABSOLUTO-20261014
# 0. El TARGET debe ser ABSOLUTO. El gate re-basa la ruta con git -C (pasos 3 y
#    4): una ruta relativa se cuenta desde DOS bases distintas -> git fatal 128,
#    o peor, el hash de OTRO objeto que si existe bajo DIR. Fail-closed con causa.
case "$TARGET" in
  /*) : ;;
  *)  echo "CONTRATO INCOMPLETO: TARGET debe ser absoluto (recibido: '$TARGET')." >&2
      echo "El gate re-basa la ruta con git -C: relativa = base doble. Cero escrituras." >&2
      exit 20 ;;
esac

# 1. El objeto existe
# HUELLA-GATE-FIX-MENSAJE-RC10-20261020
# El texto obedece al codigo: RC 10 = el destino NO existe = creacion autorizada.
# Imprimia "COLISION" (la palabra del RC 11) sobre un objeto inexistente: el
# mensaje contradecia su propio RC y asustaba en el unico caso que es luz verde.
if [ ! -f "$TARGET" ]; then
  # HUELLA-GATE-FAIL-CLOSED-TREE-20261020
  # RC 10 AUTORIZA UNA ESCRITURA y era la UNICA rama que salia antes de la
  # guarda de repo (paso 2b): firmaba creacion sobre un arbol INEXISTENTE.
  # Medido antes del fix: TARGET=/Users/marlene/directorio_inexistente/test.py
  # -> RC 10 (fail-open). Un TARGET mal escrito recibia permiso de escritura.
  # Se sube al ancestro EXISTENTE mas cercano y se exige que git lo reconozca
  # como arbol de trabajo; si no lo es, 14 (fail-closed, cero escrituras).
  # El ancestro tambien resuelve el caso legitimo: subdirectorio nuevo DENTRO
  # del repo -> el ancestro es el repo -> RC 10 sigue siendo la luz verde.
  ANCESTRO="$(dirname -- "$TARGET")"
  while [ ! -d "$ANCESTRO" ] && [ "$ANCESTRO" != "/" ]; do
    ANCESTRO="$(dirname -- "$ANCESTRO")"
  done
  if ! git --no-optional-locks -C "$ANCESTRO" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "SIN REPO: $TARGET no cae dentro de un arbol git (ancestro existente mas cercano: $ANCESTRO). No se puede firmar la creacion. Fail-closed." >&2
    exit 14
  fi
  echo "CREACION AUTORIZADA: $TARGET no existe (objeto nuevo bajo $ANCESTRO)." >&2
  exit 10
fi

# 2. El contenido ordenado YA existe en destino (la colision de la Pestana 3)
if grep -Fq -- "$HUELLA" "$TARGET"; then
  echo "COLISION DETECTADA: la huella '$HUELLA' ya habita en $TARGET. Abortando escritura." >&2
  exit 11
fi

# 2b. GUARDA DE REPO (fail-closed): sin arbol git, las condiciones 3 y 4 no
#     pueden medir nada; git status fuera de repo devuelve 128 y salida VACIA,
#     que en el gate ingenuo se lee como "limpio" -> verde falso.
DIR="$(cd "$(dirname "$TARGET")" && pwd)"
if ! git --no-optional-locks -C "$DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "SIN REPO: $TARGET no vive en un arbol git. El gate no puede validar identidad de blob. Fail-closed." >&2
  exit 14
fi

# 3. El archivo base no fue tocado por otra mano concurrente
BLOB_ACTUAL="$(git --no-optional-locks -C "$DIR" hash-object -- "$TARGET")"
if [ "$BLOB_ACTUAL" != "$BLOB_PRE" ]; then
  echo "DESFASE DE OBJETO: esperado $BLOB_PRE, medido $BLOB_ACTUAL. Arbol en movimiento." >&2
  exit 12
fi

# 4. Estado de git limpio en ese archivo
if [ -n "$(git --no-optional-locks -C "$DIR" status --porcelain -- "$TARGET")" ]; then
  echo "ESTADO SUCIO: $TARGET tiene modificaciones no adjudicadas." >&2
  exit 13
fi

# 5. (opcional) el contrato de lineas
# HUELLA-FIX-WRAPPER-PADDING-20261018: se recortan ambos lados antes de comparar.
if [ -n "$LINEAS_PRE" ]; then
  L_ACT="$(wc -l < "$TARGET" | tr -d ' ')"
  L_PRE="$(printf '%s' "$LINEAS_PRE" | tr -d '[:space:]')"
  if [ "$L_ACT" != "$L_PRE" ]; then
    echo "DESFASE DE LINEAS: esperado $L_PRE, medido $L_ACT." >&2
    exit 15
  fi
fi

echo "PRE-VUELO OK: $TARGET listo para recibir edicion sobre $BLOB_PRE."
exit 0
