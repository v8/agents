const fs = require('fs');
const path = require('path');
const parser = require('@babel/parser');

const dataDir = process.env.ECMABOT_DATA_DIR;

let JSDOM;
if (dataDir) {
  JSDOM = require('jsdom').JSDOM;
} else {
  JSDOM =
      require(path.join(__dirname, 'ecmarkup', 'node_modules', 'jsdom')).JSDOM;
}

const specDir =
    dataDir ? path.join(dataDir, 'ecma262') : path.join(__dirname, 'ecma262');
const BIBLIO_PATH = path.join(specDir, 'biblio.json');
const SPEC_PATH = path.join(specDir, 'spec.html');
const OUTPUT_PATH = path.join(specDir, 'spec_data.json');

function loadBiblio() {
  const data = fs.readFileSync(BIBLIO_PATH, 'utf-8');
  const biblio = JSON.parse(data);
  const ops = {};
  if (biblio.entries) {
    for (const entry of biblio.entries) {
      if (entry.type === 'op' && entry.aoid) {
        ops[entry.aoid] = entry;
      }
    }
  }
  biblio.ops = ops;
  return biblio;
}

function loadBiblioForPreparse() {
  const data = fs.readFileSync(BIBLIO_PATH, 'utf-8');
  const biblio = JSON.parse(data);
  const ops = {};
  const entries = {};
  if (biblio.entries) {
    for (const entry of biblio.entries) {
      if (entry.type === 'op' && entry.aoid) {
        ops[entry.aoid] = entry;
      }
      if (entry.id) {
        entries[entry.id] = entry;
      }
    }
  }
  return {ops, entries};
}

function formatPart(index, level) {
  if (level % 3 === 0) {
    return (index + 1).toString();
  } else if (level % 3 === 1) {
    return String.fromCharCode('a'.charCodeAt(0) + index);
  } else if (level % 3 === 2) {
    return decimalToRoman(index + 1);
  }
  return index.toString();
}

function decimalToRoman(num) {
  const lookup = {'x': 10, 'ix': 9, 'v': 5, 'iv': 4, 'i': 1};
  let roman = '';
  for (const i in lookup) {
    while (num >= lookup[i]) {
      roman += i;
      num -= lookup[i];
    }
  }
  return roman;
}

function processAlgorithm(alg) {
  const text = alg.textContent;
  const lines = text.split('\n').filter(line => line.trim() !== '');

  const steps = [];
  for (const line of lines) {
    const match = line.match(/^(\s*)(\d+\.|[a-z]\.|[ivx]+\.)\s*(.*)$/i);
    if (match) {
      const indent = match[1].length;
      const label = match[2];
      const content = match[3];
      steps.push({indent, label, content, raw: line});
    }
  }

  if (steps.length === 0)
    return null;

  const levels = [];
  let currentLevel = 0;
  let lastIndent = steps[0].indent;
  levels.push(steps[0].indent);

  const processedSteps = [];
  const counts = [0];

  for (let i = 0; i < steps.length; i++) {
    const step = steps[i];
    if (step.indent > lastIndent) {
      currentLevel++;
      levels.push(step.indent);
      counts.push(0);
    } else if (step.indent < lastIndent) {
      while (currentLevel > 0 && levels[currentLevel] > step.indent) {
        currentLevel--;
        levels.pop();
        counts.pop();
      }
    }

    counts[currentLevel]++;

    const posParts = [];
    for (let j = 0; j <= currentLevel; j++) {
      posParts.push(formatPart(counts[j] - 1, j));
    }
    const pos = posParts.join('.');

    processedSteps.push(
        {position: pos, content: step.content, indent: step.indent});

    lastIndent = step.indent;
  }
  return processedSteps;
}

function searchSpec(biblio, query, type) {
  const entries = biblio.entries;
  const results = [];
  const lowerQuery = query.toLowerCase();

  for (const entry of entries) {
    let match = false;

    let biblioType = null;
    if (type === 'abstract_op')
      biblioType = 'op';
    else if (type === 'grammar')
      biblioType = 'production';
    else if (type === 'prose')
      biblioType = 'clause';

    if (biblioType && entry.type !== biblioType)
      continue;

    if (entry.title && entry.title.toLowerCase().includes(lowerQuery))
      match = true;
    if (entry.aoid && entry.aoid.toLowerCase().includes(lowerQuery))
      match = true;
    if (entry.name && entry.name.toLowerCase().includes(lowerQuery))
      match = true;
    if (entry.term && entry.term.toLowerCase().includes(lowerQuery))
      match = true;

    if (match) {
      results.push({
        id: entry.id || entry.refId,
        title: entry.title || entry.term || entry.name || entry.aoid,
        type: entry.type,
        number: entry.number
      });
    }
  }
  return results;
}

function getSectionContent(id) {
  const html = fs.readFileSync(SPEC_PATH, 'utf-8');
  const dom = new JSDOM(html);
  const document = dom.window.document;
  const element = document.getElementById(id);

  if (!element) {
    return {error: `Section with id ${id} not found`};
  }

  return {content: element.outerHTML};
}

function getSectionsContent(ids) {
  const html = fs.readFileSync(SPEC_PATH, 'utf-8');
  const dom = new JSDOM(html);
  const document = dom.window.document;

  const results = {};
  for (const id of ids) {
    const element = document.getElementById(id);
    if (!element) {
      results[id] = {error: `Section with id ${id} not found`};
    } else {
      results[id] = {content: element.outerHTML};
    }
  }
  return results;
}

function getAncestry(id) {
  const html = fs.readFileSync(SPEC_PATH, 'utf-8');
  const dom = new JSDOM(html);
  const document = dom.window.document;
  const element = document.getElementById(id);

  if (!element) {
    return {error: `Section with id ${id} not found`};
  }

  const ancestry = [];
  let current = element.parentElement;

  while (current) {
    if (current.tagName.toLowerCase() === 'emu-clause') {
      const titleEl = current.querySelector('h1');
      const title = titleEl ? titleEl.textContent.trim() : 'Untitled';
      ancestry.push({id: current.id, title: title});
    }
    current = current.parentElement;
  }

  return {ancestry: ancestry.reverse()};
}

function getOperationSignature(biblio, name) {
  const entries = biblio.entries;
  for (const entry of entries) {
    if (entry.type === 'op' && entry.aoid === name) {
      return {signature: entry.signature};
    }
  }
  return {error: `Operation ${name} not found`};
}

function getOperationAlgorithm(biblio, name) {
  const entries = biblio.entries;
  for (const entry of entries) {
    if (entry.type === 'op' && entry.aoid === name) {
      const id = entry.id || entry.refId;
      if (!id)
        return {error: `No ID found for operation ${name}`};
      return getSectionContent(id);
    }
  }
  return {error: `Operation ${name} not found`};
}

function getProcessedSteps(document, id) {
  const element = document.getElementById(id);
  if (!element)
    return null;

  const alg = element.querySelector('emu-alg');
  if (!alg)
    return null;

  const text = alg.textContent;
  const lines = text.split('\n').filter(line => line.trim() !== '');

  const steps = [];
  for (const line of lines) {
    const match = line.match(/^(\s*)(\d+\.|[a-z]\.|[ivx]+\.)\s*(.*)$/i);
    if (match) {
      const indent = match[1].length;
      const label = match[2];
      const content = match[3];
      steps.push({indent, label, content, raw: line});
    }
  }

  if (steps.length === 0)
    return null;

  const levels = [];
  let currentLevel = 0;
  let lastIndent = steps[0].indent;
  levels.push(steps[0].indent);

  const processedSteps = [];
  const counts = [0];

  for (let i = 0; i < steps.length; i++) {
    const step = steps[i];
    if (step.indent > lastIndent) {
      currentLevel++;
      levels.push(step.indent);
      counts.push(0);
    } else if (step.indent < lastIndent) {
      while (currentLevel > 0 && levels[currentLevel] > step.indent) {
        currentLevel--;
        levels.pop();
        counts.pop();
      }
    }

    counts[currentLevel]++;

    const posParts = [];
    for (let j = 0; j <= currentLevel; j++) {
      posParts.push(formatPart(counts[j] - 1, j));
    }
    const pos = posParts.join('.');

    processedSteps.push({
      position: pos,
      content: step.content,
      raw: step.raw,
      indent: step.indent
    });

    lastIndent = step.indent;
  }
  return processedSteps;
}

function findCallInStep(text, biblio) {
  if (!biblio.ops)
    return null;

  const words = text.match(/[a-zA-Z]+/g);
  if (!words)
    return null;

  for (const word of words) {
    if (biblio.ops[word]) {
      return biblio.ops[word];
    }
  }
  return null;
}

function getStep(id, position, stackStr, choice) {
  const html = fs.readFileSync(SPEC_PATH, 'utf-8');
  const dom = new JSDOM(html);
  const document = dom.window.document;

  if (!stackStr) {
    return {error: 'Stack must be provided'};
  }

  const stack = stackStr.split('|').map(frame => {
    const parts = frame.split(':');
    return {id: parts[0], pos: parts[1]};
  });

  const currentFrame = stack[0];
  const processedSteps = getProcessedSteps(document, currentFrame.id);

  if (!processedSteps) {
    return {error: `No steps found for section ${currentFrame.id}`};
  }

  const targetIndex =
      processedSteps.findIndex(s => s.position === currentFrame.pos);
  if (targetIndex === -1) {
    return {
      error:
          `Step at position ${currentFrame.pos} in ${currentFrame.id} not found`
    };
  }

  const currentStep = processedSteps[targetIndex];
  const isIf = currentStep.content.startsWith('If ') ||
      currentStep.content.includes('If ') &&
          currentStep.content.includes('then');

  if (isIf && !choice) {
    const thenBranchIndex = targetIndex + 1;
    const thenBranch = processedSteps[thenBranchIndex];

    let elseBranch = null;
    let nextStepSameLevel = null;

    for (let i = targetIndex + 1; i < processedSteps.length; i++) {
      const s = processedSteps[i];
      if (s.indent === currentStep.indent) {
        if (s.content.startsWith('Else')) {
          elseBranch = s;
        } else {
          nextStepSameLevel = s;
          break;
        }
      } else if (s.indent < currentStep.indent) {
        break;
      }
    }

    return {
      step: currentStep.content,
      position: stack.map(f => `${f.id}:${f.pos}`).join('|'),
      requiresChoice: true,
      choices: {
        'true': thenBranch ? thenBranch.position : null,
        'false': elseBranch ?
            elseBranch.position :
            (nextStepSameLevel ? nextStepSameLevel.position : null)
      }
    };
  }

  let nextPos = null;
  if (choice === 'true') {
    nextPos = targetIndex + 1 < processedSteps.length ?
        processedSteps[targetIndex + 1].position :
        null;
  } else if (choice === 'false') {
    for (let i = targetIndex + 1; i < processedSteps.length; i++) {
      const s = processedSteps[i];
      if (s.indent === currentStep.indent) {
        nextPos = s.position;
        break;
      } else if (s.indent < currentStep.indent) {
        nextPos = s.position;
        break;
      }
    }
  } else {
    const call = findCallInStep(currentStep.content, loadBiblio());
    if (call && call.refId) {
      const newFrame = {id: call.refId, pos: '1'};
      const newStack = [newFrame, ...stack];
      const newStackStr = newStack.map(f => `${f.id}:${f.pos}`).join('|');

      const calledSteps = getProcessedSteps(document, call.refId);
      if (calledSteps) {
        return {
          step: `[Stepping into ${call.aoid}] ` + calledSteps[0].content,
          position: newStackStr,
          nextPosition: null
        };
      }
    }

    const nextStep = targetIndex + 1 < processedSteps.length ?
        processedSteps[targetIndex + 1] :
        null;
    return {
      step: currentStep.content,
      position: stack.map(f => `${f.id}:${f.pos}`).join('|'),
      nextPosition: nextStep ? nextStep.position : null
    };
  }

  if (nextPos) {
    currentFrame.pos = nextPos;
    const newStackStr = stack.map(f => `${f.id}:${f.pos}`).join('|');
    const nextStep = processedSteps.find(s => s.position === nextPos);
    return {
      step: nextStep ? nextStep.content : 'End of block',
      position: newStackStr,
      nextPosition: null
    };
  }

  return {error: 'Could not determine next step'};
}

function cleanAST(node) {
  if (!node || typeof node !== 'object')
    return node;
  if (Array.isArray(node))
    return node.map(cleanAST);

  const cleaned = {};
  for (const key in node) {
    if (key === 'loc' || key === 'start' || key === 'end' || key === 'extra' ||
        key === 'comments')
      continue;
    cleaned[key] = cleanAST(node[key]);
  }
  return cleaned;
}

const input = fs.readFileSync(0, 'utf-8');
try {
  const request = JSON.parse(input);
  const action = request.action;

  if (action === 'parse') {
    const code = request.code;
    let ast;
    const plugins =
        ['jsx', 'typescript', 'decorators-legacy', 'deferredImportEvaluation'];
    try {
      ast = parser.parse(code, {sourceType: 'script', plugins});
    } catch (e) {
      try {
        ast = parser.parse(code, {sourceType: 'module', plugins});
      } catch (e2) {
        console.error('Failed to parse as script:', e.message);
        console.error('Failed to parse as module:', e2.message);
        process.exit(1);
      }
    }
    console.log(JSON.stringify(cleanAST(ast)));
  } else if (action === 'preparse') {
    const {ops, entries} = loadBiblioForPreparse();
    const html = fs.readFileSync(SPEC_PATH, 'utf-8');
    const dom = new JSDOM(html);
    const document = dom.window.document;

    const xrefs = document.querySelectorAll('emu-xref');
    xrefs.forEach(xref => {
      if (xref.textContent.trim() === '') {
        const href = xref.getAttribute('href');
        if (href && href.startsWith('#')) {
          const id = href.substring(1);
          const entry = entries[id];
          if (entry) {
            if (entry.type === 'clause') {
              xref.textContent = entry.number || entry.title;
            } else if (entry.type === 'table') {
              xref.textContent = `Table ${entry.number}`;
            } else if (entry.type === 'figure') {
              xref.textContent = `Figure ${entry.number}`;
            } else if (entry.title) {
              xref.textContent = entry.title;
            }
          }
        }
      }
    });

    const steps = {};
    const algs = document.querySelectorAll('emu-alg');

    algs.forEach(alg => {
      let parent = alg.parentElement;
      while (parent && !parent.id) {
        parent = parent.parentElement;
      }

      if (parent && parent.id) {
        const processed = processAlgorithm(alg);
        if (processed) {
          let key = parent.id;
          let prev = alg.previousElementSibling;
          while (prev && prev.tagName !== 'EMU-GRAMMAR') {
            prev = prev.previousElementSibling;
          }
          if (prev) {
            const grammarText = prev.textContent.trim();
            const grammarKey =
                grammarText.replace(/[^a-zA-Z0-9]/g, '_').replace(/_+/g, '_');
            key = `${parent.id}:${grammarKey}`;
          }

          if (steps[key]) {
            let i = 1;
            while (steps[`${key}_${i}`]) {
              i++;
            }
            key = `${key}_${i}`;
          }
          steps[key] = processed;
        }
      }
    });

    const output = {ops, steps};
    fs.writeFileSync(OUTPUT_PATH, JSON.stringify(output, null, 2));
    console.log(`Saved output to ${OUTPUT_PATH}`);
  } else if (action === 'searchSpec') {
    const biblio = loadBiblio();
    const results = searchSpec(biblio, request.query, request.type);
    console.log(JSON.stringify(results));
  } else if (action === 'getSectionContent') {
    const result = getSectionContent(request.id);
    console.log(JSON.stringify(result));
  } else if (action === 'getSectionsContent') {
    const result = getSectionsContent(request.ids);
    console.log(JSON.stringify(result));
  } else if (action === 'getAncestry') {
    const result = getAncestry(request.id);
    console.log(JSON.stringify(result));
  } else if (action === 'getOperationSignature') {
    const biblio = loadBiblio();
    const result = getOperationSignature(biblio, request.name);
    console.log(JSON.stringify(result));
  } else if (action === 'getOperationAlgorithm') {
    const biblio = loadBiblio();
    const result = getOperationAlgorithm(biblio, request.name);
    console.log(JSON.stringify(result));
  } else if (action === 'getStep') {
    const result =
        getStep(request.id, request.position, request.stack, request.choice);
    console.log(JSON.stringify(result));
  } else {
    console.error(`Unknown action: ${action}`);
    process.exit(1);
  }
} catch (e) {
  console.error('Error:', e.message);
  process.exit(1);
}
