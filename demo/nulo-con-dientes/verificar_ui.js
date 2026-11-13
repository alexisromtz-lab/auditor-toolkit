// Ejecuta la pagina de verdad: los dos bloques de <script> contra un DOM
// simulado. La paridad numerica del motor no dice nada sobre si la pagina
// arranca, pinta o traduce; esto si.
//
// Cada aserto esta pensado para morder. Un aserto que no puede fallar es
// decoracion: al final hay una lista de mutaciones y lo que cada una dispara.
//
// RC 0 pagina viva · RC 1 defecto de UI · RC 2 falta fixture · RC 3 falta HTML

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const AQUI = __dirname;
const HTML_PATH = path.join(AQUI, 'index.html');
const FIXTURE_PATH = path.join(AQUI, 'casos.json');

if (!fs.existsSync(HTML_PATH)) { console.error('RC 3: falta index.html'); process.exit(3); }
if (!fs.existsSync(FIXTURE_PATH)) { console.error('RC 2: falta casos.json'); process.exit(2); }

const html = fs.readFileSync(HTML_PATH, 'utf8');
const fixture = JSON.parse(fs.readFileSync(FIXTURE_PATH, 'utf8'));

// --------------------------------------------------------------- extraccion
const bloques = [...html.matchAll(/<script([^>]*)>([\s\S]*?)<\/script>/g)]
  .map(([, attrs, cuerpo]) => ({ motor: /id="motor"/.test(attrs), cuerpo }));
const motorSrc = bloques.filter(b => b.motor).map(b => b.cuerpo).join('');
const uiSrc = bloques.filter(b => !b.motor).map(b => b.cuerpo).join('');
if (!motorSrc) { console.error('RC 1: el HTML no tiene <script id="motor">'); process.exit(1); }
if (!uiSrc) { console.error('RC 1: el HTML no tiene script de UI'); process.exit(1); }

const idsReales = new Set([...html.matchAll(/id="([^"]+)"/g)].map(m => m[1]));
// Los `<input>` declaran `type` antes que `id`, asi que hay que leer los dos
// atributos por separado: exigirlos en un orden concreto deja el mapa vacio y
// la pagina arranca con todos los sliders en cadena vacia.
const valoresDeclarados = new Map();
for (const tag of html.matchAll(/<input\b[^>]*>/g)) {
  const id = (tag[0].match(/\bid="([^"]+)"/) || [])[1];
  const val = (tag[0].match(/\bvalue="([^"]*)"/) || [])[1];
  if (id) valoresDeclarados.set(id, val === undefined ? '' : val);
}

// ----------------------------------------------------------------- DOM falso
const faltantes = new Set();
const escrituras = new Map();
const pintado = new Map();

function elemento(id) {
  const el = {
    id,
    value: valoresDeclarados.has(id) ? valoresDeclarados.get(id) : '',
    textContent: '', innerHTML: '', className: '', lang: '', disabled: false,
    width: 800, height: 500, clientWidth: 800, clientHeight: 500,
    setAttribute() {}, getAttribute() { return null; }, removeAttribute() {},
    addEventListener() {}, removeEventListener() {},
    appendChild() {}, remove() {}, focus() {}, blur() {},
    getBoundingClientRect() {
      return { left: 0, top: 0, width: 800, height: 500, right: 800, bottom: 500 };
    },
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    style: new Proxy({}, { get: () => '', set: () => true }),
    getContext() {
      const ops = new Set();
      pintado.set(id, ops);
      return new Proxy({}, {
        get(_, prop) {
          if (prop === 'canvas') return el;
          if (prop === 'measureText') return () => ({ width: 10 });
          if (prop === 'createLinearGradient' || prop === 'createRadialGradient') {
            return () => ({ addColorStop() {} });
          }
          ops.add(String(prop));
          return () => {};
        },
        set() { return true; },
      });
    },
  };
  for (const prop of ['textContent', 'innerHTML']) {
    let v = el[prop];
    Object.defineProperty(el, prop, {
      get() { return v; },
      set(nv) {
        // Chrome deja la cadena vacia cuando el valor es null o undefined; si el
        // stub guardara la cadena 'undefined' escondería justo el defecto de una
        // clave de traduccion ausente (medido: dos opciones del nulo salieron
        // sin etiqueta y el stub las daba por escritas).
        v = (nv === null || nv === undefined) ? '' : nv;
        const s = String(v);
        if (s.trim() !== '') {
          if (!escrituras.has(id)) escrituras.set(id, new Map());
          escrituras.get(id).set(prop, s);
        }
      },
    });
  }
  return el;
}

const cache = new Map();
const documentStub = {
  title: '',
  getElementById(id) {
    if (!idsReales.has(id)) { faltantes.add(id); return null; }
    if (!cache.has(id)) cache.set(id, elemento(id));
    return cache.get(id);
  },
  querySelector(sel) { return documentStub.getElementById(String(sel).replace(/^#/, '')); },
  querySelectorAll() { return []; },
  createElement(tag) { return elemento(`<${tag}>`); },
  createElementNS(ns, tag) { return elemento(`<${tag}>`); },
  addEventListener() {},
  documentElement: elemento('html'),
  body: elemento('body'),
};

const windowStub = {
  devicePixelRatio: 2,
  addEventListener() {},
  matchMedia() { return { matches: false, addEventListener() {} }; },
  requestAnimationFrame() { return 1; },
  cancelAnimationFrame() {},
  location: { search: '', href: '' },
  navigator: { language: 'en-US' },
};

// ------------------------------------------------------------------ arranque
const fallos = [];
const anota = (cond, msg) => { if (!cond) fallos.push(msg); };

// Ejercitar la pagina no puede matar al verificador: si un `oninput` lanza, lo
// que hay que reportar es el aserto que le toca, no un volcado de pila. Se
// aprendio a golpes: renombrar un lienzo reventaba `histograma` y el proceso
// moria antes de imprimir un solo diagnostico.
function ejercita(id, valor) {
  const el = documentStub.getElementById(id);
  if (!el) { anota(false, `no se pudo ejercitar \`${id}\`: ese id no existe`); return false; }
  if (valor !== undefined) el.value = valor;
  try { el.oninput(); } catch (e) {
    anota(false, `\`${id}\` lanzo al responder (${valor === undefined ? 'valor actual' : valor}): ${e && e.message}`);
    return false;
  }
  return true;
}

function pulsa(id) {
  const el = documentStub.getElementById(id);
  if (!el) { anota(false, `no se pudo pulsar \`${id}\`: ese id no existe`); return false; }
  try { el.onclick(); } catch (e) {
    anota(false, `\`${id}\` lanzo al pulsar: ${e && e.message}`);
    return false;
  }
  return true;
}

const ctx = vm.createContext({
  document: documentStub, window: windowStub, navigator: windowStub.navigator,
  console, Math, Date, JSON, isFinite, isNaN, parseFloat, parseInt, String, Number,
  Array, Object, Error, DataView, ArrayBuffer, Uint8Array, Int32Array, Float64Array,
  setTimeout: () => 1, clearTimeout: () => {}, queueMicrotask: () => {},
});

let arranque = null;
try {
  vm.runInContext(motorSrc, ctx, { filename: 'motor.js' });
  vm.runInContext(uiSrc, ctx, { filename: 'ui.js' });
} catch (e) {
  arranque = e;
}
anota(!arranque, `el arranque lanzo: ${arranque && arranque.message}`);

// Lo que la pagina publico AL ARRANCAR, congelado aqui y no leido despues: los
// asertos que mueven sliders (A5, A9) reescriben `est` desde el DOM, asi que
// leer el estado de arranque al final mide el estado de las pruebas, no el de
// arranque. Se pago con una mutacion que no mordia: cambiar el bloque por
// omision a 5 pasaba RC 0 porque A5 ya lo habia devuelto a 20.
const lecturasDeArranque = new Map();
for (const [id, el] of cache) lecturasDeArranque.set(id, el.textContent);
const leeArranque = id => (lecturasDeArranque.get(id) || '(vacio)');

// A1 — todo id que la pagina pide existe en el HTML. Un `v-empp` devuelve null
// en el navegador y revienta el primer render; aqui se nombra el id.
anota(faltantes.size === 0,
  `la pagina pide ids que no existen en el HTML: ${[...faltantes].join(', ')}`);

// A2 — el motor y la UI quedan en el mismo ambito, como en la pagina real.
const api = ['verificar_nulo', 'par_ar', 'autocorrelacion', 'correlacion_cruzada',
             'remuestreo_bloques_por_serie', 'muestras_nulas', 'RC_OK', 'BANDA'];
for (const n of api) anota(typeof ctx[n] !== 'undefined', `el motor no publica \`${n}\``);

// A3 — los dos lienzos se pintan de verdad. Un canvas sin getContext dibuja
// nada y la pagina se ve vacia sin lanzar un solo error.
for (const id of ['lienzo-serie', 'lienzo-nulo']) {
  const ops = pintado.get(id);
  anota(ops && ops.size >= 3,
    `el lienzo ${id} no se dibujo (${ops ? ops.size : 0} operaciones de contexto)`);
}

// A4 — los campos de lectura quedan escritos.
for (const id of ['v-emp', 'v-media', 'v-banda', 'v-destruye', 'v-discrimina', 'v-rc',
                  'estado', 'porque', 'exacto', 'rho-out', 'n-out', 'bloque-out', 'rep-out']) {
  const w = escrituras.get(id);
  anota(w && w.size > 0, `el id ${id} nunca recibio texto: la pagina no lo pinta`);
}

// A5 — la linea exacta publica cada valor de entrada ENTERO. Se prueba con un
// valor de siete decimales: es el caso que un `toFixed` recorta en silencio, y
// el recorte de un exponente fue el defecto real de la Pieza #1.
if (!arranque) {
  ejercita('rho', '0.1234567');
  const exacto = documentStub.getElementById('exacto').textContent;
  anota(exacto.includes('0.1234567'),
    `la linea exacta no publica rho entero; dice: ${exacto}`);
  for (const [id, campo] of [['n', 'n'], ['rep', 'repeticiones'], ['bloque', 'bloque']]) {
    const v = documentStub.getElementById(id).value;
    anota(exacto.includes(`${campo} = ${v}`),
      `la linea exacta no publica ${campo} entero (${v}); dice: ${exacto}`);
  }
  ejercita('rho', '0.9');
}

// A6 — el estado de arranque de la PAGINA es un caso congelado del oraculo.
// Esto ata la vista por omision al fixture: si un slider por omision se mueve,
// la pagina sigue viva y el motor sigue dando paridad, pero ya no ensena lo que
// el fixture certifico.
function hexAf64(h) {
  const b = new ArrayBuffer(8);
  const v = new DataView(b);
  v.setUint32(0, parseInt(h.slice(0, 8), 16));
  v.setUint32(4, parseInt(h.slice(8), 16));
  return v.getFloat64(0);
}
function fmt(x) {
  if (x === null || x === undefined) return '\u2014';
  const a = Math.abs(x);
  if (a !== 0 && (a < 1e-4 || a >= 1e6)) return x.toExponential(6);
  return x.toFixed(6);
}
const CASO_ARRANQUE = 'cruz_porSerie_b20_rho0.9_n900_r200';
const congelado = fixture.casos.find(c => c.nombre === CASO_ARRANQUE);
anota(!!congelado, `el fixture no tiene el caso de arranque ${CASO_ARRANQUE}`);
if (congelado) {
  const e = congelado.esperado;
  const quiero = {
    'v-emp': fmt(hexAf64(e.empirico)),
    'v-media': fmt(hexAf64(e.media_nula)),
    'v-rc': String(e.rc),
  };
  for (const id of Object.keys(quiero)) {
    const tengo = leeArranque(id);
    anota(tengo === quiero[id],
      `el arranque no reproduce ${CASO_ARRANQUE}: ${id} dice '${tengo}', el fixture '${quiero[id]}'`);
  }
  // `discrimina` se publica como si/no, no como numero.
  const d = leeArranque('v-discrimina');
  anota(d !== '\u2014', 'el caso de arranque es medible pero `discrimina` salio sin valor');
  anota(/^(yes|no|s\u00ed|no)$/i.test(d), `\`discrimina\` no se tradujo: '${d}'`);
}

// A7 — todo estado que el motor puede emitir tiene traduccion en LOS DOS
// idiomas. Se enumera desde el motor, no desde la tabla: al reves, una
// traduccion ausente es invisible.
const emitibles = new Set([...motorSrc.matchAll(/'(NO_MEDIDO|NULO_[A-Z_]+)'/g)].map(m => m[1]));
anota(emitibles.size >= 4, `el motor declara ${emitibles.size} estados; se esperaban 4`);
for (const est of emitibles) {
  for (const lang of ['en', 'es']) {
    const tabla = ctx.T && ctx.T[lang] && ctx.T[lang].estados;
    anota(!!(tabla && tabla[est]),
      `el estado ${est} no tiene traduccion en ${lang}`);
    if (tabla && tabla[est]) {
      anota(Array.isArray(tabla[est]) && tabla[est][0] && tabla[est][0].trim() !== '',
        `la traduccion ${lang} de ${est} no tiene titulo`);
    }
  }
}

// A8 — cambiar de idioma cambia lo que se lee. Una tabla copiada deja los dos
// idiomas identicos y nadie lo nota mirando una sola version.
if (!arranque) {
  const lee = id => {
    const el = documentStub.getElementById(id);
    return el ? el.textContent : '(el id no existe)';
  };
  const tituloEn = lee('titulo');
  const estadoEn = lee('estado');
  anota(/[A-Za-z]/.test(tituloEn), 'el titulo quedo vacio en EN');
  if (pulsa('btn-lang')) {
    const tituloEs = lee('titulo');
    const estadoEs = lee('estado');
    anota(tituloEs !== tituloEn, `el titulo no cambia al pasar a ES: '${tituloEs}'`);
    anota(estadoEs !== estadoEn,
      `el veredicto no cambia de idioma: EN='${estadoEn}' ES='${estadoEs}'`);
    if (pulsa('btn-lang')) {
      anota(lee('titulo') === tituloEn, 'volver a EN no restaura el texto original');
    }
  }
}

// A9 — un bloque no numerico no cuelga la pestana. Se descubrio en vivo: el
// primer toque de slider dejaba la pagina girando para siempre, porque
// `Math.min(NaN, n)` es NaN en JS y el `while` del remuestreador nunca crecia.
// El oraculo no cuelga: en Python toda comparacion con NaN es False, asi que
// `max(1, min(nan, n))` da 1. El motor replica esa semantica; esto lo exige.
// Un bucle infinito no se puede interrumpir desde dentro del mismo hilo: el
// cuelgue lo detecta el plazo de `tests/test_demo_nulo.py`, no este bloque.
if (!arranque) {
  const datosPrueba = [1.5, -0.5, 2.25, 0.75, -1.25, 3.5, 0.25, -2.75];
  const conNaN = JSON.stringify(ctx.remuestreo_bloques(datosPrueba.slice(), new ctx.Generador(7), NaN));
  const conUno = JSON.stringify(ctx.remuestreo_bloques(datosPrueba.slice(), new ctx.Generador(7), 1));
  anota(conNaN === conUno,
    `un bloque NaN no se comporta como el oraculo (bloque=1): NaN=${conNaN} 1=${conUno}`);

  const bloqueInp = documentStub.getElementById('bloque');
  const previo = bloqueInp ? bloqueInp.value : '20';
  const reloj = Date.now();
  const respondio = ejercita('bloque', '');
  const tardo = Date.now() - reloj;
  anota(tardo < 5000, `un bloque vacio tardo ${tardo} ms: la pagina se esta colgando`);
  if (respondio) {
    const el = documentStub.getElementById('v-emp');
    const vEmp = el ? el.textContent : '(el id no existe)';
    anota(/^[-0-9.]/.test(vEmp), `tras un bloque vacio el veredicto quedo vacio: '${vEmp}'`);
  }
  ejercita('bloque', previo);
}

// A10 — toda etiqueta que el HTML declara queda con texto, en los dos idiomas.
// Se enumera desde el HTML, no desde la tabla de traduccion: la tabla tenia tres
// claves para cinco nulos, y las dos opciones huerfanas se pintaron vacias en el
// sitio publicado —el stub las daba por escritas porque `textContent = undefined`
// le dejaba la cadena 'undefined'—. Una opcion sin etiqueta no se ve rota: se ve
// como una bolita sin nombre.
if (!arranque) {
  const etiquetas = [...idsReales].filter(id => /^(nul|inv)-txt-|^preset-[ts]-/.test(id));
  anota(etiquetas.length >= 9,
    `el HTML declara ${etiquetas.length} etiquetas; se esperaban al menos 9`);
  const vacias = (mapa) => etiquetas.filter(id => String(mapa.get(id) || '').trim() === '');
  const enBlancoEn = vacias(lecturasDeArranque);
  anota(enBlancoEn.length === 0, `etiquetas sin texto en EN: ${enBlancoEn.join(', ')}`);
  if (pulsa('btn-lang')) {
    const enBlancoEs = vacias(new Map([...cache].map(([id, el]) => [id, el.textContent])));
    anota(enBlancoEs.length === 0, `etiquetas sin texto en ES: ${enBlancoEs.join(', ')}`);
    pulsa('btn-lang');
  }
}

// ------------------------------------------------------------------ informe
if (fallos.length) {
  console.error(`RC 1: ${fallos.length} defectos de UI`);
  for (const f of fallos) console.error(`  ${f}`);
  process.exit(1);
}
console.log('UI: arranca · 2 lienzos pintados · 13 campos escritos · '
  + `${emitibles.size} estados traducidos en 2 idiomas · arranque == ${CASO_ARRANQUE}`);
