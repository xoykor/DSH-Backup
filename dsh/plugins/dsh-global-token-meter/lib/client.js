window.__ModuleLoader__.load({
	id: "dsh-global-token-meter",
	factory: (require) => {
		var module = { exports: {} };
		var exports = module.exports;
		Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
		let react_jsx_runtime = require("react/jsx-runtime");
		let react = require("react");

		const NS = "global-token-meter";
		const CHARS_PER_TOKEN = 4;
		const EMPTY_VALUE = "0.0";

		const en = {
			label: "TPS",
			unit: "tok/s",
			live: "live estimate",
			session: "session average",
			aria: "Output speed: {value} tokens per second ({mode})"
		};
		const zh = {
			label: "TPS",
			unit: "tok/s",
			live: "实时估算",
			session: "会话平均",
			aria: "输出速度：每秒 {value} 个 token（{mode}）"
		};

		const css = ".dshGlobalTokenMeter{box-sizing:border-box;min-height:28px;color:var(--dsw-alias-label-tertiary);white-space:nowrap;background:var(--dsw-alias-fill-tsp-secondary);border-radius:14px;align-items:center;gap:5px;padding:0 9px;font-size:12px;line-height:18px;font-variant-numeric:tabular-nums;display:inline-flex}.dshGlobalTokenMeter:hover{color:var(--dsw-alias-label-secondary);background:var(--dsw-alias-interactive-bg-hover)}.dshGlobalTokenMeter__dot{background:var(--dsw-alias-label-caption);border-radius:50%;flex:none;width:6px;height:6px}.dshGlobalTokenMeter[data-active=true]{color:var(--dsw-alias-label-primary)}.dshGlobalTokenMeter[data-active=true] .dshGlobalTokenMeter__dot{background:var(--dsw-alias-state-business-primary);animation:dshGlobalTokenMeterPulse 1.2s ease-in-out infinite}@keyframes dshGlobalTokenMeterPulse{0%,100%{opacity:.45;transform:scale(.8)}50%{opacity:1;transform:scale(1)}}.dshGlobalTokenMeter__label{font-weight:600;letter-spacing:.02em}.dshGlobalTokenMeter__value{color:var(--dsw-alias-label-secondary)}@media (prefers-reduced-motion:reduce){.dshGlobalTokenMeter[data-active=true] .dshGlobalTokenMeter__dot{animation:none;opacity:1}}";
		const tagId = "dsh-global-token-meter/styles";
		if (typeof document !== "undefined" && document.querySelector("style[data-plugin-css=" + JSON.stringify(tagId) + "]") === null) {
			const tag = document.createElement("style");
			tag.dataset.plugin = "dsh-global-token-meter";
			tag.dataset.pluginCss = tagId;
			tag.textContent = css;
			document.head.appendChild(tag);
		}

		function formatTokensPerSecond(value) {
			if (!Number.isFinite(value) || value <= 0) return EMPTY_VALUE;
			if (value >= 10) return String(Math.round(value));
			return value.toFixed(1).replace(/\.0$/u, "");
		}

		function estimatedPartialTokens(partial) {
			if (partial === null || partial === void 0 || !Array.isArray(partial.blocks)) return 0;
			let characters = 0;
			for (const block of partial.blocks) {
				if (block?.type === "text" || block?.type === "reasoning") {
					characters += typeof block.text === "string" ? block.text.length : 0;
					continue;
				}
				if (block?.type === "tool-call") {
					characters += typeof block.name === "string" ? block.name.length : 0;
					characters += typeof block.arguments === "string" ? block.arguments.length : 0;
				}
			}
			return characters === 0 ? 0 : Math.ceil(characters / CHARS_PER_TOKEN);
		}

		function sessionTokensPerSecond(stats) {
			if (stats === void 0 || stats === null || stats.decodeMs <= 0 || stats.decodeTokens <= 0) return 0;
			return stats.decodeTokens / (stats.decodeMs / 1e3);
		}

		/**
		 * Global header meter. The durable session projection is the authoritative
		 * value after a turn completes; while a response is streaming, the partial
		 * Chat snapshot supplies a small text-density estimate so the indicator is
		 * useful before the provider sends its final usage event.
		 */
		function GlobalTokenMeter({ useChat, useProjection, t }) {
			const partial = useChat((snapshot) => snapshot.legacy.partial);
			const stats = useProjection("sessionStats");
			const stream = react.useRef(null);
			const partialTokens = estimatedPartialTokens(partial);
			const activeKey = partial === null || partial === void 0 ? null : `${partial.turn}:${partial.step}`;

			if (activeKey === null || partialTokens === 0) {
				stream.current = null;
			} else if (stream.current?.key !== activeKey || partialTokens < stream.current.tokens) {
				stream.current = {
					key: activeKey,
					tokens: partialTokens,
					startedAt: typeof performance === "undefined" ? Date.now() : performance.now()
				};
			} else {
				stream.current.tokens = partialTokens;
			}

			const live = stream.current === null ? 0 : (() => {
				const now = typeof performance === "undefined" ? Date.now() : performance.now();
				const elapsed = Math.max(1, now - stream.current.startedAt);
				return stream.current.tokens / (elapsed / 1e3);
			})();
			const active = activeKey !== null && live > 0;
			const throughput = active ? live : sessionTokensPerSecond(stats);
			const value = formatTokensPerSecond(throughput);
			const mode = active ? t("live") : t("session");

			return (0, react_jsx_runtime.jsx)("span", {
				className: "dshGlobalTokenMeter",
				"data-active": active,
				role: "status",
				"aria-live": "off",
				"aria-label": t("aria", { value, mode }),
				title: t("aria", { value, mode }),
				children: [
					(0, react_jsx_runtime.jsx)("span", { className: "dshGlobalTokenMeter__dot", "aria-hidden": true }),
					(0, react_jsx_runtime.jsx)("span", { className: "dshGlobalTokenMeter__label", children: t("label") }),
					(0, react_jsx_runtime.jsxs)("span", { className: "dshGlobalTokenMeter__value", children: [value, " ", t("unit")] })
				]
			});
		}

		const inject = ["slots", "locale"];
		function apply(ctx) {
			ctx.effect(() => ctx.locale.register(NS, { en, zh }), "global-token-meter: dictionaries");
			ctx.slots.inject("conversation.session.header.utilities", () => ctx.slots.register({
				name: "conversation.session.header.utilities",
				id: "global-token-meter",
				order: 90,
				locale: NS
			}, GlobalTokenMeter));
		}

		exports.apply = apply;
		exports.inject = inject;
		return module.exports;
	}
});
