#!/usr/bin/env node
// -*- coding: utf-8 -*-
//
// verificar_ui.js — la pagina solo vale si ARRANCA.
//
// QUE MIDE
// --------
// `verificar_paridad.py` mide el motor: que los numeros coincidan con el
// oraculo Python. No mide la pagina. Un `<script id="motor">` perfecto dentro
// de un HTML que revienta al arrancar —un `$()` que nombra un id que no
// existe, un metodo de canvas que no llamamos, un readout que nunca se
// escribe— pasaba la paridad con RC 0 y dejaba un artefacto muerto.
//
// Este verificador ejecuta los DOS bloques `<script>` del HTML en un contexto
// unico, como el navegador, contra un DOM simulado que:
//   - devuelve `null` para todo id que el HTML no declara (y lo registra),
//   - lanza si se usa un global que el navegador no tendria,
//   - intercepta cada `textContent`/`innerHTML` escrito, por id,
//   - siembra los `value=` que el HTML declara, como haria el navegador.
//
// Y despues afirma tres cosas:
//   1. ningun id pedido falta en el HTML,
//   2. la cadena de arranque no lanza y ejercita el canvas (algo se dibujo),
//   3. el estado por defecto de la pagina reproduce el caso `nulo` del
//      fixture congelado — es decir, abrir la pagina y no tocar nada da
//      exactamente lo que el oraculo certifico.
//
// RC 0 medido · 1 defecto (nombra cual) · 4 no hay `node` · 3 falta un archivo.
//
// LIMITE DECLARADO
// ----------------
// El DOM simulado no es un navegador: mide contrato (que exista el elemento,
// que la funcion no lance, que se escriba el readout), no pixeles. Un error de
// CSS o un canvas que dibuja fuera de la vista pasan con RC 0. La revision
// visual sigue siendo humana; lo que no puede ser humano es descubrir que un
// id no existe.

'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const AQUI = __dirname;
const HTML_PATH = path.join(AQUI, 'index.html');
const FIXTURE_PATH = path.join(AQUI, 'casos.json');

function faltaArchivo(p) {
  console.error(`RC 3: falta ${path.basename(p)}`);
  process.exit(3);
}
if (!fs.existsSync(HTML_PATH)) faltaArchivo(HTML_PATH);
if (!fs.existsSync(FIXTURE_PATH)) faltaArchivo(FIXTURE_PATH);

const html = fs.readFileSync(HTML_PATH, 'utf8');
const fixture = JSON.parse(fs.readFileSync(FIXTURE_PATH, 'utf8'));

// ---------------------------------------------------------------- extraccion
// Dos bloques: el motor (id="motor") y la UI. Se ejecutan en ese orden y en el
// mismo ambito, igual que en la pagina.
const bloques = [...html.matchAll(/<script([^>]*)>([\s\S]*?)<\/script>/g)]
  .map(([, attrs, cuerpo]) => ({ motor: /id="motor"/.test(attrs), cuerpo }));
const motorSrc = bloques.filter(b => b.motor).map(b => b.cuerpo).join('');
const uiSrc = bloques.filter(b => !b.motor).map(b => b.cuerpo).join('');
if (!motorSrc) { console.error('RC 1: el HTML no tiene <script id="motor">'); process.exit(1); }
if (!uiSrc) { console.error('RC 1: el HTML no tiene script de UI'); process.exit(1); }

const idsReales = new Set([...html.matchAll(/id="([^"]+)"/g)].map(m => m[1]));
const valoresDeclarados = new Map(
  [...html.matchAll(/<input\s+id="([^"]+)"[^>]*?value="([^"]*)"/g)].map(m => [m[1], m[2]]));

// ------------------------------------------------------------------- DOM falso
const faltantes = new Set();
const canvasUsado = new Set();
const escrituras = new Map();
const listeners = new Set();

function elemento(id) {
  const el = {
    id,
    value: valoresDeclarados.has(id) ? valoresDeclarados.get(id) : '',
    textContent: '', innerHTML: '', className: '', lang: '',
    width: 800, height: 500, clientWidth: 800, clientHeight: 500,
    setAttribute() {}, getAttribute() { return null; }, removeAttribute() {},
    addEventListener(t) { listeners.add(String(t)); },
    removeEventListener() {}, appendChild() {}, remove() {}, focus() {}, blur() {},
    getBoundingClientRect() {
      return { left: 0, top: 0, width: 800, height: 500, right: 800, bottom: 500 };
    },
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    style: new Proxy({}, { get: () => '', set: () => true }),
    getContext() {
      return new Proxy({}, {
        get(_, prop) {
          if (prop === 'canvas') return el;
          if (prop === 'measureText') return () => ({ width: 10 });
          if (prop === 'createLinearGradient' || prop === 'createRadialGradient') {
            return () => ({ addColorStop() {} });
          }
          canvasUsado.add(String(prop));
          return () => {};
        },
        set() { return true; },
      });
    },
  };
  // Espia de escritura: registra que id recibio que texto.
  for (const prop of ['textContent', 'innerHTML']) {
    let v = el[prop];
    Object.defineProperty(el, prop, {
      get() { return v; },
      set(nv) {
        v = nv;
        const s = String(nv);
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
  navigator: { language: 'es-MX' },
};

// ---------------------------------------------------------------- ejecucion
const sandbox = {
  document: documentStub, window: windowStub, navigator: windowStub.navigator,
  requestAnimationFrame: windowStub.requestAnimationFrame,
  cancelAnimationFrame: windowStub.cancelAnimationFrame,
  devicePixelRatio: 2, console,
  Math, Number, JSON, Map, Set, Array, Object, String, Boolean, Error, RegExp,
  parseFloat, parseInt, isFinite, isNaN, Infinity, NaN, Intl, Date, Float64Array,
};
sandbox.globalThis = sandbox;
const contexto = vm.createContext(sandbox);

const errores = [];
for (const [nombre, src] of [['motor', motorSrc], ['ui', uiSrc]]) {
  try {
    vm.runInContext(src, contexto, { filename: `${nombre}.js` });
  } catch (e) {
    errores.push(`${nombre}: ${e.message}`);
  }
}

// La tabla `LANG` vive dentro de la IIFE de la pagina, no en el global. Se
// inyecta una sonda justo antes del cierre para poder leerla desde aqui. Si la
// inyeccion no aplica, se falla en vez de dar por bueno un cero.
let LANG = null;
const SONDA = 'globalThis.__LANG = LANG; })();';
const uiConSonda = uiSrc.replace(/\}\)\(\);\s*$/, SONDA);
if (uiConSonda === uiSrc) {
  errores.push('no se pudo inyectar la sonda de LANG: la IIFE no cierra con `})();`');
} else {
  // Contexto propio y aislado: `globalThis` debe apuntar al sandbox de la
  // sonda, no al del primer contexto, o `__LANG` se escribe en el objeto
  // equivocado y la lectura da null.
  const sandboxSonda = { ...sandbox };
  sandboxSonda.globalThis = sandboxSonda;
  const ctxSonda = vm.createContext(sandboxSonda);
  try {
    vm.runInContext(motorSrc, ctxSonda, { filename: 'motor_sonda.js' });
    vm.runInContext(uiConSonda, ctxSonda, { filename: 'ui_sonda.js' });
    LANG = sandboxSonda.__LANG || null;
    if (!LANG) errores.push('la sonda corrio pero no expuso LANG');
  } catch (e) {
    errores.push(`sonda: ${e.message}`);
  }
}

// ---------------------------------------------------------------- aserciones
const fallas = [];

if (faltantes.size) {
  fallas.push(`ids pedidos que el HTML no declara: ${[...faltantes].join(', ')}`);
}
for (const e of errores) fallas.push(`arranque: ${e}`);
if (!errores.length && canvasUsado.size === 0) {
  fallas.push('no se ejercito el canvas: la escena nunca se dibujo');
}
if (!errores.length && escrituras.size === 0) {
  fallas.push('ningun readout escrito: la cadena motor->DOM no llego al DOM');
}

// Todo `motivo` que el motor sepa emitir debe tener traduccion en los dos
// idiomas. El motor porta el oraculo y razona en espanol a proposito —su texto
// es el que compara la paridad— asi que la traduccion vive en la capa de UI y
// puede quedarse corta al añadir un estado nuevo. Esta asercion es la que lo
// impide: un motivo sin traducir se pinta en espanol dentro de la vista EN.
const motivosDelMotor = [...motorSrc.matchAll(/motivo:\s*'([^']+)'/g)]
  .map(m => m[1]).filter(Boolean);
if (!LANG) {
  if (!errores.length) fallas.push('la pagina no declara LANG: no hay tabla de traduccion que medir');
} else {
  for (const idioma of ['en', 'es']) {
    const tabla = (LANG[idioma] || {}).motivo || {};
    for (const m of motivosDelMotor) {
      if (!(m in tabla)) {
        fallas.push(`i18n: el motivo ${JSON.stringify(m)} no tiene traduccion en ${idioma}`);
      }
    }
  }
}

// El estado por defecto de la pagina debe reproducir el caso `nulo` congelado.
const casoNulo = (fixture.casos || []).find(c => c.nombre === 'nulo');
if (!casoNulo) {
  fallas.push('el fixture no tiene el caso `nulo`: no hay contra que comparar el arranque');
} else if (!errores.length) {
  const esp = casoNulo.esperado;
  const lee = id => (escrituras.get(id) || new Map()).get('textContent');

  const claseDibujada = lee('clase');
  if (claseDibujada !== esp.clase) {
    fallas.push(`arranque: la pagina abre en clase ${JSON.stringify(claseDibujada)}, ` +
                `el oraculo certifico ${JSON.stringify(esp.clase)}`);
  }
  // Los readouts numericos se comparan por valor, no por formato: la pagina
  // decide como redondea, el fixture dice cuanto vale.
  for (const [id, clave] of [['rI1', 'I1_algebra'], ['rI2', 'I2_algebra'],
                             ['rE', null], ['rB', null]]) {
    const texto = lee(id);
    if (texto === undefined) { fallas.push(`arranque: el readout ${id} quedo vacio`); continue; }
    if (clave === null) continue;
    const n = parseFloat(texto);
    if (!Number.isFinite(n) || Math.abs(n - esp[clave]) > 1e-6 * Math.max(1, Math.abs(esp[clave]))) {
      fallas.push(`arranque: ${id} muestra ${JSON.stringify(texto)}, el oraculo dice ${esp[clave]}`);
    }
  }
  const gamma = lee('rGamma');
  if (esp.gamma_infinita && gamma !== '∞') {
    fallas.push(`arranque: gamma infinito se dibuja ${JSON.stringify(gamma)}, se esperaba "∞"`);
  }
}

// Un numero que no cabe en su caja no se ve. Medido en el sitio publicado el
// 13-Nov-2026: el input de 88 px mostraba `3.3356409` y el exponente `e-9`
// caia fuera de la caja, asi que el campo nulo se leia 1e9 veces mas grande de
// lo que es. El ancho no se puede medir sin layout; lo que SI se puede exigir
// es que el valor completo se publique en algun sitio visible.
if (!errores.length) {
  for (const [ids, caja] of [[['e0', 'e1', 'e2'], 'exacto-e'],
                             [['b0', 'b1', 'b2'], 'exacto-b']]) {
    const publicado = (escrituras.get(caja) || new Map()).get('textContent') || '';
    if (!publicado) {
      fallas.push(`el vector ${ids[0][0].toUpperCase()} no publica su valor exacto: ${caja} quedo vacio`);
      continue;
    }
    for (const id of ids) {
      const el = cache.get(id);
      const v = el ? String(el.value).trim() : '';
      if (v && !publicado.includes(v)) {
        fallas.push(`el valor de ${id} (${v}) no aparece completo en ${caja}: ${JSON.stringify(publicado)}`);
      }
    }
  }
}

// ------------------------------------------------------------------ reporte
if (fallas.length) {
  for (const f of fallas) console.error(`FALLA ${f}`);
  console.error(`RC 1: ${fallas.length} defecto(s) de UI. ` +
                `${idsReales.size} ids declarados · ${escrituras.size} readouts escritos`);
  process.exit(1);
}

const clase = (escrituras.get('clase') || new Map()).get('textContent');
console.log(`UI MEDIDA · ${idsReales.size} ids declarados · ${escrituras.size} readouts escritos · ` +
            `${canvasUsado.size} metodos de canvas · arranque en ${clase} (igual al oraculo) · RC 0`);
process.exit(0);
