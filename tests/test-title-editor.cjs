// #2: typing a stream title must only re-render the title field, and every key
// press must reach the saved title.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/index.tsx'), 'utf8');

// Body of a top-level function, from its declaration to the next one.
function slice(name) {
  const start = source.indexOf(`function ${name}(`);
  assert.ok(start >= 0, `${name} not found`);
  const next = source.indexOf('\nfunction ', start + 1);
  return source.slice(start, next < 0 ? undefined : next);
}

for (const section of ['LiveSection', 'YouTubeSection']) {
  test(`${section} keeps no title draft of its own`, () => {
    const body = slice(section);
    assert.doesNotMatch(body, /titleInput/);
    assert.match(body, /<TitleEditor\b/);
  });
}

// Minimal hooks: the component is a pure function of its state slots.
function mount(onSave) {
  const slots = [];
  let renders = 0;
  let cursor = 0;
  const elements = [];
  const React = {
    Fragment: 'Fragment',
    createElement: (type, props, ...children) => {
      const el = { type, props: props || {}, children };
      elements.push(el);
      return el;
    },
  };
  const useState = initial => {
    const i = cursor++;
    if (!(i in slots)) slots[i] = initial;
    return [slots[i], v => { slots[i] = v; render(); }];
  };
  const compiled = ts.transpileModule(slice('TitleEditor'), { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.React } }).outputText;
  const context = { React, useState, t: k => k, PanelSectionRow: 'Row', TextField: 'TextField',
    ActionCard: 'ActionCard', IcSave: 'IcSave' };
  vm.createContext(context);
  vm.runInContext(compiled + '\nthis.TitleEditor = TitleEditor;', context);
  function render() {
    cursor = 0;
    elements.length = 0;
    renders++;
    context.TitleEditor({ placeholder: 'old', color: '#fff', onSave });
  }
  render();
  const find = type => elements.find(e => e.type === type);
  return { find, renders: () => renders };
}

test('every quick key press reaches the saved title', () => {
  const saved = [];
  const editor = mount(v => saved.push(v));
  let typed = '';
  for (const ch of 'Speedrun!!') {
    typed += ch;
    editor.find('TextField').props.onChange({ target: { value: typed } });
  }
  assert.equal(editor.find('TextField').props.value, 'Speedrun!!');
  assert.equal(editor.find('ActionCard').props.disabled, false);
  editor.find('ActionCard').props.onClick();
  assert.deepEqual(saved, ['Speedrun!!']);
  assert.equal(editor.find('TextField').props.value, '');
  assert.equal(editor.find('ActionCard').props.disabled, true);
});
