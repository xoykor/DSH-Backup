window.__ModuleLoader__.load({
  id: "dsh-continue-button",
  factory: (require) => {
    var module = { exports: {} };
    var exports = module.exports;
    Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
    let react_jsx_runtime = require("react/jsx-runtime");
    let react = require("react");

    const NS = "continue-button";
    const CONTINUE_TEXT = "continue";

    const en = {
      label: "Continue",
      aria: "Continue the response",
      title: "Send continue to let the model resume"
    };
    const zh = {
      label: "继续",
      aria: "继续生成回答",
      title: "发送“继续”，让模型接着输出"
    };

    const css = [
      ".dshContinueButtonWrap{order:1;display:inline-flex}",
      ".dshContinueButton{box-sizing:border-box;min-height:34px;color:var(--dsw-alias-label-secondary);cursor:pointer;background:var(--dsw-alias-interactive-bg-hover);border:0;border-radius:999px;padding:0 12px;font-size:13px;font-weight:500;line-height:20px;white-space:nowrap;transition:background-color .1s,color .1s}",
      ".dshContinueButton:hover:not(:disabled){color:var(--dsw-alias-label-primary);background:var(--dsw-alias-interactive-bg-hover-solid)}",
      ".dshContinueButton:focus-visible{outline:2px solid var(--dsw-alias-state-business-primary);outline-offset:2px}",
      ".dshContinueButton:disabled{cursor:default;opacity:.4}",
      "@media (max-width:520px){.dshContinueButton{padding:0 9px;font-size:12px}}"
    ].join("");
    const tagId = "dsh-continue-button/styles";
    if (typeof document !== "undefined" && document.querySelector("style[data-plugin-css=" + JSON.stringify(tagId) + "]") === null) {
      const tag = document.createElement("style");
      tag.dataset.plugin = "dsh-continue-button";
      tag.dataset.pluginCss = tagId;
      tag.textContent = css;
      document.head.appendChild(tag);
    }

    function ContinueButton({ useInput, inputActions, useSession, t }) {
      const input = useInput((snapshot) => snapshot);
      const running = useSession((snapshot) => snapshot.running) ?? false;
      if (input === void 0 || inputActions === void 0) return null;

      const hasDraft = input.draft.trim() !== "" || input.attachmentIds.length > 0;
      const submitting = input.phase !== "plain";
      const disabled = hasDraft || submitting || running;
      const continueResponse = () => {
        if (disabled) return;
        inputActions.setDraft(CONTINUE_TEXT);
        inputActions.submit();
      };

      return (0, react_jsx_runtime.jsx)("span", {
        className: "dshContinueButtonWrap",
        children: (0, react_jsx_runtime.jsx)("button", {
          type: "button",
          className: "dshContinueButton",
          "aria-label": t("aria"),
          title: t("title"),
          disabled,
          onMouseDown: (event) => {
            event.preventDefault();
          },
          onClick: continueResponse,
          children: t("label")
        })
      });
    }

    const inject = ["slots", "locale"];
    function apply(ctx) {
      ctx.effect(() => ctx.locale.register(NS, { en, zh }), "continue-button: dictionaries");
      ctx.slots.inject("conversation.input.right", () => ctx.slots.register({
        name: "conversation.input.right",
        id: "continue-button",
        order: 100,
        locale: NS
      }, ContinueButton));
    }

    exports.apply = apply;
    exports.inject = inject;
    return module.exports;
  }
});
