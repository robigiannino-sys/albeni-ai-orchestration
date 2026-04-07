FROM node:18-alpine

WORKDIR /app

# Install curl for healthcheck
RUN apk add --no-cache curl

COPY package*.json ./
RUN npm install --production

COPY . .

# Create dashboard directory (will be populated from root context or volume)
RUN mkdir -p /app/dashboard

# Railway assigns PORT dynamically
ENV PORT=3000
EXPOSE ${PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

CMD ["node", "server.js"]
