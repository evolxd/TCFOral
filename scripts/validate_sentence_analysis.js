const fs = require("fs");
const vm = require("vm");

const html = fs.readFileSync("index.html", "utf8");
const match = html.match(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/i);
if (!match) throw new Error("Inline script not found.");

function makeElement(selector = "") {
  return {
    selector,
    value: selector === "#levelSelect" ? "b2" : selector === "#provider" ? "browser" : "",
    checked: false,
    hidden: true,
    disabled: false,
    innerHTML: "",
    textContent: "",
    className: "",
    style: {},
    dataset: {},
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    addEventListener() {},
    removeEventListener() {},
    appendChild() {},
    remove() {},
    click() {},
    focus() {},
    play() { return Promise.resolve(); },
    pause() {},
    load() {},
    querySelector() { return makeElement("nested"); },
    querySelectorAll() { return []; },
    closest() { return null; },
    setAttribute() {},
    getAttribute() { return null; },
    scrollIntoView() {},
    getBoundingClientRect() { return { top: 0, left: 0, width: 100, height: 40 }; }
  };
}

const elements = new Map();
const getElement = selector => {
  if (!elements.has(selector)) elements.set(selector, makeElement(selector));
  return elements.get(selector);
};
const storage = new Map();
const documentStub = {
  querySelector: getElement,
  querySelectorAll() { return []; },
  createElement() { return makeElement("created"); },
  addEventListener() {},
  body: makeElement("body")
};
const windowStub = {
  scrollY: 0,
  innerHeight: 900,
  addEventListener() {},
  scrollTo() {},
  setTimeout,
  clearTimeout,
  requestAnimationFrame: callback => callback()
};
const context = vm.createContext({
  console,
  document: documentStub,
  window: windowStub,
  localStorage: {
    getItem: key => storage.has(key) ? storage.get(key) : null,
    setItem: (key, value) => storage.set(key, String(value)),
    removeItem: key => storage.delete(key)
  },
  navigator: {},
  location: { protocol: "file:", hostname: "", href: "file:///index.html" },
  history: { replaceState() {} },
  URL,
  Blob,
  TextEncoder,
  TextDecoder,
  AbortController,
  fetch: async () => ({ ok: false, text: async () => "disabled in validation" }),
  speechSynthesis: { cancel() {}, speak() {} },
  SpeechSynthesisUtterance: function SpeechSynthesisUtterance(text) { this.text = text; },
  alert() {},
  confirm() { return false; },
  requestAnimationFrame: callback => callback(),
  cancelAnimationFrame() {},
  setTimeout,
  clearTimeout,
  setInterval,
  clearInterval
});
for (const id of [...html.matchAll(/\bid="([^"]+)"/g)].map(match => match[1])) {
  context[id] = getElement(`#${id}`);
}
context.globalThis = context;

vm.runInContext(match[1], context, { filename: "index.html" });

function count(source, token) {
  return source.split(token).length - 1;
}

function renderLevel(level) {
  vm.runInContext(`activeLevel = ${JSON.stringify(level)}; clearCardLevels(); renderCards();`, context);
  return getElement("#cards").innerHTML;
}

const b2 = renderLevel("b2");
const c1 = renderLevel("c1");
const a2 = renderLevel("a2");
const b2Count = count(b2, "data-sentence-analysis-toggle=");
const c1Count = count(c1, "data-sentence-analysis-toggle=");
const a2Count = count(a2, "data-sentence-analysis-toggle=");

if (b2Count !== 176) throw new Error(`Expected 176 B2 analysis toggles, found ${b2Count}.`);
if (c1Count !== 138) throw new Error(`Expected 138 C1 analysis toggles, found ${c1Count}.`);
if (a2Count !== 0) throw new Error(`A2 should not have analysis toggles, found ${a2Count}.`);

for (const label of ["句子骨架", "好句型 · 为什么好", "语法注意", "替换公式", "常见错误", "考场作用"]) {
  if (!b2.includes(label) || !c1.includes(label)) throw new Error(`Missing analysis section: ${label}`);
}
if (!b2.includes("data-sentence-analysis-panel")) throw new Error("B2 analysis panels were not rendered.");
if (!b2.includes("sentence-controls-inline")) throw new Error("Inline sentence controls were not rendered.");
if (b2.includes("本句没有新增的高风险语法点") || c1.includes("本句没有新增的高风险语法点")) {
  throw new Error("Empty analysis placeholders should be hidden, not rendered.");
}
if (vm.runInContext(`renderSentenceAnalysisBlock('测试空板块', [])`, context) !== "") {
  throw new Error("Empty analysis blocks should not render.");
}

for (const [level, rendered] of [["b2", b2], ["c1", c1]]) {
  const blocks = [...rendered.matchAll(/<div class="sentence-analysis-block[^>]*">([\s\S]*?)<\/div>\s*<\/div>/g)].map(match => match[1]);
  const withoutSentenceExample = blocks.filter(block => !block.includes("«"));
  if (withoutSentenceExample.length) throw new Error(`${level.toUpperCase()} has ${withoutSentenceExample.length} analysis blocks without a current-sentence example.`);
}

const ruleCounts = vm.runInContext(`(() => {
  const visible = buildSentenceGrammarVisibleKeys();
  const result = {};
  sentenceGrammarRules.forEach(rule => result[rule.id] = 0);
  visible.forEach(key => {
    const id = sentenceGrammarRules.map(rule => rule.id).find(id => key.endsWith(':' + id));
    if (id) result[id] += 1;
  });
  return result;
})()`, context);
for (const [id, value] of Object.entries(ruleCounts)) {
  if (value > 5) throw new Error(`Grammar rule ${id} is shown ${value} times.`);
}

const grammarSpacing = vm.runInContext(`(() => {
  const visible = [...buildSentenceGrammarVisibleKeys()];
  const positions = {};
  visible.forEach(key => {
    const [level, cardIndex, sentenceIndex, ...ruleParts] = key.split(':');
    const ruleId = ruleParts.join(':');
    const ordinal = (level === 'b2' ? 0 : templates.length) + Number(cardIndex);
    (positions[ruleId] ||= []).push({ ordinal, sentenceIndex: Number(sentenceIndex), key });
  });
  return positions;
})()`, context);

for (const [id, positions] of Object.entries(grammarSpacing)) {
  positions.sort((a, b) => a.ordinal - b.ordinal || a.sentenceIndex - b.sentenceIndex);
  for (let index = 1; index < positions.length; index += 1) {
    const gap = positions[index].ordinal - positions[index - 1].ordinal;
    if (gap < 2) throw new Error(`Grammar rule ${id} repeats without one full card between explanations.`);
  }
}

const fallbackPatternCounts = vm.runInContext(`(() => {
  const result = { b2: 0, c1: 0 };
  ['b2', 'c1'].forEach(level => templates.forEach(item => {
    splitFrench(variantFor(item, level).fr).forEach(line => {
      const notes = sentenceGoodPatterns(line, item);
      if (notes.some(note => ['提问骨架', '论证骨架', '表达骨架'].includes(note.phrase))) result[level] += 1;
    });
  }));
  return result;
})()`, context);

console.log(JSON.stringify({
  b2Count,
  c1Count,
  a2Count,
  maxGrammarRepeats: Math.max(...Object.values(ruleCounts)),
  fallbackPatternCounts
}));
