const assert = require('node:assert/strict');
const test = require('node:test');
const ahp = require('../../frontend/mockups/ahp.js');

class Element {
  constructor(tagName = 'div') {
    this.tagName = tagName;
    this.children = [];
    this.dataset = {};
    this.className = '';
    this.hidden = false;
    this.disabled = false;
    this.textContent = '';
    this.classList = { toggle() {} };
  }

  append(...children) {
    this.children.push(...children);
  }

  replaceChildren(...children) {
    this.children = children;
  }

  setAttribute() {}

  addEventListener() {}
}

test('mount renders criterion comparisons with API-compatible pair keys', () => {
  const elements = new Map();
  const container = {
    querySelector(selector) {
      if (!elements.has(selector)) elements.set(selector, new Element());
      return elements.get(selector);
    },
  };
  const previousDocument = global.document;
  global.document = {
    createDocumentFragment: () => new Element('#fragment'),
    createElement: (tagName) => new Element(tagName),
    createTextNode: (text) => ({ textContent: text }),
  };

  try {
    ahp.mount(container);
  } finally {
    global.document = previousDocument;
  }

  const comparisons = elements.get('#ahp-comparisons').children[0].children;
  assert.deepEqual(comparisons.map((label) => label.children[1].dataset.pair), [
    'distance:nominalTime',
    'distance:co2Kg',
    'distance:minmax',
    'nominalTime:co2Kg',
    'nominalTime:minmax',
    'co2Kg:minmax',
  ]);
});

test('setSolutions enables the ranking only when every criterion has a finite value', () => {
  const elements = new Map();
  const container = {
    querySelector(selector) {
      if (!elements.has(selector)) elements.set(selector, new Element());
      return elements.get(selector);
    },
  };
  const previousDocument = global.document;
  global.document = {
    createDocumentFragment: () => new Element('#fragment'),
    createElement: (tagName) => new Element(tagName),
    createTextNode: (text) => ({ textContent: text }),
  };

  try {
    ahp.mount(container);
    ahp.setSolutions([{
      distance: 0,
      nominalTime: 12.5,
      co2Kg: 4,
      minmax: 0,
    }]);
    assert.equal(elements.get('#ahp-calculate').disabled, false);
    assert.match(elements.get('#ahp-status').textContent, /1 solução disponível/);

    ahp.setSolutions([{
      distance: 10,
      nominalTime: 12.5,
      co2Kg: null,
      minmax: 0,
    }]);
    assert.equal(elements.get('#ahp-calculate').disabled, true);
    assert.match(elements.get('#ahp-status').textContent, /Emissão de CO2/);

    ahp.setSolutions([{
      distance: 10,
      nominalTime: 12.5,
      co2Kg: Infinity,
      minmax: 0,
    }]);
    assert.equal(elements.get('#ahp-calculate').disabled, true);
  } finally {
    ahp.clear();
    global.document = previousDocument;
  }
});
