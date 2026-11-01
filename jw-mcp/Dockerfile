FROM node:22-bookworm-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force

COPY start.js ./
RUN chown -R node:node /app
USER node

ENV NODE_ENV=production \
    MCP_TRANSPORT=http \
    AUTH_STORE_PATH=/tmp/jw-mcp-auth.json

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:'+(process.env.PORT||process.env.MCP_PORT||7860)+'/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "start.js"]
