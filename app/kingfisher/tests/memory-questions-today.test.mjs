import assert from "node:assert/strict";
import {createRequire} from "node:module";
import {test} from "node:test";
import {fileURLToPath} from "node:url";
import {build} from "vite";

const compiled = await build({configFile: false, logLevel: "silent", build: {write: false, minify: false,
  lib: {entry: fileURLToPath(new URL("../src/MemoryQuestions.tsx", import.meta.url)), formats: ["cjs"]},
  rollupOptions: {external: ["react", "react/jsx-runtime", "./api", "./BefundeAnsicht", "./befunde", "./Befunde.css"]}}});
const code = [compiled].flat().flatMap(result => result.output).find(item => item.type === "chunk").code;
const require = createRequire(import.meta.url);

function befund(id, overrides = {}) {
  return {id, text: id, schwere: "hinweis", art: "waise", unterart: "ruhend", sachen: [{sache: "person:demo", name: "Demo"}],
    belege: [{episode_id: `ep-${id}`, zitat: "Synthetic source quote"}], vorschlaege: [], stand: `stand-${id}`, ...overrides};
}

function ui({responses}) {
  const slots = [];
  const effects = [];
  const listeners = new Map();
  const calls = [];
  const actionCalls = [];
  let hookIndex = 0;
  let props = {active: true, onOpenAll() {}};
  const hooks = {
    useState(value) {
      const slot = hookIndex++;
      if (!(slot in slots)) slots[slot] = typeof value === "function" ? value() : value;
      return [slots[slot], next => { slots[slot] = typeof next === "function" ? next(slots[slot]) : next; }];
    },
    useRef(value) {
      const slot = hookIndex++;
      return slots[slot] ??= {current: value};
    },
    useCallback(callback) { hookIndex++; return callback; },
    useEffect(effect, dependencies) {
      const slot = hookIndex++;
      const previous = slots[slot];
      if (!previous || dependencies.some((value, index) => value !== previous[index])) {
        slots[slot] = dependencies;
        effects.push(effect);
      }
    },
  };
  const module = {exports: {}};
  function BefundZeile(rowProps) { return {type: "BefundZeileMock", props: rowProps}; }
  const previousWindow = globalThis.window;
  globalThis.window = {addEventListener: (name, callback) => listeners.set(name, callback),
    removeEventListener: name => listeners.delete(name)};
  new Function("require", "module", "exports", code)(name => {
    if (name === "react") return hooks;
    if (name === "./api") return {api: {
      lintBefunde: async status => {
        calls.push(status);
        const response = responses.shift();
        if (response instanceof Error) throw response;
        return response;
      },
      lintStatus: async (...args) => { actionCalls.push(args); return {}; },
      lintEntscheiden: async (...args) => { actionCalls.push(args); return {}; },
    }};
    if (name === "./BefundeAnsicht") return {BefundZeile};
    if (name === "./befunde") return {ergebnisSatz: () => "synthetic"};
    if (name === "./Befunde.css") return {};
    return require(name);
  }, module, module.exports);
  function render(next) {
    if (next) props = {...props, ...next};
    hookIndex = 0;
    return module.exports.MemoryQuestions(props);
  }
  function nodes(node) {
    if (!node || typeof node !== "object") return [];
    const rendered = node.type !== "BefundZeileMock" && node.props?.befund
      ? {type: "BefundZeileMock", props: node.props} : null;
    return [node, ...nodes(rendered), ...[node.props?.children].flat(Infinity).flatMap(nodes)];
  }
  async function settle() { for (let i = 0; i < 4; i++) await new Promise(resolve => setImmediate(resolve)); }
  async function mount() {
    render();
    for (const effect of effects.splice(0)) effect();
    await settle();
    return nodes(render());
  }
  function rowIds() { return nodes(render()).filter(node => node.type === "BefundZeileMock").map(node => node.props.befund.id); }
  function button(label) { return nodes(render()).find(node => node.type === "button" && String(node.props.children).includes(label)); }
  function dispose() { globalThis.window = previousWindow; }
  return {mount, render, nodes, rowIds, button, listeners, calls, actionCalls, dispose};
}

const answer = befunde => ({befunde});

test("Today filters only ruhend before prioritizing and limiting to five rows", async () => {
  const rows = [
    ...Array.from({length: 7}, (_, index) => befund(`stale-${index}`)),
    befund("conflict", {art: "widerspruch", unterart: "frist", schwere: "wichtig"}),
    befund("unmatched-name", {unterart: "ohne_akte"}),
    befund("dangling-reference", {unterart: "verwaister_bezug"}),
    befund("unknown-waise", {unterart: "future-subtype"}),
    befund("other-live", {art: "querverweis", unterart: ""}),
  ];
  const view = ui({responses: [answer(rows)]});
  try {
    await view.mount();
    assert.deepEqual(view.rowIds(), ["conflict", "unmatched-name", "dangling-reference", "unknown-waise", "other-live"]);
    const visible = view.nodes(view.render()).find(node => node.type === "BefundZeileMock" && node.props.befund.id === "unmatched-name");
    assert.deepEqual(visible.props.befund, rows[8]);
    assert.equal(visible.props.befund.stand, "stand-unmatched-name");
    assert.equal(visible.props.befund.belege[0].episode_id, "ep-unmatched-name");
    visible.props.onAktion(visible.props.befund, "erledigt");
    await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual(view.actionCalls, [["unmatched-name", "erledigt", "stand-unmatched-name"]]);
    assert.equal(view.calls.length, 1);
    assert.equal(view.calls[0], "offen");
  } finally { view.dispose(); }
});

test("focus refresh and post-error retry apply the same Today filtering", async () => {
  const first = [befund("first-stale"), befund("first-live", {art: "querverweis", unterart: ""})];
  const refreshed = [befund("focus-stale"), befund("focus-live", {art: "querverweis", unterart: ""})];
  const retried = [befund("retry-stale"), befund("retry-live", {art: "widerspruch", schwere: "wichtig", unterart: "frist"})];
  const view = ui({responses: [answer(first), answer(refreshed)]});
  try {
    await view.mount();
    assert.deepEqual(view.rowIds(), ["first-live"]);
    view.listeners.get("focus")();
    await new Promise(resolve => setImmediate(resolve));
    await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual(view.rowIds(), ["focus-live"]);
    assert.equal(view.calls.length, 2);
  } finally { view.dispose(); }

  const failed = ui({responses: [new Error("offline"), answer(retried)]});
  try {
    await failed.mount();
    assert.ok(failed.nodes(failed.render()).some(node => node.props?.role === "alert"));
    const retry = failed.button("Erneut laden");
    assert.ok(retry);
    await retry.props.onClick();
    await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual(failed.rowIds(), ["retry-live"]);
    assert.deepEqual(failed.calls, ["offen", "offen"]);
  } finally { failed.dispose(); }
});

test("full Review continues to render the complete lint list", async () => {
  const source = await import("node:fs/promises");
  const page = await source.readFile(new URL("../src/ReviewPage.tsx", import.meta.url), "utf8");
  const list = await source.readFile(new URL("../src/BefundeAnsicht.tsx", import.meta.url), "utf8");
  assert.match(page, /<WasAufgefallenIst active \/>/);
  assert.match(list, /setBefunde\(daten\.befunde\)/);
});
