FROM node:22-alpine AS build

WORKDIR /app

COPY client/package.json client/package-lock.json ./

RUN npm ci

COPY client/ ./

ARG CLIENT_ORIGIN

ENV CLIENT_ORIGIN=${CLIENT_ORIGIN}

RUN npm run build


FROM node:22-alpine AS runtime

ENV NODE_ENV=production
ENV HOST=0.0.0.0
ENV PORT=3000

WORKDIR /app

COPY --from=build /app/build ./build

EXPOSE 3000

USER node

CMD ["node", "build"]