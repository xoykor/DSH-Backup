# Browser automation control server — mirrors the searxng deployment pattern.
FROM mcr.microsoft.com/playwright:v1.49.0-noble AS base
WORKDIR /app
ENV BROWSER_PORT=8731
COPY server.mjs ./server.mjs
RUN npm install --no-audit --no-fund playwright@1.49.0 || npx playwright@1.49.0 install chromium >/dev/null 2>&1 || true
EXPOSE 8731
CMD ["node", "server.mjs"]
