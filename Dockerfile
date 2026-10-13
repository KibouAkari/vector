FROM node:24-alpine AS dependencies

WORKDIR /app

COPY package.json ./

RUN npm install --omit=dev


FROM node:24-alpine AS builder

WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=dependencies /app/node_modules ./node_modules

COPY . .

RUN npm run build


FROM node:24-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup \
    --system \
    --gid 1001 \
    vector

RUN adduser \
    --system \
    --uid 1001 \
    --ingroup vector \
    vector

COPY --from=builder \
    --chown=vector:vector \
    /app/.next/standalone \
    ./

COPY --from=builder \
    --chown=vector:vector \
    /app/.next/static \
    ./.next/static

# VECTOR_PDF_RUNTIME_PACKAGING_5763
#
# pdf-lib is dynamically imported by artifact-runtime.js.
# Next standalone output does not currently trace/copy it,
# so include only pdf-lib and its verified production runtime
# dependency closure instead of copying all node_modules.
COPY --from=dependencies \
    --chown=vector:vector \
    /app/node_modules/pdf-lib \
    ./node_modules/pdf-lib

COPY --from=dependencies \
    --chown=vector:vector \
    /app/node_modules/@pdf-lib/standard-fonts \
    ./node_modules/@pdf-lib/standard-fonts

COPY --from=dependencies \
    --chown=vector:vector \
    /app/node_modules/@pdf-lib/upng \
    ./node_modules/@pdf-lib/upng

COPY --from=dependencies \
    --chown=vector:vector \
    /app/node_modules/pako \
    ./node_modules/pako

COPY --from=dependencies \
    --chown=vector:vector \
    /app/node_modules/tslib \
    ./node_modules/tslib


# VECTOR_DOCX_RUNTIME_PACKAGING_57710
#
# DOCX Composer v3 dynamically imports "docx".
# Next standalone contains a bundled server chunk but does not
# expose the package to native Node ESM package resolution.
#
# Copy the audited docx 9.7.2 runtime dependency closure only.
# pako is already copied above by VECTOR_PDF_RUNTIME_PACKAGING_5763.
COPY --from=dependencies \
    --chown=vector:vector \
    /app/node_modules/docx \
    ./node_modules/docx

COPY --from=dependencies \
    --chown=vector:vector \
    /app/node_modules/@types/node \
    ./node_modules/@types/node

COPY --from=dependencies \
    --chown=vector:vector \
    /app/node_modules/undici-types \
    ./node_modules/undici-types

COPY --from=dependencies \
    --chown=vector:vector \
    /app/node_modules/hash.js \
    ./node_modules/hash.js

COPY --from=dependencies \
    --chown=vector:vector \
    /app/node_modules/minimalistic-assert \
    ./node_modules/minimalistic-assert

COPY --from=dependencies \
    --chown=vector:vector \
    /app/node_modules/inherits \
    ./node_modules/inherits

COPY --from=dependencies \
    --chown=vector:vector \
    /app/node_modules/jszip \
    ./node_modules/jszip

COPY --from=dependencies \
    --chown=vector:vector \
    /app/node_modules/lie \
    ./node_modules/lie

COPY --from=dependencies \
    --chown=vector:vector \
    /app/node_modules/immediate \
    ./node_modules/immediate

COPY --from=dependencies \
    --chown=vector:vector \
    /app/node_modules/setimmediate \
    ./node_modules/setimmediate

COPY --from=dependencies \
    --chown=vector:vector \
    /app/node_modules/core-util-is \
    ./node_modules/core-util-is

COPY --from=dependencies \
    --chown=vector:vector \
    /app/node_modules/isarray \
    ./node_modules/isarray

COPY --from=dependencies \
    --chown=vector:vector \
    /app/node_modules/process-nextick-args \
    ./node_modules/process-nextick-args

COPY --from=dependencies \
    --chown=vector:vector \
    /app/node_modules/util-deprecate \
    ./node_modules/util-deprecate

COPY --from=dependencies \
    --chown=vector:vector \
    /app/node_modules/nanoid \
    ./node_modules/nanoid

COPY --from=dependencies \
    --chown=vector:vector \
    /app/node_modules/xml \
    ./node_modules/xml

COPY --from=dependencies \
    --chown=vector:vector \
    /app/node_modules/sax \
    ./node_modules/sax

COPY --from=dependencies \
    --chown=vector:vector \
    /app/node_modules/xml-js \
    ./node_modules/xml-js


USER vector

EXPOSE 3000

CMD ["node", "server.js"]

COPY --from=builder --chown=vector:vector /app/public ./public
