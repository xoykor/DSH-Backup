import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

function loadContinueButton() {
  let component;
  const context = {
    window: {
      __ModuleLoader__: {
        load({ factory }) {
          const module = factory((id) => {
            if (id === 'react/jsx-runtime') return {
              jsx: (type, props) => ({ type, props }),
            };
            if (id === 'react') return {};
            throw new Error(`unexpected dependency: ${id}`);
          });
          context.plugin = module;
        },
      },
    },
  };
  vm.runInNewContext(readFileSync(new URL('../lib/client.js', import.meta.url), 'utf8'), context);
  context.plugin.apply({
    effect(setup) {
      setup();
    },
    locale: {
      register() {},
    },
    slots: {
      inject(name, setup) {
        assert.equal(name, 'conversation.input.right');
        setup();
      },
      register(options, candidate) {
        assert.equal(options.id, 'continue-button');
        component = candidate;
        return () => {};
      },
    },
  });
  assert.equal(typeof component, 'function');
  return component;
}

const input = (draft = '', running = false) => ({
  useInput: (select) => select({ draft, attachmentIds: [], phase: 'plain' }),
  useSession: (select) => select({ running }),
  inputActions: {
    setDraft() {},
    submit() {},
  },
  t: (key) => key,
});

test('renders an enabled Continue button for an empty idle composer', () => {
  const ContinueButton = loadContinueButton();
  let sentDraft;
  let submitted = 0;
  const props = input();
  props.inputActions.setDraft = (draft) => {
    sentDraft = draft;
  };
  props.inputActions.submit = () => {
    submitted += 1;
  };

  const tree = ContinueButton(props);
  const button = tree.props.children;

  assert.equal(button.props.disabled, false);
  button.props.onClick();
  assert.equal(sentDraft, 'continue');
  assert.equal(submitted, 1);
});

test('does not replace an existing draft or submit while busy', () => {
  const ContinueButton = loadContinueButton();
  for (const props of [input('keep this'), input('', true)]) {
    let changed = false;
    let submitted = false;
    props.inputActions.setDraft = () => {
      changed = true;
    };
    props.inputActions.submit = () => {
      submitted = true;
    };

    const button = ContinueButton(props).props.children;
    assert.equal(button.props.disabled, true);
    button.props.onClick();
    assert.equal(changed, false);
    assert.equal(submitted, false);
  }
});
